#!/usr/bin/env python3
"""JEV backed, dependency free decision router for Jev Control Plane."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONFIG_NAMES = (Path(".jev/project.json"), Path("jev.project.json"))
KEYCHAIN_SERVICE = "jev-control-plane-router"
DEFAULT_SETTINGS_FILE = Path.home() / ".config" / "jev-control-plane" / "settings.json"
PRODUCTION_TERMS = {
    "production", "prod", "live site", "deploy live", "publish", "domain",
}
DESTRUCTIVE_TERMS = {
    "drop table", "delete all", "truncate", "remove database", "force push",
    "reset database", "delete project", "destroy", "purge",
}
HIGH_RISK_TERMS = {
    "migration", "authentication", "authorization", "permissions", "rls",
    "billing", "payment", "secrets", "oauth", "dns",
}
MEDIUM_RISK_TERMS = {
    "database", "supabase", "vercel", "webhook", "integration", "deploy",
    "email", "crm", "api", "schema",
}
BUILD_TERMS = {
    "build", "create", "implement", "add", "fix", "change", "update",
    "refactor", "deploy", "connect", "design",
}
DISTINCT_TERMS = {
    "new feature", "new app", "new website", "new crm", "separate project",
    "standalone", "from scratch",
}
CONTINUATION_TERMS = {
    "continue", "also", "follow up", "same", "previous", "fix it",
}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
PROFILE_ORDER = {
    "rapid_decision": 0,
    "balanced_build": 1,
    "complex_build": 2,
    "critical_review": 3,
}
EFFORT_ORDER = {"low": 0, "medium": 1, "high": 2}
JEV_OVERRIDE_CONFIDENCE = 0.80
DEFAULT_ROUTER_TIMEOUT_SECONDS = 8
DEFAULT_LOG_MAX_BYTES = 5_000_000
DEFAULT_LOG_BACKUPS = 3
RUNTIME_MODEL_DEFAULTS = {
    "rapid_decision": "gpt-5.6-luna",
    "balanced_build": "gpt-5.6-terra",
    "complex_build": "gpt-5.6-sol",
    "critical_review": "gpt-6-astra",
}
CLAUDE_MODEL_DEFAULTS = {
    "rapid_decision": "haiku",
    "balanced_build": "sonnet",
    "complex_build": "opus",
    "critical_review": "opus",
}
ROUTED_THREAD_TOOLS = {
    "mcp__codex_app__create_thread": ("prompt", "thinking"),
    "mcp__codex_app__send_message_to_thread": ("prompt", "thinking"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(command: list[str], cwd: Path, timeout: int = 4) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = (result.stdout or result.stderr).strip()
        return result.returncode, output
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def find_config(start: Path) -> Path | None:
    explicit = os.environ.get("JEV_PROJECT_FILE")
    if explicit:
        path = Path(explicit).expanduser().resolve()
        return path if path.is_file() else None
    current = start.resolve()
    for parent in (current, *current.parents):
        for name in CONFIG_NAMES:
            candidate = parent / name
            if candidate.is_file():
                return candidate
    return None


def load_config(cwd: Path) -> tuple[dict[str, Any], Path | None, list[str]]:
    path = find_config(cwd)
    if path is None:
        return {}, None, ["project_manifest_missing"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, path, ["project_manifest_invalid"]
    if not isinstance(data, dict):
        return {}, path, ["project_manifest_invalid"]
    return data, path, []


def git_context(cwd: Path) -> dict[str, Any]:
    if shutil.which("git") is None:
        return {"available": False}
    root_code, root = run(["git", "rev-parse", "--show-toplevel"], cwd)
    if root_code != 0:
        return {"available": True, "repository": False}
    root_path = Path(root)
    _, remote = run(["git", "config", "--get", "remote.origin.url"], root_path)
    _, branch = run(["git", "branch", "--show-current"], root_path)
    _, status = run(["git", "status", "--porcelain"], root_path)
    return {
        "available": True,
        "repository": True,
        "root": str(root_path),
        "remote": remote or None,
        "branch": branch or None,
        "dirty": bool(status),
    }


def repository_slug(remote: str | None) -> str | None:
    if not remote:
        return None
    value = remote.strip().removesuffix(".git")
    if value.startswith("git@") and ":" in value:
        value = value.split(":", 1)[1]
    elif "://" in value:
        value = value.split("://", 1)[1].split("/", 1)[-1]
    parts = [part for part in value.split("/") if part]
    return "/".join(parts[-2:]).lower() if len(parts) >= 2 else None


def expected_repository(config: dict[str, Any]) -> str | None:
    github = config.get("services", {}).get("github", {})
    owner = github.get("owner")
    repository = github.get("repository")
    if owner and repository:
        return f"{owner}/{repository}".lower()
    return None


def contains_any(text: str, terms: set[str]) -> bool:
    return any(
        re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None
        for term in terms
    )


def env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return min(max(value, minimum), maximum)


def redact_secrets(text: str) -> str:
    """Best effort redaction before text leaves the local machine."""
    redacted = re.sub(
        r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+",
        r"\1 [REDACTED]",
        text,
    )
    redacted = re.sub(
        r"\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,})\b",
        "[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY)[A-Z0-9_]*)"
        r"\s*([:=])\s*([^\s,;]+)",
        r"\1\2[REDACTED]",
        redacted,
    )
    return redacted


def scope_status(prompt: str, config: dict[str, Any]) -> str:
    excluded = config.get("blueprint", {}).get("scope", {}).get("excluded", [])
    normalized = prompt.lower()
    for item in excluded:
        phrase = str(item).lower().replace("_", " ")
        if phrase and phrase in normalized:
            return "change_request"
    return "inside_scope" if config else "unknown"


def risk_level(prompt: str) -> str:
    text = prompt.lower()
    if contains_any(text, DESTRUCTIVE_TERMS):
        return "critical"
    if contains_any(text, PRODUCTION_TERMS | HIGH_RISK_TERMS):
        return "high"
    if contains_any(text, MEDIUM_RISK_TERMS):
        return "medium"
    return "low"


def model_profile(prompt: str, risk: str) -> tuple[str, str]:
    text = prompt.lower()
    if risk in {"critical", "high"}:
        return "critical_review", "high"
    if any(term in text for term in {"architecture", "redesign", "hard bug", "root cause"}):
        return "complex_build", "high"
    if contains_any(text, BUILD_TERMS):
        return "balanced_build", "medium"
    return "rapid_decision", "low"


def thread_action(prompt: str, risk: str) -> tuple[str, bool]:
    text = prompt.lower()
    if contains_any(text, CONTINUATION_TERMS):
        return "reuse_current", False
    distinct = contains_any(text, DISTINCT_TERMS)
    if distinct or risk in {"critical", "high"}:
        return "create_new", contains_any(text, BUILD_TERMS)
    return "reuse_current", False


def cli_capabilities() -> dict[str, dict[str, Any]]:
    mapping = {"github": "gh", "supabase": "supabase", "vercel": "vercel"}
    return {
        service: {"cli": executable, "installed": shutil.which(executable) is not None}
        for service, executable in mapping.items()
    }


def live_identity_checks(config: dict[str, Any], cwd: Path) -> dict[str, Any]:
    services = config.get("services", {})
    checks: dict[str, Any] = {}

    github = services.get("github", {})
    if not github:
        checks["github"] = {"status": "not_configured"}
    elif shutil.which("gh"):
        code, login = run(["gh", "api", "user", "--jq", ".login"], cwd, 8)
        expected = github.get("expected_login")
        checks["github"] = {
            "status": "ready" if code == 0 and (not expected or login == expected) else "mismatch_or_unavailable",
            "identity": login or None,
            "expected": expected,
        }
    else:
        checks["github"] = {"status": "cli_missing"}

    supabase = services.get("supabase", {})
    if not supabase:
        checks["supabase"] = {"status": "not_configured"}
    elif shutil.which("supabase"):
        code, output = run(["supabase", "projects", "list", "--output", "json"], cwd, 10)
        expected_ref = supabase.get("project_ref")
        present = False
        if code == 0:
            try:
                projects = json.loads(output)
                present = not expected_ref or any(
                    item.get("id") == expected_ref or item.get("ref") == expected_ref
                    for item in projects if isinstance(item, dict)
                )
            except json.JSONDecodeError:
                present = False
        checks["supabase"] = {
            "status": "ready" if code == 0 and present else "mismatch_or_unavailable",
            "expected_project_ref": expected_ref,
        }
    else:
        checks["supabase"] = {"status": "cli_missing"}

    vercel = services.get("vercel", {})
    if not vercel:
        checks["vercel"] = {"status": "not_configured"}
    elif shutil.which("vercel"):
        code, identity = run(["vercel", "whoami"], cwd, 8)
        expected = vercel.get("expected_login")
        checks["vercel"] = {
            "status": "ready" if code == 0 and (not expected or expected in identity) else "mismatch_or_unavailable",
            "identity": identity or None,
            "expected": expected,
        }
    else:
        checks["vercel"] = {"status": "cli_missing"}
    return checks


def router_token(cwd: Path) -> str | None:
    token = os.environ.get("JEV_ROUTER_TOKEN", "").strip()
    if token:
        return token
    if sys.platform == "darwin" and shutil.which("security"):
        code, value = run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            cwd,
            3,
        )
        if code == 0 and value:
            return value.strip()
    return None


def safe_router_endpoint(value: str) -> str | None:
    endpoint = value.strip()
    if not endpoint:
        return None
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme == "https" and parsed.netloc:
        return endpoint
    if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return endpoint
    return None


def router_endpoint() -> str | None:
    endpoint = safe_router_endpoint(os.environ.get("JEV_ROUTER_ENDPOINT", ""))
    if endpoint:
        return endpoint
    settings_path = Path(
        os.environ.get("JEV_SETTINGS_FILE", str(DEFAULT_SETTINGS_FILE))
    ).expanduser()
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    configured = settings.get("router_endpoint") if isinstance(settings, dict) else None
    return safe_router_endpoint(configured) if isinstance(configured, str) else None


def jev_router_payload(
    prompt: str,
    config: dict[str, Any],
    decision: dict[str, Any],
    git: dict[str, Any],
) -> dict[str, Any]:
    blueprint = config.get("blueprint", {})
    scope = blueprint.get("scope", {})
    return {
        "prompt": redact_secrets(prompt)[:12000],
        "context": {
            "clientId": decision["client_id"],
            "projectId": decision["project_id"],
            "projectPhase": decision["project_phase"],
            "businessGoal": redact_secrets(str(blueprint.get("business_goal", "")))[:1000],
            "requiredScope": [
                redact_secrets(str(item))[:500]
                for item in scope.get("required", [])[:100]
            ],
            "excludedScope": [
                redact_secrets(str(item))[:500]
                for item in scope.get("excluded", [])[:100]
            ],
            "definitionOfDone": [
                redact_secrets(str(item))[:500]
                for item in blueprint.get("definition_of_done", [])[:100]
            ],
            "environment": decision["environment"],
            "repository": {
                "present": bool(git.get("repository")),
                "matchesRegisteredProject": decision["repository"]["matches"],
                "dirty": git.get("dirty"),
            },
            "localRecommendation": {
                "scopeStatus": decision["scope_status"],
                "riskLevel": decision["risk_level"],
                "threadAction": decision["thread"]["action"],
                "worktreeRecommended": decision["thread"]["worktree_recommended"],
                "modelProfile": decision["model"]["profile"],
                "reasoningEffort": decision["model"]["reasoning_effort"],
            },
            "routingPolicy": {
                "deterministicFactsAreAuthoritative": True,
                "missingManifestDoesNotImplyProduction": True,
                "continuationsStayInCurrentThread": True,
                "distinctDeliverablesUseNewThread": True,
                "worktreeRequiresRepository": True,
                "highRiskUsesCriticalReview": True,
                "modelProfileDescribesExecutionWork": True,
            },
        },
    }


def request_jev_decision(
    prompt: str,
    config: dict[str, Any],
    decision: dict[str, Any],
    git: dict[str, Any],
    cwd: Path,
) -> tuple[dict[str, Any] | None, str | None]:
    token = router_token(cwd)
    if not token:
        return None, "jev_credentials_unavailable"

    endpoint = router_endpoint()
    if not endpoint:
        return None, "jev_endpoint_unavailable"
    body = json.dumps(
        jev_router_payload(prompt, config, decision, git),
        separators=(",", ":"),
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
            "user-agent": "jev-control-plane/0.2",
        },
        method="POST",
    )
    try:
        timeout = env_int(
            "JEV_ROUTER_TIMEOUT_SECONDS",
            DEFAULT_ROUTER_TIMEOUT_SECONDS,
            1,
            30,
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return None, f"jev_http_{error.code}"
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return None, "jev_unavailable"

    if (
        not isinstance(payload, dict)
        or payload.get("provider") != "jev"
        or payload.get("model") != "typesafe-ai/jev"
        or not isinstance(payload.get("decision"), dict)
    ):
        return None, "jev_response_invalid"
    return payload, None


def apply_jev_decision(
    decision: dict[str, Any],
    response: dict[str, Any],
    git: dict[str, Any],
    prompt: str,
    config: dict[str, Any],
    live: bool,
) -> None:
    routed = response["decision"]
    supported = {
        "scopeStatus": {
            "inside_scope", "necessary_dependency", "change_request", "unrelated", "unknown",
        },
        "riskLevel": {"low", "medium", "high", "critical"},
        "reversibility": {"easy", "costly", "difficult"},
        "threadAction": {"reuse_current", "create_new"},
        "modelProfile": {
            "rapid_decision", "balanced_build", "complex_build", "critical_review",
        },
        "reasoningEffort": {"low", "medium", "high"},
    }
    for key, choices in supported.items():
        if routed.get(key) not in choices:
            raise ValueError(f"unsupported Jev decision: {key}")
    if not isinstance(routed.get("worktreeRecommended"), bool):
        raise ValueError("unsupported Jev worktree decision")

    local = {
        "scope_status": decision["scope_status"],
        "risk_level": decision["risk_level"],
        "reversibility": decision["reversibility"],
        "thread_action": decision["thread"]["action"],
        "worktree_recommended": decision["thread"]["worktree_recommended"],
        "model_profile": decision["model"]["profile"],
        "reasoning_effort": decision["model"]["reasoning_effort"],
    }
    confidence = response.get("confidence", {})
    if not isinstance(confidence, dict):
        confidence = {}
    adjustments: list[str] = []

    def confident(field: str) -> bool:
        value = confidence.get(field)
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and 0 <= float(value) <= 1
            and float(value) >= JEV_OVERRIDE_CONFIDENCE
        )

    if not config:
        decision["scope_status"] = "unknown"
        if routed["scopeStatus"] != "unknown":
            adjustments.append("scope_requires_registered_manifest")
    elif local["scope_status"] == "change_request":
        decision["scope_status"] = "change_request"
        if routed["scopeStatus"] != "change_request":
            adjustments.append("explicit_scope_exclusion_preserved")
    elif confident("scopeStatus"):
        decision["scope_status"] = routed["scopeStatus"]
    else:
        decision["scope_status"] = local["scope_status"]
        if routed["scopeStatus"] != local["scope_status"]:
            adjustments.append("low_confidence_scope_override_rejected")

    routed_risk = routed["riskLevel"]
    local_risk = local["risk_level"]
    if RISK_ORDER[routed_risk] < RISK_ORDER[local_risk]:
        decision["risk_level"] = local_risk
        adjustments.append("deterministic_risk_floor_preserved")
    elif RISK_ORDER[routed_risk] > RISK_ORDER[local_risk] and not confident("riskLevel"):
        decision["risk_level"] = local_risk
        adjustments.append("low_confidence_risk_escalation_rejected")
    else:
        decision["risk_level"] = routed_risk

    decision["reversibility"] = (
        routed["reversibility"]
        if decision["risk_level"] == routed_risk
        else local["reversibility"]
    )
    if decision["risk_level"] == "critical":
        decision["reversibility"] = "difficult"
    elif decision["risk_level"] == "high" and decision["reversibility"] == "easy":
        decision["reversibility"] = "costly"
        adjustments.append("high_risk_reversibility_normalized")

    text = prompt.lower()
    explicit_continuation = contains_any(text, CONTINUATION_TERMS)
    explicit_distinct = contains_any(text, DISTINCT_TERMS)
    if explicit_continuation and not explicit_distinct:
        decision["thread"]["action"] = "reuse_current"
        if routed["threadAction"] != "reuse_current":
            adjustments.append("explicit_continuation_preserved")
    elif explicit_distinct:
        decision["thread"]["action"] = "create_new"
        if routed["threadAction"] != "create_new":
            adjustments.append("explicit_distinct_work_preserved")
    elif confident("threadAction"):
        decision["thread"]["action"] = routed["threadAction"]
    else:
        decision["thread"]["action"] = local["thread_action"]
        if routed["threadAction"] != local["thread_action"]:
            adjustments.append("low_confidence_thread_override_rejected")

    worktree = routed["worktreeRecommended"]
    if worktree and not git.get("repository"):
        worktree = False
        if "worktree_unavailable_without_repository" not in decision["warnings"]:
            decision["warnings"].append("worktree_unavailable_without_repository")
    decision["thread"]["worktree_recommended"] = worktree

    profile = routed["modelProfile"]
    effort = routed["reasoningEffort"]
    minimum_profile = local["model_profile"]
    minimum_effort = local["reasoning_effort"]
    if decision["risk_level"] in {"high", "critical"}:
        minimum_profile = "critical_review"
        minimum_effort = "high"
    elif decision["risk_level"] == "medium":
        if PROFILE_ORDER[minimum_profile] < PROFILE_ORDER["balanced_build"]:
            minimum_profile = "balanced_build"
        if EFFORT_ORDER[minimum_effort] < EFFORT_ORDER["medium"]:
            minimum_effort = "medium"
    if PROFILE_ORDER[profile] < PROFILE_ORDER[minimum_profile]:
        profile = minimum_profile
        adjustments.append("model_profile_floor_applied")
    if EFFORT_ORDER[effort] < EFFORT_ORDER[minimum_effort]:
        effort = minimum_effort
        adjustments.append("reasoning_floor_applied")
    decision["model"]["profile"] = profile
    decision["model"]["reasoning_effort"] = effort

    production_requested = contains_any(text, PRODUCTION_TERMS)
    production_policy = config.get("policy", {}).get(
        "production_requires_confirmation", True
    )
    decision["requires_confirmation"] = (
        (production_requested and production_policy)
        or decision["risk_level"] == "critical"
        or decision["reversibility"] == "difficult"
    )
    repo_mismatch = decision["repository"]["matches"] is False
    external_signal = contains_any(
        text,
        PRODUCTION_TERMS | DESTRUCTIVE_TERMS | HIGH_RISK_TERMS | MEDIUM_RISK_TERMS,
    )
    decision["external_writes_blocked"] = repo_mismatch or (
        not config
        and (
            live
            or decision["risk_level"] in {"high", "critical"}
            or external_signal
        )
    )
    decision["decision_provider"] = response["provider"]
    decision["decision_model"] = response["model"]
    decision["decision_confidence"] = confidence
    decision["jev_raw_decision"] = dict(routed)
    decision["routing_adjustments"] = adjustments


def runtime_model(profile: str, host: str = "codex", config: dict[str, Any] | None = None) -> str:
    prefix = "JEV_CLAUDE_MODEL" if host == "claude" else "JEV_RUNTIME_MODEL"
    key = f"{prefix}_{profile.upper()}"
    configured = os.environ.get(key, "").strip()
    defaults = CLAUDE_MODEL_DEFAULTS if host == "claude" else RUNTIME_MODEL_DEFAULTS
    project_mapping = (config or {}).get("runtime_models", {}).get(host, {}).get(profile)
    project_value = project_mapping.strip() if isinstance(project_mapping, str) else ""
    return configured or project_value or defaults[profile]


def routing_mode(config: dict[str, Any]) -> str:
    """Return the effective delegated routing mode without trusting arbitrary values."""
    environment_mode = os.environ.get("JEV_ROUTING_MODE")
    if environment_mode in {"active", "shadow"}:
        return environment_mode
    project_mode = config.get("routing", {}).get("mode")
    return project_mode if project_mode in {"active", "shadow"} else "active"


def apply_runtime_route(decision: dict[str, Any], host: str = "codex", config: dict[str, Any] | None = None) -> None:
    decision["runtime"] = {
        "host": host,
        "model": runtime_model(decision["model"]["profile"], host, config),
        "reasoning_effort": decision["model"]["reasoning_effort"],
    }


def decide(
    prompt: str,
    cwd: Path,
    live: bool = False,
    use_jev: bool = False,
    host: str = "codex",
) -> dict[str, Any]:
    config, config_path, warnings = load_config(cwd)
    git = git_context(cwd)
    actual_repo = repository_slug(git.get("remote"))
    expected_repo = expected_repository(config)
    repo_match = None if not expected_repo or not actual_repo else actual_repo == expected_repo
    if repo_match is False:
        warnings.append("repository_mismatch")

    risk = risk_level(prompt)
    profile, effort = model_profile(prompt, risk)
    thread, worktree = thread_action(prompt, risk)
    if worktree and not git.get("repository"):
        worktree = False
        warnings.append("worktree_unavailable_without_repository")
    scope = scope_status(prompt, config)
    production_requested = contains_any(prompt.lower(), PRODUCTION_TERMS)
    production_policy = config.get("policy", {}).get("production_requires_confirmation", True)
    default_environment = config.get("environments", {}).get("default", "unknown")
    selected_environment = "production" if production_requested else default_environment
    requires_confirmation = production_requested and production_policy
    if risk == "critical":
        requires_confirmation = True
    external_signal = contains_any(
        prompt.lower(),
        PRODUCTION_TERMS | DESTRUCTIVE_TERMS | HIGH_RISK_TERMS | MEDIUM_RISK_TERMS,
    )
    external_writes_blocked = repo_match is False or (
        not config and (live or risk in {"high", "critical"} or external_signal)
    )

    decision = {
        "schema_version": "1.1.0",
        "decided_at": utc_now(),
        "client_id": config.get("client", {}).get("client_id", "unresolved"),
        "project_id": config.get("project", {}).get("project_id", "unresolved"),
        "project_phase": config.get("blueprint", {}).get("phase", "unknown"),
        "environment": selected_environment,
        "manifest": str(config_path) if config_path else None,
        "repository": {
            "expected": expected_repo,
            "actual": actual_repo,
            "matches": repo_match,
            "branch": git.get("branch"),
            "dirty": git.get("dirty"),
        },
        "scope_status": scope,
        "risk_level": risk,
        "reversibility": "difficult" if risk == "critical" else "costly" if risk == "high" else "easy",
        "thread": {"action": thread, "worktree_recommended": worktree},
        "model": {"profile": profile, "reasoning_effort": effort},
        "capabilities": cli_capabilities(),
        "requires_confirmation": requires_confirmation,
        "external_writes_blocked": external_writes_blocked,
        "definition_of_done": config.get("blueprint", {}).get("definition_of_done", []),
        "warnings": warnings,
        "decision_provider": "local_fallback",
        "decision_model": "local_rules_v1",
        "routing_mode": routing_mode(config),
    }
    if use_jev:
        response, error = request_jev_decision(prompt, config, decision, git, cwd)
        if response:
            try:
                apply_jev_decision(decision, response, git, prompt, config, live)
            except ValueError:
                decision["warnings"].append("jev_response_invalid")
        elif error:
            decision["warnings"].append(error)
    if live:
        decision["identity_checks"] = live_identity_checks(config, cwd)
    apply_runtime_route(decision, host, config)
    return decision


def rotate_decision_log(path: Path, incoming_bytes: int) -> None:
    max_bytes = env_int(
        "JEV_DECISION_LOG_MAX_BYTES",
        DEFAULT_LOG_MAX_BYTES,
        1024,
        100_000_000,
    )
    backups = env_int("JEV_DECISION_LOG_BACKUPS", DEFAULT_LOG_BACKUPS, 0, 20)
    try:
        current_bytes = path.stat().st_size
    except FileNotFoundError:
        return
    if current_bytes + incoming_bytes <= max_bytes:
        return
    if backups == 0:
        path.unlink(missing_ok=True)
        return
    oldest = path.with_name(f"{path.name}.{backups}")
    oldest.unlink(missing_ok=True)
    for index in range(backups - 1, 0, -1):
        source = path.with_name(f"{path.name}.{index}")
        if source.exists():
            source.replace(path.with_name(f"{path.name}.{index + 1}"))
    path.replace(path.with_name(f"{path.name}.1"))


def record_decision(decision: dict[str, Any], prompt: str) -> None:
    path = log_directory()
    if path is None:
        return
    path.mkdir(parents=True, exist_ok=True)
    record = dict(decision)
    record["prompt_sha256"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    line = json.dumps(record, separators=(",", ":")) + "\n"
    log_path = path / "decisions.jsonl"
    rotate_decision_log(log_path, len(line.encode("utf-8")))
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def hook_context(decision: dict[str, Any]) -> str:
    warnings = ",".join(decision["warnings"]) or "none"
    done = decision.get("definition_of_done", [])
    done_text = "; ".join(str(item) for item in done[:4]) or "not_registered"
    return (
        "Jev decision context. "
        f"provider={decision['decision_provider']}; model={decision['decision_model']}; "
        f"client={decision['client_id']}; project={decision['project_id']}; "
        f"phase={decision['project_phase']}; scope={decision['scope_status']}; "
        f"environment={decision['environment']}; "
        f"risk={decision['risk_level']}; reversibility={decision['reversibility']}; "
        f"thread={decision['thread']['action']}; "
        f"worktree={decision['thread']['worktree_recommended']}; "
        f"model_profile={decision['model']['profile']}; "
        f"reasoning={decision['model']['reasoning_effort']}; "
        f"runtime_model={decision['runtime']['model']}; "
        f"runtime_reasoning={decision['runtime']['reasoning_effort']}; "
        f"routing_mode={decision['routing_mode']}; "
        f"confirmation={decision['requires_confirmation']}; "
        f"external_writes_blocked={decision['external_writes_blocked']}; "
        f"warnings={warnings}; definition_of_done={done_text}. "
        "Treat these routing fields as authoritative for this prompt. "
        "The current turn model is already selected, so runtime fields apply when delegating work. "
        "For planning, classification, or read only requests, report them exactly and do not run preflight. "
        "Before consequential external work, preflight may add identity evidence but must not replace request routing. "
        "Never expose secrets. Verify identity before external writes."
    )


def routed_prompt(prompt: str, decision: dict[str, Any]) -> str:
    context = hook_context(decision)
    return (
        "<jev_routing_context>\n"
        f"{context}\n"
        "The delegated runtime was selected before this task started. Report these values exactly "
        "when asked, and distinguish the JEV decision model from the actual runtime model.\n"
        "</jev_routing_context>\n\n"
        f"{prompt}"
    )


def route_tool_call(payload: dict[str, Any]) -> dict[str, Any] | None:
    tool_name = str(payload.get("tool_name", ""))
    route = ROUTED_THREAD_TOOLS.get(tool_name)
    if route is None:
        return None
    prompt_field, reasoning_field = route
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    prompt = tool_input.get(prompt_field)
    if not isinstance(prompt, str) or not prompt.strip():
        return None
    cwd = Path(payload.get("cwd") or os.getcwd())
    decision = decide(prompt, cwd, use_jev=True)
    decision["route_applied"] = decision["routing_mode"] == "active"
    record_decision(decision, prompt)
    if decision["routing_mode"] == "shadow":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": (
                    "JEV shadow mode observed delegated work without changing tool input. "
                    f"Recommendation: profile={decision['model']['profile']}, "
                    f"model={decision['runtime']['model']}, "
                    f"reasoning={decision['runtime']['reasoning_effort']}."
                ),
            }
        }
    updated = dict(tool_input)
    updated[prompt_field] = routed_prompt(prompt, decision)
    updated["model"] = decision["runtime"]["model"]
    updated[reasoning_field] = decision["runtime"]["reasoning_effort"]
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": updated,
            "additionalContext": (
                "JEV applied delegated runtime routing: "
                f"profile={decision['model']['profile']}; "
                f"model={decision['runtime']['model']}; "
                f"reasoning={decision['runtime']['reasoning_effort']}."
            ),
        }
    }


def route_claude_agent_call(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("tool_name") not in {"Agent", "Task"}:
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return None
    cwd = Path(payload.get("cwd") or os.getcwd())
    decision = decide(prompt, cwd, use_jev=True, host="claude")
    decision["route_applied"] = decision["routing_mode"] == "active"
    record_decision(decision, prompt)
    if decision["routing_mode"] == "shadow":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": (
                    "JEV shadow mode observed delegated work without changing tool input. "
                    f"Recommendation: profile={decision['model']['profile']}, "
                    f"model={decision['runtime']['model']}, "
                    f"reasoning={decision['runtime']['reasoning_effort']}."
                ),
            }
        }
    updated = dict(tool_input)
    updated["prompt"] = routed_prompt(prompt, decision)
    agent_type = tool_input.get("subagent_type")
    generic = agent_type in {"general-purpose", "general_purpose"}
    if generic:
        effort = decision["runtime"]["reasoning_effort"]
        updated["subagent_type"] = f"jev-control-plane:routed-{effort}"
        updated["model"] = decision["runtime"]["model"]
        status = "JEV applied Claude model and effort to a general agent"
    else:
        status = "JEV preserved the specialized Claude agent and added context only"
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": updated,
            "additionalContext": status,
        }
    }


def plugin_host() -> str:
    if os.environ.get("PLUGIN_ROOT"):
        return "codex"
    return "claude" if os.environ.get("CLAUDE_PLUGIN_ROOT") else "codex"


def log_directory() -> Path | None:
    if plugin_host() == "claude":
        value = os.environ.get("CLAUDE_PLUGIN_DATA") or os.environ.get("PLUGIN_DATA")
    else:
        value = os.environ.get("PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    return Path(value).expanduser() if value else None


def recent_decisions(limit: int, directory: Path | None = None) -> dict[str, Any]:
    directory = directory or log_directory()
    if directory is None:
        return {
            "data_directory": None,
            "decisions": [],
            "summary": {"provider": {}, "profile": {}, "runtime_model": {}},
            "warning": "plugin_data_unavailable",
        }
    path = directory / "decisions.jsonl"
    records: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
                    records = records[-limit:]
    except FileNotFoundError:
        pass
    summary: dict[str, dict[str, int]] = {
        "provider": {}, "profile": {}, "runtime_model": {},
    }
    for record in records:
        model = record.get("model") if isinstance(record.get("model"), dict) else {}
        runtime = record.get("runtime") if isinstance(record.get("runtime"), dict) else {}
        values = {
            "provider": record.get("decision_provider"),
            "profile": model.get("profile"),
            "runtime_model": runtime.get("model"),
        }
        for category, value in values.items():
            if isinstance(value, str):
                summary[category][value] = summary[category].get(value, 0) + 1
    return {"data_directory": str(directory), "decisions": records, "summary": summary}


def installation_doctor(cwd: Path) -> dict[str, Any]:
    config, path, warnings = load_config(cwd)
    endpoint = router_endpoint()
    return {
        "python_supported": sys.version_info >= (3, 10),
        "project_manifest": str(path) if config else None,
        "project_warnings": warnings,
        "router_endpoint_configured": endpoint is not None,
        "router_token_configured": router_token(cwd) is not None,
        "git_repository": git_context(cwd).get("repository", False),
        "decision_log_directory": str(log_directory()) if log_directory() else None,
        "codex_plugin_root": bool(os.environ.get("PLUGIN_ROOT")),
        "claude_plugin_root": bool(os.environ.get("CLAUDE_PLUGIN_ROOT")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Jev Control Plane local decision router")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("hook")
    subparsers.add_parser("route-tool")
    decide_parser = subparsers.add_parser("decide")
    decide_parser.add_argument("--prompt", required=True)
    decide_parser.add_argument("--cwd", default=os.getcwd())
    decide_parser.add_argument("--host", choices=("codex", "claude"), default="codex")
    decide_parser.add_argument("--json", action="store_true")
    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--cwd", default=os.getcwd())
    recent_parser = subparsers.add_parser("recent")
    recent_parser.add_argument("--limit", type=int, default=10)
    recent_parser.add_argument("--data-dir")
    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("--cwd", default=os.getcwd())
    preflight_parser.add_argument(
        "--prompt",
        default="Verify configured account identities",
        help="Optional request context. Neutral identity verification is used by default.",
    )
    dashboard_parser = subparsers.add_parser("dashboard")
    dashboard_parser.add_argument("--cwd", default=os.getcwd())
    dashboard_parser.add_argument("--data-dir")
    dashboard_parser.add_argument("--port", type=int, default=8765)
    dashboard_parser.add_argument("--demo", action="store_true")
    recipes_parser = subparsers.add_parser("recipes")
    recipes_parser.add_argument("--cwd", default=os.getcwd())
    recipes_parser.add_argument("--preview")
    recipes_parser.add_argument("--apply")
    recipes_parser.add_argument("--project-id")
    handoff_parser = subparsers.add_parser("handoff")
    handoff_parser.add_argument("--prompt", required=True)
    handoff_parser.add_argument("--cwd", default=os.getcwd())
    handoff_parser.add_argument("--host", choices=("codex", "claude"), default="codex")
    handoff_parser.add_argument("--use-jev", action="store_true")
    verify_parser = subparsers.add_parser("handoff-verify")
    verify_parser.add_argument("--file", required=True)
    adapter_parser = subparsers.add_parser("adapter-check")
    adapter_parser.add_argument("--spec", required=True)
    advice_parser = subparsers.add_parser("pr-advice")
    advice_parser.add_argument("--cwd", default=os.getcwd())
    advice_parser.add_argument("--base", required=True)
    advice_parser.add_argument("--head", default="HEAD")
    advice_parser.add_argument("--title", default="")
    advice_parser.add_argument("--title-env")
    advice_parser.add_argument("--use-jev", action="store_true")
    advice_parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args()

    if args.command == "dashboard":
        from jev_dashboard import serve_dashboard
        return serve_dashboard(Path(args.cwd), args.port, Path(args.data_dir) if args.data_dir else None, args.demo)

    if args.command in {"recipes", "handoff", "handoff-verify", "adapter-check", "pr-advice"}:
        import jev_features as features

        if args.command == "recipes":
            config, manifest, _ = load_config(Path(args.cwd))
            if args.apply:
                if manifest is None:
                    parser.error("No project manifest found")
                if not args.project_id:
                    parser.error("--project-id is required when applying a recipe")
                print(json.dumps(features.apply_recipe(manifest, args.apply, args.project_id), indent=2))
            elif args.preview:
                preview = features.preview_recipe(config, args.preview)
                print(json.dumps({
                    "recipe": preview["recipe"],
                    "before": {key: config.get(key) for key in ("policy", "routing")},
                    "after": {key: preview["after"].get(key) for key in ("policy", "routing")},
                }, indent=2))
            else:
                print(json.dumps(features.list_recipes(), indent=2))
            return 0
        if args.command == "handoff":
            decision = decide(args.prompt, Path(args.cwd), use_jev=args.use_jev, host=args.host)
            print(json.dumps(features.build_handoff(decision), indent=2))
            return 0
        if args.command == "handoff-verify":
            try:
                packet = json.loads(Path(args.file).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                packet = None
            report = features.verify_handoff(packet)
            print(json.dumps(report, indent=2))
            return 0 if report["valid"] else 1
        if args.command == "adapter-check":
            try:
                adapter = json.loads(Path(args.spec).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                adapter = None
            report = features.validate_adapter(adapter)
            print(json.dumps(report, indent=2))
            return 0 if report["valid"] else 1
        title = os.environ.get(args.title_env, "") if args.title_env else args.title
        try:
            changes = features.collect_pr_changes(Path(args.cwd), args.base, args.head)
        except ValueError as error:
            parser.error(str(error))
        names = " ".join(item["path"] for item in changes[:30])
        prompt = f"Review pull request: {title[:240]}. Changed paths: {names[:3000]}"
        decision = decide(prompt, Path(args.cwd), use_jev=args.use_jev)
        report = features.pr_advice(title, changes, decision)
        print(features.pr_markdown(report) if args.markdown else json.dumps(report, indent=2))
        return 0

    if args.command == "hook":
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError:
            return 0
        prompt = str(payload.get("prompt", ""))
        cwd = Path(payload.get("cwd") or os.getcwd())
        decision = decide(prompt, cwd, use_jev=True, host=plugin_host())
        record_decision(decision, prompt)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": hook_context(decision),
            }
        }))
        return 0

    if args.command == "route-tool":
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError:
            return 0
        routed = (
            route_claude_agent_call(payload)
            if plugin_host() == "claude" and payload.get("tool_name") in {"Agent", "Task"}
            else route_tool_call(payload)
        )
        if routed is not None:
            print(json.dumps(routed))
        return 0

    if args.command == "decide":
        decision = decide(args.prompt, Path(args.cwd), use_jev=True, host=args.host)
        print(json.dumps(decision, indent=2) if args.json else hook_context(decision))
        return 0

    if args.command == "doctor":
        report = installation_doctor(Path(args.cwd))
        print(json.dumps(report, indent=2))
        return 0 if all((
            report["python_supported"],
            report["project_manifest"],
            report["router_endpoint_configured"],
            report["router_token_configured"],
        )) else 1

    if args.command == "recent":
        directory = Path(args.data_dir).expanduser() if args.data_dir else None
        print(json.dumps(recent_decisions(min(max(args.limit, 1), 100), directory), indent=2))
        return 0

    decision = decide(args.prompt, Path(args.cwd), live=True)
    print(json.dumps(decision, indent=2))
    return 1 if decision["external_writes_blocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

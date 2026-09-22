"""Local, dependency free product features around the JEV decision engine."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


RECIPE_DIRECTORY = Path(__file__).resolve().parents[1] / "recipes"
ALLOWED_RECIPE_FIELDS = {"policy", "routing"}
ALLOWED_POLICY_FIELDS = {"production_requires_confirmation", "destructive_actions"}
ALLOWED_ROUTING_FIELDS = {"mode"}
HANDOFF_FIELDS = (
    "client_id", "project_id", "project_phase", "environment", "scope_status",
    "risk_level", "reversibility", "thread", "model", "runtime", "repository",
    "requires_confirmation", "external_writes_blocked", "definition_of_done",
    "decision_provider", "decision_model", "routing_mode", "warnings",
)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def redact_packet_value(value: Any) -> Any:
    """Apply best effort credential redaction to exported project metadata."""
    if isinstance(value, dict):
        return {key: redact_packet_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_packet_value(item) for item in value]
    if not isinstance(value, str):
        return value
    text = re.sub(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+", r"\1 [REDACTED]", value)
    text = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,})\b", "[REDACTED]", text)
    return re.sub(
        r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY)[A-Z0-9_]*)\s*([:=])\s*([^\s,;]+)",
        r"\1\2[REDACTED]", text,
    )


def build_handoff(decision: dict[str, Any]) -> dict[str, Any]:
    """Carry decision context between agents without raw prompts or credentials."""
    packet = {
        "format": "jev-handoff-v1",
        "created_at": decision.get("decided_at"),
        "context": redact_packet_value({key: decision[key] for key in HANDOFF_FIELDS if key in decision}),
        "notice": "Context only. Recheck project identity and permissions before external writes.",
    }
    packet["sha256"] = hashlib.sha256(canonical_json(packet)).hexdigest()
    return packet


def verify_handoff(packet: Any) -> dict[str, Any]:
    if not isinstance(packet, dict) or packet.get("format") != "jev-handoff-v1":
        return {"valid": False, "reason": "invalid_format"}
    expected = packet.get("sha256")
    unsigned = {key: value for key, value in packet.items() if key != "sha256"}
    digest = hashlib.sha256(canonical_json(unsigned)).hexdigest()
    context = packet.get("context")
    valid = (
        isinstance(expected, str) and expected == digest
        and isinstance(context, dict)
        and all(key in HANDOFF_FIELDS for key in context)
    )
    return {
        "valid": valid,
        "reason": "checksum_match" if valid else "invalid_context_or_checksum",
        "authenticated": False,
        "notice": "The checksum detects changes but does not prove who created this packet.",
    }


def list_recipes() -> list[dict[str, Any]]:
    recipes = []
    for path in sorted(RECIPE_DIRECTORY.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("id") != path.stem:
            raise ValueError(f"Recipe id does not match filename: {path.name}")
        validate_recipe(data)
        recipes.append(data)
    return recipes


def validate_recipe(recipe: dict[str, Any]) -> None:
    changes = recipe.get("changes")
    if not isinstance(changes, dict) or not changes or set(changes) - ALLOWED_RECIPE_FIELDS:
        raise ValueError("Recipe has unsupported changes")
    policy = changes.get("policy", {})
    routing = changes.get("routing", {})
    if not isinstance(policy, dict) or set(policy) - ALLOWED_POLICY_FIELDS:
        raise ValueError("Recipe has unsupported policy fields")
    if not isinstance(routing, dict) or set(routing) - ALLOWED_ROUTING_FIELDS:
        raise ValueError("Recipe has unsupported routing fields")
    if "production_requires_confirmation" in policy and policy["production_requires_confirmation"] is not True:
        raise ValueError("Recipe cannot disable production confirmation")
    if "destructive_actions" in policy and policy["destructive_actions"] != "block_without_explicit_request":
        raise ValueError("Recipe cannot weaken destructive action policy")
    if "mode" in routing and routing["mode"] not in {"active", "shadow"}:
        raise ValueError("Unsupported routing mode")


def preview_recipe(config: dict[str, Any], recipe_id: str) -> dict[str, Any]:
    recipe = next((item for item in list_recipes() if item["id"] == recipe_id), None)
    if recipe is None:
        raise ValueError("Unknown recipe")
    updated = json.loads(json.dumps(config))
    for section, changes in recipe["changes"].items():
        updated.setdefault(section, {}).update(changes)
    return {"recipe": recipe, "before": config, "after": updated}


def apply_recipe(manifest: Path, recipe_id: str, expected_project_id: str) -> dict[str, Any]:
    """Atomically apply a selected recipe after caller explicitly opts in."""
    if manifest.is_symlink():
        raise ValueError("Refusing to edit a symlinked manifest")
    original = json.loads(manifest.read_text(encoding="utf-8"))
    actual = original.get("project", {}).get("project_id")
    if not expected_project_id or actual != expected_project_id:
        raise ValueError("Project identity does not match")
    preview = preview_recipe(original, recipe_id)
    fd, name = tempfile.mkstemp(prefix=".jev-recipe-", suffix=".json", dir=manifest.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(preview["after"], handle, indent=2)
            handle.write("\n")
        os.replace(name, manifest)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return {"applied": recipe_id, "manifest": str(manifest), "project_id": actual}


def update_model_mapping(
    manifest: Path, project_id: str, host: str, profile: str,
    model: str, expected_current: str,
) -> dict[str, Any]:
    """Save one project model mapping after identity and stale value checks."""
    if manifest.is_symlink():
        raise ValueError("Refusing to edit a symlinked manifest")
    if host not in {"codex", "claude"}:
        raise ValueError("Unsupported host")
    if profile not in {"rapid_decision", "balanced_build", "complex_build", "critical_review"}:
        raise ValueError("Unsupported profile")
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,100}", model):
        raise ValueError("Model name must be a simple model identifier")
    config = json.loads(manifest.read_text(encoding="utf-8"))
    if config.get("project", {}).get("project_id") != project_id or not project_id:
        raise ValueError("Project identity does not match")
    current = config.get("runtime_models", {}).get(host, {}).get(profile)
    if current != expected_current:
        raise ValueError("Model mapping changed since the dashboard loaded")
    config.setdefault("runtime_models", {}).setdefault(host, {})[profile] = model
    fd, name = tempfile.mkstemp(prefix=".jev-model-", suffix=".json", dir=manifest.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)
            handle.write("\n")
        os.replace(name, manifest)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return {"saved": True, "project_id": project_id, "host": host, "profile": profile, "model": model}


def validate_adapter(spec: Any) -> dict[str, Any]:
    """Validate the small host adapter contract used by community integrations."""
    if not isinstance(spec, dict):
        return {"valid": False, "errors": ["adapter must be an object"]}
    errors = []
    required = ("id", "tool_names", "prompt_field", "model_field", "reasoning_field")
    for field in required:
        if field not in spec:
            errors.append(f"missing {field}")
    if not isinstance(spec.get("id"), str) or not spec.get("id"):
        errors.append("id must be a nonempty string")
    names = spec.get("tool_names")
    if not isinstance(names, list) or not names or not all(isinstance(item, str) and item for item in names):
        errors.append("tool_names must contain at least one name")
    for field in ("prompt_field", "model_field", "reasoning_field"):
        if not isinstance(spec.get(field), str) or not spec.get(field):
            errors.append(f"{field} must be a nonempty string")
    if len({spec.get(field) for field in ("prompt_field", "model_field", "reasoning_field")}) != 3:
        errors.append("prompt, model, and reasoning fields must differ")
    return {"valid": not errors, "errors": errors}


def adapt_tool_input(spec: dict[str, Any], tool_name: str, tool_input: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    result = validate_adapter(spec)
    if not result["valid"]:
        raise ValueError("Invalid adapter: " + ", ".join(result["errors"]))
    if tool_name not in spec["tool_names"]:
        raise ValueError("Tool is not covered by this adapter")
    updated = dict(tool_input)
    if decision.get("routing_mode") == "shadow":
        return updated
    updated[spec["model_field"]] = decision["runtime"]["model"]
    updated[spec["reasoning_field"]] = decision["runtime"]["reasoning_effort"]
    return updated


def collect_pr_changes(cwd: Path, base: str, head: str) -> list[dict[str, Any]]:
    """Read local Git metadata only. No network or GitHub account is required."""
    for ref in (base, head):
        checked = subprocess.run(
            ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=cwd,
            capture_output=True, text=True, check=False, timeout=10,
        )
        if checked.returncode:
            raise ValueError(f"Unknown Git commit or ref: {ref}")
    result = subprocess.run(
        ["git", "diff", "--no-ext-diff", "--numstat", base, head, "--"],
        cwd=cwd, capture_output=True, text=True, check=False, timeout=20,
    )
    if result.returncode:
        raise ValueError("Could not read local Git diff")
    changes = []
    for line in result.stdout.splitlines()[:300]:
        parts = line.split("\t", 2)
        if len(parts) == 3:
            additions, deletions, path = parts
            changes.append({
                "path": path,
                "additions": int(additions) if additions.isdigit() else None,
                "deletions": int(deletions) if deletions.isdigit() else None,
            })
    return changes


def pr_advice(title: str, changes: list[dict[str, Any]], decision: dict[str, Any]) -> dict[str, Any]:
    paths = [item["path"] for item in changes]
    tests = [path for path in paths if "test" in path.lower()]
    areas = []
    for label, terms in (
        ("database", ("migration", "schema", ".sql")),
        ("security", ("auth", "permission", "rls", "secret")),
        ("deployment", ("deploy", "vercel", "docker", ".github/workflows")),
    ):
        if any(any(term in path.lower() for term in terms) for path in paths):
            areas.append(label)
    checks = ["Run the repository test suite", "Review the changed files and expected behavior"]
    if "database" in areas:
        checks.append("Review migration rollback and data compatibility")
    if "security" in areas:
        checks.append("Verify authorization and access boundaries")
    if "deployment" in areas:
        checks.append("Verify deployment configuration before release")
    if not tests and changes:
        checks.append("Confirm whether the change needs automated tests")
    return {
        "title": title[:240],
        "file_count": len(changes),
        "changed_files": changes,
        "sensitive_areas": areas,
        "decision_provider": decision["decision_provider"],
        "risk": decision["risk_level"],
        "model_profile": decision["model"]["profile"],
        "recommended_runtime": decision["runtime"],
        "requires_confirmation": decision["requires_confirmation"],
        "external_writes_blocked": decision["external_writes_blocked"],
        "verification": checks,
        "notice": "Advisory only. This command does not edit files, post comments, or deploy.",
    }


def pr_markdown(report: dict[str, Any]) -> str:
    lines = [
        "## JEV pull request advice", "",
        f"Risk: {report['risk']}",
        f"Recommended profile: {report['model_profile']}",
        f"Suggested runtime: {report['recommended_runtime']['model']} ({report['recommended_runtime']['reasoning_effort']})",
        f"Decision provider: {report['decision_provider']}",
        f"Files reviewed: {report['file_count']}",
        "", "Verification to consider:",
    ]
    lines.extend(f"* {item}" for item in report["verification"])
    lines.extend(["", report["notice"], ""])
    return "\n".join(lines)

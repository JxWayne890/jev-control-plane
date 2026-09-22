"""Localhost only dashboard for inspecting and testing JEV routing."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import jev_control_plane as core
import jev_features as features


ASSET_DIRECTORY = Path(__file__).resolve().parents[1] / "dashboard"
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/bars.css": ("bars.css", "text/css; charset=utf-8"),
    "/model-controls.css": ("model-controls.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
VISIBLE_DECISION_FIELDS = {
    "decided_at", "client_id", "project_id", "environment", "scope_status",
    "risk_level", "reversibility", "thread", "model", "runtime", "repository",
    "requires_confirmation", "external_writes_blocked", "warnings", "decision_provider",
    "decision_model", "routing_mode", "route_applied", "prompt_sha256", "routing_adjustments",
}


def public_decision(decision: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in decision.items() if key in VISIBLE_DECISION_FIELDS}


def demo_decisions() -> list[dict[str, Any]]:
    examples = [
        ("2026-09-21T10:35:00Z", "local_fallback", "critical_review", "gpt-6-astra", "high", "high", False),
        ("2026-09-21T12:10:00Z", "jev", "complex_build", "gpt-5.6-sol", "high", "medium", False),
        ("2026-09-21T13:42:00Z", "jev", "balanced_build", "gpt-5.6-terra", "medium", "low", True),
        ("2026-09-21T14:16:00Z", "jev", "rapid_decision", "gpt-5.6-luna", "low", "low", True),
    ]
    return [
        {
            "decided_at": when, "client_id": "sample", "project_id": "sample-app",
            "environment": "local", "scope_status": "inside_scope", "risk_level": risk,
            "decision_provider": provider,
            "decision_model": "typesafe-ai/jev" if provider == "jev" else "local_rules_v1",
            "thread": {"action": "reuse_current", "worktree_recommended": False},
            "model": {"profile": profile, "reasoning_effort": effort},
            "runtime": {"host": "codex", "model": model, "reasoning_effort": effort},
            "repository": {"matches": True, "branch": "main", "dirty": False},
            "requires_confirmation": risk == "high", "external_writes_blocked": False,
            "routing_mode": "active" if applied else "shadow", "route_applied": applied,
            "warnings": ["jev_unavailable"] if provider == "local_fallback" else [],
        }
        for when, provider, profile, model, effort, risk, applied in examples
    ]


def dashboard_state(cwd: Path, data_dir: Path | None, demo: bool) -> dict[str, Any]:
    config, path, warnings = core.load_config(cwd)
    history = demo_decisions() if demo else [
        public_decision(item)
        for item in core.recent_decisions(60, data_dir).get("decisions", [])
    ]
    profiles = list(core.PROFILE_ORDER)
    return {
        "demo": demo,
        "project": {
            "client": "Sample organization" if demo else config.get("client", {}).get("display_name", "Unregistered"),
            "name": "Sample application" if demo else config.get("project", {}).get("project_id", "Unregistered"),
            "manifest": "sample data" if demo else str(path) if path else None,
            "phase": "implementation" if demo else config.get("blueprint", {}).get("phase", "unknown"),
            "required_scope": [] if demo else config.get("blueprint", {}).get("scope", {}).get("required", []),
            "excluded_scope": [] if demo else config.get("blueprint", {}).get("scope", {}).get("excluded", []),
            "definition_of_done": [] if demo else config.get("blueprint", {}).get("definition_of_done", []),
            "policy": {"production_requires_confirmation": True} if demo else {
                "production_requires_confirmation": config.get("policy", {}).get("production_requires_confirmation", True),
                "destructive_actions": config.get("policy", {}).get("destructive_actions"),
            },
            "routing_mode": "shadow" if demo else core.routing_mode(config),
            "warnings": warnings,
        },
        "connection": {
            "router_endpoint_configured": False if demo else core.router_endpoint() is not None,
            "router_token_configured": False if demo else core.router_token(cwd) is not None,
            "decision_log_available": bool(data_dir or core.log_directory()),
        },
        "models": [
            {
                "profile": profile,
                "codex": core.runtime_model(profile, "codex", config),
                "claude": core.runtime_model(profile, "claude", config),
                "configured": {
                    "codex": config.get("runtime_models", {}).get("codex", {}).get(profile),
                    "claude": config.get("runtime_models", {}).get("claude", {}).get(profile),
                },
                "source": {
                    "codex": "environment" if os.environ.get(f"JEV_RUNTIME_MODEL_{profile.upper()}") else "project" if config.get("runtime_models", {}).get("codex", {}).get(profile) else "default",
                    "claude": "environment" if os.environ.get(f"JEV_CLAUDE_MODEL_{profile.upper()}") else "project" if config.get("runtime_models", {}).get("claude", {}).get(profile) else "default",
                },
            }
            for profile in profiles
        ],
        "decisions": history,
        "recipes": features.list_recipes(),
    }


def make_handler(cwd: Path, data_dir: Path | None, demo: bool):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format_string: str, *args: Any) -> None:
            return

        def _headers(self, status: int, content_type: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()

        def _send_json(self, status: int, value: Any) -> None:
            body = json.dumps(value, separators=(",", ":")).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8", len(body))
            self.wfile.write(body)

        def _valid_host(self) -> bool:
            host = self.headers.get("Host", "").split(":", 1)[0].lower()
            return host in {"127.0.0.1", "localhost"}

        def do_GET(self) -> None:
            if not self._valid_host():
                self._send_json(403, {"error": "local_host_only"})
                return
            route = urlparse(self.path).path
            if route == "/favicon.ico":
                self._headers(204, "image/x-icon", 0)
                return
            if route == "/api/state":
                self._send_json(200, dashboard_state(cwd, data_dir, demo))
                return
            asset = ASSETS.get(route)
            if asset is None:
                self._send_json(404, {"error": "not_found"})
                return
            body = (ASSET_DIRECTORY / asset[0]).read_bytes()
            self._headers(200, asset[1], len(body))
            self.wfile.write(body)

        def do_POST(self) -> None:
            if not self._valid_host():
                self._send_json(403, {"error": "local_host_only"})
                return
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc != self.headers.get("Host"):
                self._send_json(403, {"error": "origin_mismatch"})
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                self._send_json(415, {"error": "json_required"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 20000:
                    raise ValueError("Request must be between 1 and 20000 bytes")
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError("JSON object required")
                route = urlparse(self.path).path
                if route == "/api/preview":
                    prompt = payload.get("prompt")
                    host = payload.get("host", "codex")
                    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 12000:
                        raise ValueError("Enter a prompt of at most 12000 characters")
                    if host not in {"codex", "claude"}:
                        raise ValueError("Unsupported host")
                    if demo:
                        raise ValueError("The test lab is disabled in sample data mode")
                    decision = core.decide(prompt, cwd, use_jev=payload.get("use_jev") is True, host=host)
                    self._send_json(200, public_decision(decision))
                    return
                if route == "/api/handoff":
                    prompt = payload.get("prompt")
                    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 12000:
                        raise ValueError("Enter a prompt of at most 12000 characters")
                    if demo:
                        raise ValueError("Handoff export is disabled in sample data mode")
                    decision = core.decide(prompt, cwd, use_jev=False)
                    self._send_json(200, features.build_handoff(decision))
                    return
                if route == "/api/recipe-preview":
                    recipe_id = payload.get("recipe_id")
                    if not isinstance(recipe_id, str):
                        raise ValueError("Recipe id required")
                    config, _, _ = core.load_config(cwd)
                    preview = features.preview_recipe(config, recipe_id)
                    self._send_json(200, {
                        "recipe": preview["recipe"],
                        "before": {key: config.get(key) for key in ("policy", "routing")},
                        "after": {key: preview["after"].get(key) for key in ("policy", "routing")},
                    })
                    return
                if route == "/api/model-map":
                    if demo:
                        raise ValueError("Sample data mode cannot change a project")
                    config, manifest, _ = core.load_config(cwd)
                    if manifest is None or not config:
                        raise ValueError("No registered project manifest")
                    report = features.update_model_mapping(
                        manifest,
                        payload.get("project_id"),
                        payload.get("host"),
                        payload.get("profile"),
                        payload.get("model"),
                        payload.get("expected_current"),
                    )
                    self._send_json(200, report)
                    return
                self._send_json(404, {"error": "not_found"})
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json(400, {"error": str(error)})

    return Handler


def serve_dashboard(cwd: Path, port: int, data_dir: Path | None, demo: bool) -> int:
    if not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535")
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(cwd.resolve(), data_dir, demo))
    print(f"JEV dashboard: http://127.0.0.1:{server.server_port}", flush=True)
    if demo:
        print("Sample data mode. No live decisions or real project data are shown.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0

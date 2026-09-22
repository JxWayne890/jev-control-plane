#!/usr/bin/env python3
"""Run the public repository validation suite."""

from __future__ import annotations

import importlib.util
import json
import py_compile
import re
import subprocess
import sys
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "jev-control-plane"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def validate_json_files() -> None:
    for path in sorted(ROOT.rglob("*.json")):
        if ".git" not in path.parts and "node_modules" not in path.parts:
            read_json(path)
            print(f"valid json: {path.relative_to(ROOT)}")


def validate_schemas() -> None:
    project_schema = read_json(PLUGIN / "schemas" / "project.schema.json")
    decision_schema = read_json(PLUGIN / "schemas" / "decision.schema.json")
    jsonschema.Draft202012Validator.check_schema(project_schema)
    jsonschema.Draft202012Validator.check_schema(decision_schema)

    example = read_json(PLUGIN / "examples" / "project.json")
    live_manifest = read_json(ROOT / ".jev" / "project.json")
    jsonschema.validate(example, project_schema)
    jsonschema.validate(live_manifest, project_schema)

    script = PLUGIN / "scripts" / "jev_control_plane.py"
    spec = importlib.util.spec_from_file_location("jev_control_plane_check", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load decision router")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    decision = module.decide("Explain this project", ROOT)
    jsonschema.validate(decision, decision_schema)
    print("valid schemas and examples")


def validate_packaging() -> None:
    manifest = read_json(PLUGIN / ".codex-plugin" / "plugin.json")
    marketplace = read_json(ROOT / ".agents" / "plugins" / "marketplace.json")
    entry = next(
        item for item in marketplace["plugins"] if item["name"] == manifest["name"]
    )
    source = (ROOT / entry["source"]["path"]).resolve()
    if source != PLUGIN.resolve():
        raise AssertionError("marketplace source does not resolve to the plugin")

    hooks = read_json(PLUGIN / "hooks" / "hooks.json")
    claude_manifest = read_json(PLUGIN / ".claude-plugin" / "plugin.json")
    if claude_manifest["name"] != manifest["name"]:
        raise AssertionError("Codex and Claude plugin names differ")
    if claude_manifest["version"].split("+", 1)[0] != manifest["version"].split("+", 1)[0]:
        raise AssertionError("Codex and Claude plugin versions differ")
    if "Agent|Task" not in hooks["hooks"]["PreToolUse"][0]["matcher"]:
        raise AssertionError("Claude agent hook is missing")
    commands = [
        item["command"]
        for group in hooks["hooks"].values()
        for registration in group
        for item in registration["hooks"]
    ]
    if not commands or not all("scripts/jev_control_plane.py" in item for item in commands):
        raise AssertionError("hook commands do not target the decision router")
    if not all("CLAUDE_PLUGIN_ROOT" in item and "PLUGIN_ROOT" in item for item in commands):
        raise AssertionError("hook commands must resolve both plugin hosts")
    for effort in ("low", "medium", "high"):
        agent = PLUGIN / "agents" / f"routed-{effort}.md"
        contents = agent.read_text(encoding="utf-8")
        if f"name: routed-{effort}" not in contents or f"effort: {effort}" not in contents:
            raise AssertionError(f"invalid Claude agent: {agent.name}")

    required = [
        ROOT / "README.md",
        ROOT / "LICENSE",
        ROOT / "SECURITY.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "CHANGELOG.md",
        PLUGIN / "skills" / "jev-control-plane" / "SKILL.md",
        PLUGIN / "scripts" / "jev_features.py",
        PLUGIN / "scripts" / "jev_dashboard.py",
        PLUGIN / "dashboard" / "index.html",
        PLUGIN / "dashboard" / "styles.css",
        PLUGIN / "dashboard" / "app.js",
        ROOT / "docs" / "dashboard.md",
        ROOT / "docs" / "advanced-features.md",
        ROOT / "docs" / "adapters.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise AssertionError(f"missing release files: {', '.join(missing)}")
    print("valid Codex and Claude plugin packaging")


def validate_documentation() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    stale = [
        "does not silently change the active Codex model",
        "automatic model switching\",",
        "automatic thread creation\",",
    ]
    for phrase in stale:
        if phrase in readme:
            raise AssertionError(f"stale documentation found: {phrase}")
    for document in ROOT.rglob("*.md"):
        if ".git" in document.parts or "node_modules" in document.parts:
            continue
        contents = document.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", contents):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            relative = target.split("#", 1)[0]
            if relative and not (document.parent / relative).exists():
                raise AssertionError(
                    f"broken local link in {document.relative_to(ROOT)}: {target}"
                )
    for name in (
        "dashboard-overview.png", "dashboard-decisions.png", "dashboard-test-lab.png",
        "dashboard-model-controls.png", "dashboard-projects.png",
    ):
        image = ROOT / "docs" / "images" / name
        if not image.is_file() or not image.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            raise AssertionError(f"missing or invalid dashboard screenshot: {name}")
    print("valid documentation consistency")


def main() -> int:
    validate_json_files()
    for name in ("jev_control_plane.py", "jev_features.py", "jev_dashboard.py"):
        py_compile.compile(str(PLUGIN / "scripts" / name), doraise=True)
    validate_schemas()
    validate_packaging()
    validate_documentation()
    run([
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "plugins/jev-control-plane/tests",
        "-v",
    ])

    validator = (
        Path.home()
        / ".codex"
        / "skills"
        / ".system"
        / "plugin-creator"
        / "scripts"
        / "validate_plugin.py"
    )
    if validator.is_file():
        run([sys.executable, str(validator), str(PLUGIN)])
    else:
        print("plugin creator validator not installed, skipped")

    print("repository checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

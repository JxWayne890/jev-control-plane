import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import jev_control_plane as core  # noqa: E402
import jev_dashboard as dashboard  # noqa: E402
import jev_features as features  # noqa: E402


class ProductFeatureTests(unittest.TestCase):
    def project(self, directory):
        root = Path(directory)
        manifest = root / ".jev" / "project.json"
        manifest.parent.mkdir()
        manifest.write_text(json.dumps({
            "client": {"client_id": "test", "display_name": "Test"},
            "project": {"project_id": "sample", "project_type": "app"},
            "blueprint": {"phase": "implementation", "scope": {"required": [], "excluded": []}, "definition_of_done": ["Tests pass"]},
            "services": {}, "environments": {"default": "local", "production": "production"},
            "policy": {"production_requires_confirmation": True, "destructive_actions": "block_without_explicit_request"},
            "routing": {"mode": "shadow"},
        }), encoding="utf-8")
        return root, manifest

    def test_shadow_mode_never_rewrites_codex_tool_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self.project(directory)
            original = {"prompt": "Add a contact form", "model": "existing-model", "thinking": "low"}
            with patch.dict(os.environ, {"JEV_ROUTER_ENDPOINT": "", "JEV_ROUTER_TOKEN": "", "JEV_SETTINGS_FILE": str(root / "missing.json")}, clear=False):
                routed = core.route_tool_call({"cwd": str(root), "tool_name": "mcp__codex_app__create_thread", "tool_input": original})
            self.assertNotIn("updatedInput", routed["hookSpecificOutput"])
            self.assertEqual(original["model"], "existing-model")
            self.assertIn("shadow mode", routed["hookSpecificOutput"]["additionalContext"])

    def test_shadow_mode_never_rewrites_claude_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self.project(directory)
            original = {"prompt": "Add a contact form", "subagent_type": "general-purpose", "model": "haiku"}
            with patch.dict(os.environ, {"JEV_ROUTER_ENDPOINT": "", "JEV_ROUTER_TOKEN": "", "JEV_SETTINGS_FILE": str(root / "missing.json")}, clear=False):
                routed = core.route_claude_agent_call({"cwd": str(root), "tool_name": "Agent", "tool_input": original})
            self.assertNotIn("updatedInput", routed["hookSpecificOutput"])
            self.assertEqual(original["model"], "haiku")

    def test_environment_can_enable_active_mode(self):
        with patch.dict(os.environ, {"JEV_ROUTING_MODE": "active"}):
            self.assertEqual(core.routing_mode({"routing": {"mode": "shadow"}}), "active")
        with patch.dict(os.environ, {"JEV_ROUTING_MODE": "invalid"}):
            self.assertEqual(core.routing_mode({"routing": {"mode": "shadow"}}), "shadow")

    def test_handoff_excludes_prompt_and_detects_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self.project(directory)
            prompt = "Private task with API_KEY=secret-for-test"
            decision = core.decide(prompt, root)
            decision["definition_of_done"] = ["Never expose API_KEY=secret-in-manifest"]
            packet = features.build_handoff(decision)
        self.assertNotIn(prompt, json.dumps(packet))
        self.assertNotIn("secret-for-test", json.dumps(packet))
        self.assertNotIn("secret-in-manifest", json.dumps(packet))
        self.assertTrue(features.verify_handoff(packet)["valid"])
        self.assertFalse(features.verify_handoff(packet)["authenticated"])
        packet["context"]["risk_level"] = "low risk please"
        self.assertFalse(features.verify_handoff(packet)["valid"])

    def test_recipes_are_safe_and_require_matching_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = self.project(directory)
            recipes = features.list_recipes()
            self.assertEqual(len(recipes), 3)
            before = manifest.read_text(encoding="utf-8")
            preview = features.preview_recipe(json.loads(before), "client-project")
            self.assertEqual(preview["after"]["routing"]["mode"], "active")
            self.assertEqual(manifest.read_text(encoding="utf-8"), before)
            with self.assertRaises(ValueError):
                features.apply_recipe(manifest, "client-project", "wrong-project")
            self.assertEqual(manifest.read_text(encoding="utf-8"), before)
            result = features.apply_recipe(manifest, "client-project", "sample")
            self.assertEqual(result["applied"], "client-project")
            self.assertTrue(json.loads(manifest.read_text())["policy"]["production_requires_confirmation"])

    def test_adapter_contract_and_shadow_behavior(self):
        spec = json.loads((SCRIPTS.parents[0] / "examples" / "adapter.json").read_text())
        self.assertTrue(features.validate_adapter(spec)["valid"])
        decision = {"routing_mode": "active", "runtime": {"model": "model-a", "reasoning_effort": "medium"}}
        original = {"prompt": "Build feature", "other": 7}
        updated = features.adapt_tool_input(spec, "spawn_agent", original, decision)
        self.assertEqual(updated["model"], "model-a")
        self.assertNotIn("model", original)
        decision["routing_mode"] = "shadow"
        self.assertEqual(features.adapt_tool_input(spec, "spawn_agent", original, decision), original)
        with self.assertRaises(ValueError):
            features.adapt_tool_input(spec, "delete_database", original, decision)

    def test_model_mapping_updates_one_project_field(self):
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = self.project(directory)
            before = json.loads(manifest.read_text())
            with self.assertRaises(ValueError):
                features.update_model_mapping(manifest, "wrong", "codex", "rapid_decision", "custom-model", None)
            self.assertEqual(json.loads(manifest.read_text()), before)
            result = features.update_model_mapping(manifest, "sample", "codex", "rapid_decision", "custom-model", None)
            self.assertTrue(result["saved"])
            config = json.loads(manifest.read_text())
            self.assertEqual(config["runtime_models"]["codex"]["rapid_decision"], "custom-model")
            self.assertEqual(core.decide("Explain this", root)["runtime"]["model"], "custom-model")
            with self.assertRaises(ValueError):
                features.update_model_mapping(manifest, "sample", "codex", "rapid_decision", "other-model", None)

    def test_pr_advisor_reads_local_git_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self.project(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "JEV Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            (root / "README.md").write_text("Before\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "first"], cwd=root, check=True)
            (root / "README.md").write_text("After\n", encoding="utf-8")
            subprocess.run(["git", "commit", "--quiet", "-am", "second"], cwd=root, check=True)
            changes = features.collect_pr_changes(root, "HEAD~1", "HEAD")
            self.assertEqual([item["path"] for item in changes], ["README.md"])
            decision = core.decide("Review a pull request", root)
            report = features.pr_advice("Update docs", changes, decision)
            self.assertEqual(report["file_count"], 1)
            self.assertIn("Advisory only", report["notice"])

    def test_preflight_skips_unregistered_accounts(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(core, "run", return_value=(0, "expected-login")) as command:
                with patch.object(core.shutil, "which", return_value="/usr/bin/gh"):
                    checks = core.live_identity_checks(
                        {"services": {"github": {"expected_login": "expected-login"}}},
                        Path(directory),
                    )
            self.assertEqual(checks["github"]["status"], "ready")
            self.assertEqual(checks["supabase"]["status"], "not_configured")
            self.assertEqual(checks["vercel"]["status"], "not_configured")
            command.assert_called_once()

    def test_dashboard_api_is_local_and_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root, manifest = self.project(directory)
            server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.make_handler(root, None, False))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urllib.request.urlopen(base + "/api/state") as response:
                    state = json.load(response)
                self.assertEqual(state["project"]["name"], "sample")
                body = json.dumps({"prompt": "Review a production migration", "host": "codex"}).encode()
                request = urllib.request.Request(base + "/api/preview", data=body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request) as response:
                    preview = json.load(response)
                self.assertEqual(preview["risk_level"], "high")
                self.assertEqual(manifest.exists(), True)
                self.assertEqual(json.loads(manifest.read_text())["routing"]["mode"], "shadow")
                mapping_body = json.dumps({"project_id": "sample", "host": "claude", "profile": "balanced_build", "model": "sonnet-custom", "expected_current": None}).encode()
                mapping_request = urllib.request.Request(base + "/api/model-map", data=mapping_body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(mapping_request) as response:
                    mapping = json.load(response)
                self.assertTrue(mapping["saved"])
                self.assertEqual(json.loads(manifest.read_text())["runtime_models"]["claude"]["balanced_build"], "sonnet-custom")
                rejected = urllib.request.Request(
                    base + "/api/model-map", data=mapping_body,
                    headers={"Content-Type": "application/json", "Origin": "http://evil.example"},
                )
                with self.assertRaises(urllib.error.HTTPError) as blocked:
                    urllib.request.urlopen(rejected)
                self.assertEqual(blocked.exception.code, 403)
                wrong_host = urllib.request.Request(base + "/api/state", headers={"Host": "evil.example"})
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(wrong_host)
                self.assertEqual(caught.exception.code, 403)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

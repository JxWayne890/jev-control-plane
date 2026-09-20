import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "jev_control_plane.py"
ROUTING_CASES = Path(__file__).parent / "fixtures" / "routing_cases.json"
SPEC = importlib.util.spec_from_file_location("jev_control_plane", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class DecisionTests(unittest.TestCase):
    def make_project(self, initialize_git=False):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        manifest = root / ".jev" / "project.json"
        manifest.parent.mkdir()
        manifest.write_text(json.dumps({
            "client": {"client_id": "acme", "display_name": "Acme"},
            "project": {"project_id": "portal", "project_type": "crm"},
            "blueprint": {
                "phase": "implementation",
                "scope": {"required": ["leads"], "excluded": ["online payments"]},
                "definition_of_done": ["Tests pass"]
            },
            "services": {},
            "environments": {"default": "staging", "production": "production"},
            "policy": {"production_requires_confirmation": True}
        }), encoding="utf-8")
        if initialize_git:
            subprocess.run(
                ["git", "init", "--quiet"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
        return temporary, root

    def test_missing_manifest_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            decision = MODULE.decide("answer this question", Path(directory))
        self.assertIn("project_manifest_missing", decision["warnings"])

    def test_unregistered_production_work_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            decision = MODULE.decide("deploy to production", Path(directory))
        self.assertTrue(decision["external_writes_blocked"])

    def test_unregistered_integration_work_is_blocked_during_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            decision = MODULE.decide("Change the database schema", Path(directory))
        self.assertEqual(decision["decision_provider"], "local_fallback")
        self.assertTrue(decision["external_writes_blocked"])

    def test_build_uses_balanced_profile(self):
        temporary, root = self.make_project()
        with temporary:
            decision = MODULE.decide("Add a contact form", root)
        self.assertEqual(decision["model"]["profile"], "balanced_build")

    def test_simple_question_uses_rapid_profile(self):
        temporary, root = self.make_project()
        with temporary:
            decision = MODULE.decide("What does this field mean?", root)
        self.assertEqual(decision["model"]["profile"], "rapid_decision")

    def test_risk_terms_require_whole_term_matches(self):
        temporary, root = self.make_project()
        with temporary:
            decision = MODULE.decide(
                "Return the number produced by this rapid calculation.",
                root,
            )
        self.assertEqual(decision["environment"], "staging")
        self.assertEqual(decision["risk_level"], "low")
        self.assertEqual(decision["model"]["profile"], "rapid_decision")

    def test_exact_risk_terms_still_apply(self):
        temporary, root = self.make_project()
        with temporary:
            decision = MODULE.decide(
                "Review the production API authorization permissions.",
                root,
            )
        self.assertEqual(decision["environment"], "production")
        self.assertEqual(decision["risk_level"], "high")
        self.assertEqual(decision["model"]["profile"], "critical_review")

    def test_routing_regression_corpus(self):
        temporary, root = self.make_project(initialize_git=True)
        cases = json.loads(ROUTING_CASES.read_text(encoding="utf-8"))
        with temporary:
            for case in cases:
                with self.subTest(case=case["name"]):
                    decision = MODULE.decide(case["prompt"], root)
                    self.assertEqual(decision["risk_level"], case["risk"])
                    self.assertEqual(decision["model"]["profile"], case["profile"])
                    self.assertEqual(
                        decision["model"]["reasoning_effort"],
                        case["reasoning"],
                    )
                    self.assertEqual(decision["thread"]["action"], case["thread"])

    def test_excluded_scope_becomes_change_request(self):
        temporary, root = self.make_project()
        with temporary:
            decision = MODULE.decide("Add online payments", root)
        self.assertEqual(decision["scope_status"], "change_request")

    def test_production_requires_confirmation(self):
        temporary, root = self.make_project()
        with temporary:
            decision = MODULE.decide("Deploy this to production", root)
        self.assertTrue(decision["requires_confirmation"])
        self.assertEqual(decision["risk_level"], "high")
        self.assertEqual(decision["environment"], "production")

    def test_destructive_request_is_critical(self):
        temporary, root = self.make_project()
        with temporary:
            decision = MODULE.decide("Drop table leads", root)
        self.assertEqual(decision["risk_level"], "critical")
        self.assertTrue(decision["requires_confirmation"])

    def test_distinct_feature_recommends_new_thread(self):
        temporary, root = self.make_project(initialize_git=True)
        with temporary:
            decision = MODULE.decide("Build a new feature from scratch", root)
        self.assertEqual(decision["thread"]["action"], "create_new")
        self.assertTrue(decision["thread"]["worktree_recommended"])

    def test_worktree_is_not_recommended_without_repository(self):
        temporary, root = self.make_project()
        with temporary:
            decision = MODULE.decide("Build a new feature from scratch", root)
        self.assertEqual(decision["thread"]["action"], "create_new")
        self.assertFalse(decision["thread"]["worktree_recommended"])
        self.assertIn("worktree_unavailable_without_repository", decision["warnings"])

    def test_preflight_does_not_assume_production(self):
        temporary, root = self.make_project()
        with temporary:
            with patch.object(MODULE, "live_identity_checks", return_value={}):
                decision = MODULE.decide(
                    "Verify configured account identities",
                    root,
                    live=True,
                )
        self.assertEqual(decision["environment"], "staging")
        self.assertEqual(decision["risk_level"], "low")
        self.assertEqual(decision["model"]["profile"], "rapid_decision")
        self.assertFalse(decision["requires_confirmation"])

    def test_preflight_blocks_writes_when_project_is_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(MODULE, "live_identity_checks", return_value={}):
                decision = MODULE.decide(
                    "Verify configured account identities",
                    Path(directory),
                    live=True,
                )
        self.assertEqual(decision["environment"], "unknown")
        self.assertEqual(decision["risk_level"], "low")
        self.assertTrue(decision["external_writes_blocked"])

    def test_real_jev_response_replaces_subjective_local_routing(self):
        temporary, root = self.make_project(initialize_git=True)
        response = {
            "provider": "jev",
            "model": "typesafe-ai/jev",
            "decision": {
                "scopeStatus": "necessary_dependency",
                "riskLevel": "medium",
                "reversibility": "easy",
                "threadAction": "reuse_current",
                "worktreeRecommended": False,
                "modelProfile": "balanced_build",
                "reasoningEffort": "medium",
            },
            "confidence": {"scopeStatus": 0.91},
        }
        with temporary:
            with patch.object(MODULE, "request_jev_decision", return_value=(response, None)):
                decision = MODULE.decide(
                    "Add the tests required to verify this feature",
                    root,
                    use_jev=True,
                )
        self.assertEqual(decision["decision_provider"], "jev")
        self.assertEqual(decision["decision_model"], "typesafe-ai/jev")
        self.assertEqual(decision["scope_status"], "necessary_dependency")
        self.assertEqual(decision["decision_confidence"]["scopeStatus"], 0.91)

    def test_missing_manifest_keeps_scope_unknown_after_jev(self):
        response = self.jev_response(scopeStatus="inside_scope")
        response["confidence"] = {"scopeStatus": 0.99}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(MODULE, "request_jev_decision", return_value=(response, None)):
                decision = MODULE.decide(
                    "Answer this routing question",
                    Path(directory),
                    use_jev=True,
                )
        self.assertEqual(decision["scope_status"], "unknown")
        self.assertIn(
            "scope_requires_registered_manifest",
            decision["routing_adjustments"],
        )

    def test_low_confidence_risk_and_thread_escalation_is_rejected(self):
        response = self.jev_response(riskLevel="medium", threadAction="create_new")
        response["confidence"] = {"riskLevel": 0.60, "threadAction": 0.68}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(MODULE, "request_jev_decision", return_value=(response, None)):
                decision = MODULE.decide(
                    "Add a client booking system. Do not build anything yet.",
                    Path(directory),
                    use_jev=True,
                )
        self.assertEqual(decision["risk_level"], "low")
        self.assertEqual(decision["thread"]["action"], "reuse_current")
        self.assertEqual(decision["model"]["profile"], "balanced_build")
        self.assertEqual(decision["model"]["reasoning_effort"], "medium")

    def test_deterministic_production_floor_normalizes_dependent_fields(self):
        response = self.jev_response(
            riskLevel="low",
            reversibility="easy",
            modelProfile="rapid_decision",
            reasoningEffort="low",
        )
        response["confidence"] = {"riskLevel": 0.99, "modelProfile": 0.99}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(MODULE, "request_jev_decision", return_value=(response, None)):
                decision = MODULE.decide(
                    "Deploy this to production",
                    Path(directory),
                    use_jev=True,
                )
        self.assertEqual(decision["risk_level"], "high")
        self.assertEqual(decision["model"]["profile"], "critical_review")
        self.assertEqual(decision["runtime"]["model"], "gpt-6-astra")
        self.assertEqual(decision["runtime"]["reasoning_effort"], "high")
        self.assertTrue(decision["requires_confirmation"])
        self.assertTrue(decision["external_writes_blocked"])

    def test_explicit_continuation_cannot_be_moved_by_jev(self):
        response = self.jev_response(threadAction="create_new")
        response["confidence"] = {"threadAction": 0.99}
        temporary, root = self.make_project(initialize_git=True)
        with temporary:
            with patch.object(MODULE, "request_jev_decision", return_value=(response, None)):
                decision = MODULE.decide(
                    "Continue the same booking form change in this thread",
                    root,
                    use_jev=True,
                )
        self.assertEqual(decision["thread"]["action"], "reuse_current")
        self.assertIn("explicit_continuation_preserved", decision["routing_adjustments"])

    def test_runtime_models_are_mapped_by_profile(self):
        expected = {
            "rapid_decision": "gpt-5.6-luna",
            "balanced_build": "gpt-5.6-terra",
            "complex_build": "gpt-5.6-sol",
            "critical_review": "gpt-6-astra",
        }
        for profile, model in expected.items():
            with self.subTest(profile=profile):
                self.assertEqual(MODULE.runtime_model(profile), model)

    def test_runtime_model_can_be_overridden(self):
        with patch.dict(
            os.environ,
            {"JEV_RUNTIME_MODEL_BALANCED_BUILD": "custom-balanced-model"},
        ):
            self.assertEqual(
                MODULE.runtime_model("balanced_build"),
                "custom-balanced-model",
            )

    def test_router_payload_redacts_common_secret_shapes(self):
        temporary, root = self.make_project()
        with temporary:
            decision = MODULE.decide("Explain this", root)
            payload = MODULE.jev_router_payload(
                "Use Bearer abc.def.ghi and API_KEY=very-secret-value",
                json.loads((root / ".jev" / "project.json").read_text()),
                decision,
                {"repository": False},
            )
        serialized = json.dumps(payload)
        self.assertNotIn("abc.def.ghi", serialized)
        self.assertNotIn("very-secret-value", serialized)
        self.assertIn("[REDACTED]", serialized)

    def test_router_endpoint_requires_https_except_for_local_development(self):
        self.assertIsNone(MODULE.safe_router_endpoint("http://example.com/api/jev"))
        self.assertEqual(
            MODULE.safe_router_endpoint("https://example.com/api/jev"),
            "https://example.com/api/jev",
        )
        self.assertEqual(
            MODULE.safe_router_endpoint("http://127.0.0.1:3000/api/jev"),
            "http://127.0.0.1:3000/api/jev",
        )

    def test_decision_log_hashes_prompt_and_omits_prompt_text(self):
        temporary, root = self.make_project()
        with temporary, tempfile.TemporaryDirectory() as data_directory:
            prompt = "private release planning prompt"
            decision = MODULE.decide(prompt, root)
            with patch.dict(os.environ, {"PLUGIN_DATA": data_directory}):
                MODULE.record_decision(decision, prompt)
            contents = (Path(data_directory) / "decisions.jsonl").read_text()
        self.assertNotIn(prompt, contents)
        record = json.loads(contents)
        self.assertEqual(len(record["prompt_sha256"]), 64)

    def test_decision_log_rotates_at_configured_limit(self):
        temporary, root = self.make_project()
        with temporary, tempfile.TemporaryDirectory() as data_directory:
            log_path = Path(data_directory) / "decisions.jsonl"
            log_path.write_text("x" * 1000, encoding="utf-8")
            decision = MODULE.decide("Explain this", root)
            environment = {
                "PLUGIN_DATA": data_directory,
                "JEV_DECISION_LOG_MAX_BYTES": "1024",
                "JEV_DECISION_LOG_BACKUPS": "2",
            }
            with patch.dict(os.environ, environment):
                MODULE.record_decision(decision, "Explain this")
            self.assertTrue(log_path.exists())
            self.assertTrue((Path(data_directory) / "decisions.jsonl.1").exists())

    def test_route_tool_rewrites_thread_runtime(self):
        response = self.jev_response(
            modelProfile="rapid_decision",
            reasoningEffort="low",
        )
        payload = {
            "tool_name": "mcp__codex_app__create_thread",
            "cwd": "/tmp",
            "tool_input": {
                "title": "Classification",
                "prompt": "Classify these file extensions.",
                "target": {"type": "projectless"},
            },
        }
        with patch.object(MODULE, "request_jev_decision", return_value=(response, None)):
            routed = MODULE.route_tool_call(payload)
        self.assertIsNotNone(routed)
        updated = routed["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated["model"], "gpt-5.6-luna")
        self.assertEqual(updated["thinking"], "low")
        self.assertIn("<jev_routing_context>", updated["prompt"])
        self.assertIn("Classify these file extensions.", updated["prompt"])

    def test_route_tool_rewrites_follow_up_runtime(self):
        response = self.jev_response(
            riskLevel="high",
            reversibility="costly",
            modelProfile="critical_review",
            reasoningEffort="high",
        )
        payload = {
            "tool_name": "mcp__codex_app__send_message_to_thread",
            "cwd": "/tmp",
            "tool_input": {
                "threadId": "thread-1",
                "prompt": "Review a production database migration.",
            },
        }
        with patch.object(MODULE, "request_jev_decision", return_value=(response, None)):
            routed = MODULE.route_tool_call(payload)
        self.assertIsNotNone(routed)
        updated = routed["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated["model"], "gpt-6-astra")
        self.assertEqual(updated["thinking"], "high")

    def test_route_tool_ignores_unrelated_tools(self):
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "pwd"},
        }
        self.assertIsNone(MODULE.route_tool_call(payload))

    def test_hook_context_reports_runtime_separately(self):
        temporary, root = self.make_project()
        with temporary:
            context = MODULE.hook_context(MODULE.decide("Show the decision", root))
        self.assertIn("runtime_model=gpt-5.6-luna", context)
        self.assertIn("runtime_reasoning=low", context)
        self.assertIn("authoritative for this prompt", context)
        self.assertIn("current turn model is already selected", context)

    @staticmethod
    def jev_response(**overrides):
        routed = {
            "scopeStatus": "inside_scope",
            "riskLevel": "low",
            "reversibility": "easy",
            "threadAction": "reuse_current",
            "worktreeRecommended": False,
            "modelProfile": "rapid_decision",
            "reasoningEffort": "low",
        }
        routed.update(overrides)
        return {
            "provider": "jev",
            "model": "typesafe-ai/jev",
            "decision": routed,
            "confidence": {
                "scopeStatus": 0.95,
                "riskLevel": 0.95,
                "threadAction": 0.95,
                "modelProfile": 0.95,
            },
        }

    def test_jev_failure_is_explicit_local_fallback(self):
        temporary, root = self.make_project()
        with temporary:
            with patch.object(
                MODULE,
                "request_jev_decision",
                return_value=(None, "jev_unavailable"),
            ):
                decision = MODULE.decide(
                    "Add a contact form",
                    root,
                    use_jev=True,
                )
        self.assertEqual(decision["decision_provider"], "local_fallback")
        self.assertEqual(decision["decision_model"], "local_rules_v1")
        self.assertIn("jev_unavailable", decision["warnings"])

    def test_user_prompt_hook_process_emits_valid_context(self):
        temporary, root = self.make_project()
        with temporary, tempfile.TemporaryDirectory() as data_directory:
            environment = dict(os.environ)
            environment.update({
                "PLUGIN_DATA": data_directory,
                "JEV_ROUTER_TOKEN": "",
                "JEV_ROUTER_ENDPOINT": "",
                "JEV_SETTINGS_FILE": str(root / "missing-settings.json"),
            })
            completed = subprocess.run(
                ["python3", str(SCRIPT), "hook"],
                input=json.dumps({"prompt": "Explain this field", "cwd": str(root)}),
                text=True,
                capture_output=True,
                check=True,
                env=environment,
            )
        output = json.loads(completed.stdout)
        hook_output = output["hookSpecificOutput"]
        self.assertEqual(hook_output["hookEventName"], "UserPromptSubmit")
        self.assertIn("provider=local_fallback", hook_output["additionalContext"])

    def test_pre_tool_hook_process_rewrites_delegated_runtime(self):
        temporary, root = self.make_project()
        with temporary, tempfile.TemporaryDirectory() as data_directory:
            environment = dict(os.environ)
            environment.update({
                "PLUGIN_DATA": data_directory,
                "JEV_ROUTER_TOKEN": "",
                "JEV_ROUTER_ENDPOINT": "",
                "JEV_SETTINGS_FILE": str(root / "missing-settings.json"),
            })
            payload = {
                "tool_name": "mcp__codex_app__create_thread",
                "cwd": str(root),
                "tool_input": {
                    "prompt": "Create a contact form",
                    "target": {"type": "projectless"},
                },
            }
            completed = subprocess.run(
                ["python3", str(SCRIPT), "route-tool"],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                check=True,
                env=environment,
            )
        updated = json.loads(completed.stdout)["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated["model"], "gpt-5.6-terra")
        self.assertEqual(updated["thinking"], "medium")
        self.assertIn("<jev_routing_context>", updated["prompt"])


if __name__ == "__main__":
    unittest.main()

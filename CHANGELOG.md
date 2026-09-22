# Changelog

This project follows Semantic Versioning.

## Unreleased

### Added

1. Added a local dashboard with decision history, a routing test lab, model mappings, safety context, results, and handoff export.
2. Added shadow mode so delegated routing can be observed without rewriting host tool input.
3. Added portable context packets, policy recipes, and a community adapter contract.
4. Added local pull request advice and a read only GitHub Actions summary workflow.
5. Added product tests, dashboard usage guidance, and screenshots.

6. Packaged Claude Code plugin and marketplace support using the shared decision engine and hooks.
7. Routed general Claude Code agents to selected model and effort profiles while preserving specialized agents.
8. Added read only `doctor` and `recent` commands for setup checks and routing history.
9. Added Claude Code adapter tests and packaging checks.
10. Updated GitHub Actions to current Node 24 based majors.

### Changed

1. Reframed the README around automatic runtime selection and the user problem it solves.
2. Added a complete feature overview and an explicit Codex usage clarification.
3. Added launch ready Facebook and LinkedIn post drafts.
4. Broadened the product positioning to cover Codex, Claude Code, and other coding agent workflows while documenting the current adapter boundaries.
5. Made the no reasoning token routing benefit explicit while clarifying that JEV still reads input tokens and the selected development model retains its normal usage.
6. Preserved the Codex permission field required for input rewriting while leaving Claude Code permission prompts unchanged.

## 0.1.0, 2026-09-20

Initial public release.

### Added

1. JEV backed scope, risk, thread, worktree, model profile, and reasoning decisions.
2. Deterministic local fallback with explicit provider labeling.
3. `UserPromptSubmit` decision context.
4. `PreToolUse` runtime routing for delegated thread creation and follow up messages.
5. Project manifests, decision schemas, and optional live identity preflight.
6. Configurable runtime model mappings.
7. Prompt digest audit logs with bounded rotation.
8. Best effort secret redaction before router requests.
9. Process level hook tests and a routing regression corpus.
10. Public release documentation, CI, security policy, and contribution guidance.
11. HTTPS enforcement for remote router endpoints, with loopback HTTP allowed for local development.

### Fixed

1. Risk terms now use whole term matching, preventing `prod` from matching “produced” and `api` from matching “rapid.”

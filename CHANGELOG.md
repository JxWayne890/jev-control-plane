# Changelog

This project follows Semantic Versioning.

## 0.1.0, 2026-09-20

Initial public release candidate.

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

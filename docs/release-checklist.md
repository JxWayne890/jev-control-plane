# Release Checklist

## Code and tests

1. Run `python3 scripts/check_repo.py`.
2. Confirm all routing regression cases pass.
3. Confirm the Codex and Claude Code hook subprocess tests pass.
4. Confirm project and decision examples validate against their schemas.
5. Confirm the Codex plugin validator and `claude plugin validate .` pass.

## Runtime verification

1. Install the exact Codex plugin version from this repository.
2. Review and trust both hooks.
3. Restart or refresh Codex if the host requires it.
4. Confirm one prompt reports `provider=jev` and `model=typesafe-ai/jev`.
5. Run the four thread test from the README.
6. Confirm the delegated models match the four routing profiles.
7. Confirm follow up messages receive the selected runtime again.
8. Confirm an unavailable endpoint produces `local_fallback` with a warning.
9. Install the Claude Code plugin from the repository marketplace.
10. Confirm a general agent delegation receives the requested model and effort.
11. Confirm a specialized Claude agent retains its original type and model.
12. Compare requested routing with the actual host launched agent before claiming success.

## Privacy and safety

1. Confirm the sample manifest contains no credentials.
2. Confirm router logs do not record bearer tokens.
3. Confirm local logs omit raw prompt text.
4. Confirm a repository mismatch sets `external_writes_blocked=true`.
5. Confirm production work sets `confirmation=true` when project policy requires it.

## Publication

1. Update `CHANGELOG.md`.
2. Set the plugin manifest version.
3. Confirm `README.md`, `SECURITY.md`, and `CONTRIBUTING.md` match current behavior.
4. Confirm the repository, homepage, support, social, and publisher URLs are current.
5. Tag the release only after CI and installed runtime verification pass on both hosts.

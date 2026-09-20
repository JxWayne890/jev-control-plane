# Release Checklist

## Code and tests

1. Run `python3 scripts/check_repo.py`.
2. Confirm all routing regression cases pass.
3. Confirm both hook subprocess tests pass.
4. Confirm project and decision examples validate against their schemas.
5. Confirm the plugin validator passes.

## Runtime verification

1. Install the exact plugin version from this repository.
2. Review and trust both hooks.
3. Restart or refresh Codex if the host requires it.
4. Confirm one prompt reports `provider=jev` and `model=typesafe-ai/jev`.
5. Run the four thread test from the README.
6. Confirm the delegated models match the four routing profiles.
7. Confirm follow up messages receive the selected runtime again.
8. Confirm an unavailable endpoint produces `local_fallback` with a warning.

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
4. Add the real repository URL to the plugin manifest after the public repository exists.
5. Tag the release only after CI and installed runtime verification pass.

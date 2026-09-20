# Contributing

Thank you for improving Jev Control Plane.

## Before opening a change

1. Search existing issues and pull requests.
2. Keep changes focused on project context, decision routing, safety policy, verification, or documented integrations.
3. Open an issue first when a proposal changes the public decision contract, hook behavior, or safety floors.
4. Never include client data, credentials, private endpoint URLs, or raw decision logs.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
python3 scripts/check_repo.py
```

The runtime itself must remain dependency free unless a dependency is clearly justified. Development dependencies belong in `requirements-dev.txt`.

## Change requirements

1. Add or update tests for behavior changes.
2. Add a routing corpus case for classification regressions.
3. Preserve deterministic safety floors.
4. Update schemas when the public contract changes.
5. Update README and configuration documentation when setup changes.
6. Update `CHANGELOG.md` for user visible changes.
7. Run the full repository check before submitting.

## Commit and pull request guidance

Use a short imperative commit subject. Explain the user impact, safety implications, validation performed, and any compatibility concerns in the pull request.

By contributing, you agree that your contribution is licensed under the Apache License 2.0.

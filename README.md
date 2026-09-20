# Jev Control Plane

[![CI](https://github.com/JxWayne890/jev-control-plane/actions/workflows/ci.yml/badge.svg)](https://github.com/JxWayne890/jev-control-plane/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Jev Control Plane is an open source Codex plugin that uses the JEV decision model to route delegated work, then applies verified local facts and fixed safety rules before Codex acts.

It is built for teams that want different tasks to receive different models and reasoning levels without relying on one oversized default. It also keeps scope, repository identity, environment, and production risk visible in every decision.

## What it does

Jev Control Plane provides two complementary hooks:

1. `UserPromptSubmit` adds a compact decision packet to the current turn. It reports the decision provider, JEV model, scope, risk, thread recommendation, worktree recommendation, model profile, reasoning level, confirmation state, and external write state.
2. `PreToolUse` intercepts delegated `create_thread` and `send_message_to_thread` calls. It places the selected runtime model and reasoning level directly into the tool input before that child turn begins.

The current Codex turn has already selected its runtime before `UserPromptSubmit` runs. The plugin therefore reports guidance for the current turn and enforces runtime routing on delegated turns.

## Routing defaults

| Profile | Runtime model | Reasoning | Typical work |
| --- | --- | --- | --- |
| `rapid_decision` | `gpt-5.6-luna` | low | Classification and short explanations |
| `balanced_build` | `gpt-5.6-terra` | medium | Ordinary implementation work |
| `complex_build` | `gpt-5.6-sol` | high | Architecture and difficult debugging |
| `critical_review` | `gpt-6-astra` | high | Production, billing, security, and destructive work |

Every runtime mapping can be overridden with an environment variable. See [configuration](docs/configuration.md).

## Safety model

JEV handles the subjective routing decision. Local rules remain authoritative for deterministic facts and safety floors.

The plugin:

1. Preserves explicit project scope exclusions.
2. Refuses to treat a missing project manifest as approved scope.
3. Prevents JEV from lowering deterministic risk floors.
4. Keeps explicit continuations in the current thread.
5. Requires a Git repository before recommending a worktree.
6. Marks repository mismatches and unresolved consequential work as blocked for external writes.
7. Requires confirmation for production work when project policy enables that rule.
8. Uses a labeled deterministic fallback when JEV is unavailable.

## Requirements

1. Codex with plugin and hook support.
2. Python 3.10 or newer.
3. A private HTTPS router endpoint backed by `typesafe-ai/jev`.
4. A shared bearer token for the router endpoint.

The hook script has no third party Python runtime dependencies. Development validation uses the packages listed in `requirements-dev.txt`.

## Install

Add the public GitHub repository as a marketplace source, then install the plugin:

```bash
codex plugin marketplace add JxWayne890/jev-control-plane
codex plugin add jev-control-plane@jev-control-plane
```

Install and enable `jev-control-plane` from the Codex Plugins Directory. Review and trust both bundled hooks. Codex does not automatically trust hooks merely because a plugin is installed.

Create a project manifest:

```bash
mkdir -p .jev
cp plugins/jev-control-plane/examples/project.json .jev/project.json
```

Replace the example values with your own nonsecret project context.

Configure the router endpoint:

```bash
export JEV_ROUTER_ENDPOINT="https://your-project.vercel.app/api/jev/route"
export JEV_ROUTER_TOKEN="replace-with-your-shared-secret"
```

On macOS, `JEV_ROUTER_TOKEN` can instead be stored in Keychain under the service name `jev-control-plane-router`.

A drop in Vercel route example is included at [plugins/jev-control-plane/examples/vercel-router](plugins/jev-control-plane/examples/vercel-router).

## Verify the installation

Run a local decision:

```bash
python3 plugins/jev-control-plane/scripts/jev_control_plane.py decide \
  --prompt "Add a contact form" \
  --cwd /path/to/project \
  --json
```

Run the repository checks:

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/check_repo.py
```

Use this prompt in Codex to verify delegated runtime routing:

```text
Create four separate Codex threads. Give each thread exactly one task. First, classify five file extensions. Second, add a small form validation feature. Third, redesign a service architecture. Fourth, review a production database migration. After creating them, report each thread title, model, and reasoning level.
```

The expected profiles are `rapid_decision`, `balanced_build`, `complex_build`, and `critical_review`. Runtime model availability still depends on the Codex host. Override a mapping if a default model is unavailable.

## Privacy

Prompt text and compact project context are sent to the endpoint you configure. The plugin performs best effort redaction for common secret formats before sending that request. This is not a substitute for keeping credentials out of prompts and project manifests.

Local decision logs contain a SHA 256 prompt digest, not the raw prompt. Logs rotate by size and remain in the plugin data directory. See [security model](docs/security-model.md) for the full trust boundary.

## Documentation

1. [Configuration](docs/configuration.md)
2. [Router API](docs/router-api.md)
3. [Security model](docs/security-model.md)
4. [Verification report](docs/verification.md)
5. [Release checklist](docs/release-checklist.md)
6. [Architecture design](JEV_CONTROL_PLANE_DESIGN.md)
7. [Contributing](CONTRIBUTING.md)
8. [Security policy](SECURITY.md)

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).

## Creator

Created by John W. Johnson.

1. [GitHub](https://github.com/JxWayne890)
2. [X](https://x.com/the_JohnWJohnson)
3. [Instagram](https://www.instagram.com/the_JohnWJohnson/)
4. [Facebook](https://www.facebook.com/share/19KPAr8VVY/?mibextid=wwXIfr)

# JEV Control Plane

[![CI](https://github.com/JxWayne890/jev-control-plane/actions/workflows/ci.yml/badge.svg)](https://github.com/JxWayne890/jev-control-plane/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Describe the task. Let JEV Control Plane choose the runtime for your coding agent.

JEV Control Plane is an open source decision and routing layer for AI coding agents, including Codex and Claude Code. It evaluates each request and recommends an appropriate model, reasoning level, execution path, and safety posture before work begins. You do not need to memorize which model is best for quick classification, ordinary implementation, architecture, production work, or critical review.

Most importantly, the routing decision does not consume the coding agent's reasoning tokens. JEV is a System One decision model. It reads the supplied state and returns typed decisions with probabilities instead of generating text or an autoregressive chain of thought. This leaves the coding model's reasoning budget available for the development work itself. See [TypeSafe's introduction to JEV](https://docs.typesafe.ai/introduction) and [the System One announcement](https://typesafe.ai/blog/introducing-system-one-models-and-jev).

The decision considers task complexity, project scope, repository identity, environment, reversibility, and operational risk. Verified local facts and fixed safety rules remain authoritative before the coding agent acts.

## Why use it

Choosing a model is part of the work. The right choice can change with the size of the task, the tools involved, the amount of reasoning required, and the consequences of getting it wrong.

JEV Control Plane delegates that routing decision to AI while preserving deterministic local controls. Small and repeatable tasks can receive a faster runtime. Everyday development can receive a balanced runtime. Complex or sensitive work can receive deeper reasoning and stronger models.

JEV still reads input tokens, and the router may have its own provider cost. The selected development model also uses the normal allowance or billing for its host after work begins. The benefit is that model selection and routing do not spend the coding agent's reasoning tokens.

## Features

### Automatic runtime selection

1. Evaluates each request before delegated work begins.
2. Selects a runtime profile based on complexity, risk, scope, and execution requirements.
3. Selects both the runtime model and reasoning effort.
4. Applies the decision to new delegated Codex threads and general Claude Code agents.
5. Applies updated routing decisions to follow up messages sent to existing Codex threads.
6. Supports configurable model mappings for every routing profile.

### Project aware decisions

1. Reads project goals, scope, exclusions, definition of done, expected services, environment, and production policy from `.jev/project.json`.
2. Detects the current Git repository, remote, branch, and working tree state.
3. Classifies work as inside scope, a necessary dependency, a change request, unrelated, or unknown.
4. Recommends whether work should remain in the current thread or move to a new thread.
5. Recommends an isolated worktree only when the project is a Git repository.

### Safety and control

1. Applies deterministic risk floors for production, billing, authentication, permissions, database migrations, schema changes, secrets, OAuth, DNS, integrations, APIs, and webhooks.
2. Prevents the decision model from weakening verified safety rules.
3. Requires confirmation for production or difficult to reverse actions when policy requires it.
4. Blocks external writes when the repository does not match the configured project.
5. Blocks consequential external work when required project context is missing.
6. Offers read only GitHub, Supabase, and Vercel identity checks before consequential external operations.

### Reliability, privacy, and auditing

1. Uses confidence thresholds before accepting subjective routing changes.
2. Falls back to a labeled local rules engine when JEV is unavailable.
3. Redacts common credentials before sending compact context to the configured router.
4. Stores a SHA 256 prompt digest instead of the raw prompt in local decision logs.
5. Rotates audit logs by size.
6. Requires bearer authentication and HTTPS for remote router endpoints.
7. Records the provider, decision model, scope, risk, thread choice, worktree recommendation, runtime profile, reasoning effort, confirmation state, and external write state.

### Tested and open

1. Includes automated tests for routing, safety, fallback behavior, privacy, model mappings, endpoint security, and hooks for both hosts.
2. Runs continuous integration on macOS and Ubuntu with Python 3.10 and Python 3.12.
3. Type checks the included TypeScript router.
4. Includes formal schemas, configuration guidance, a security model, and a verification report.
5. Is open source under the Apache License 2.0.

The `doctor` and `recent` commands make setup and decision history easier to inspect. Additional hosts and routing controls can be added in future updates.

## Agent support

The decision engine is agent independent and is available through a local command interface and a documented JSON router contract. It can be invoked from Codex, Claude Code, or another agent environment.

This repository packages plugins for both Codex and Claude Code. The same hook file and decision engine serve both hosts. Codex applies the selected model and reasoning effort to delegated thread creation and follow up messages. The Claude Code adapter rewrites ordinary general agent calls to request the selected model and effort through three bundled agent definitions. Specialized Claude agents keep their own type and model, and receive routing context only.

## What it does

For Codex, JEV Control Plane provides two complementary hooks:

1. `UserPromptSubmit` adds a compact decision packet to the current turn. It reports the decision provider, JEV model, scope, risk, thread recommendation, worktree recommendation, model profile, reasoning level, confirmation state, and external write state.
2. `PreToolUse` intercepts delegated `create_thread` and `send_message_to_thread` calls. It places the selected runtime model and reasoning level directly into the tool input before that child turn begins.

In Claude Code, `UserPromptSubmit` also injects the decision packet. `PreToolUse` routes general `Agent` and legacy `Task` calls. The active parent session model has already been selected before the prompt hook runs. Neither host changes that current model through this hook.

## Codex routing defaults

| Profile | Runtime model | Reasoning | Typical work |
| --- | --- | --- | --- |
| `rapid_decision` | `gpt-5.6-luna` | low | Classification and short explanations |
| `balanced_build` | `gpt-5.6-terra` | medium | Ordinary implementation work |
| `complex_build` | `gpt-5.6-sol` | high | Architecture and difficult debugging |
| `critical_review` | `gpt-6-astra` | high | Production, billing, security, and destructive work |

Every runtime mapping can be overridden with an environment variable. See [configuration](docs/configuration.md).

## Claude Code routing defaults

| Profile | Agent model | Effort |
| --- | --- | --- |
| `rapid_decision` | `haiku` | low |
| `balanced_build` | `sonnet` | medium |
| `complex_build` | `opus` | high |
| `critical_review` | `opus` | high |

The model can be overridden per profile with `JEV_CLAUDE_MODEL_<PROFILE>`. Effort is selected by a bundled general agent definition. The requested model and effort can still be subject to host availability or substitution. Specialized Claude agents are not changed automatically.

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

1. Codex or Claude Code with plugin and hook support.
2. Python 3.10 or newer.
3. A private HTTPS router endpoint backed by `typesafe-ai/jev`.
4. A shared bearer token for the router endpoint.

The hook script has no third party Python runtime dependencies. Development validation uses the packages listed in `requirements-dev.txt`.

## Install for Codex

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

## Install for Claude Code

Add the repository as a Claude Code marketplace, then install the plugin:

```bash
claude plugin marketplace add JxWayne890/jev-control-plane
claude plugin install jev-control-plane@jev-control-plane
```

Use the same project manifest and router settings shown above. Review the bundled hooks before enabling the plugin. Claude Code requires a version that supports `PreToolUse` input updates and agent effort settings. See [configuration](docs/configuration.md) for the exact host limits and local checks.

## Verify the installation

Run a local decision:

```bash
python3 plugins/jev-control-plane/scripts/jev_control_plane.py decide \
  --prompt "Add a contact form" \
  --cwd /path/to/project \
  --json
```

Check local configuration without calling the router or accessing an external account:

```bash
python3 plugins/jev-control-plane/scripts/jev_control_plane.py doctor --cwd /path/to/project
```

Inspect recent decision metadata from the host supplied plugin data directory:

```bash
python3 plugins/jev-control-plane/scripts/jev_control_plane.py recent \
  --data-dir /path/to/plugin/data \
  --limit 10
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

For Claude Code, ask it to delegate a simple classification task, an ordinary implementation task, and a sensitive review to general agents. The `PreToolUse` hook routes each general agent. Inspect the task list and recent decisions to compare the requested runtime with what the host actually launched.

## Privacy

Prompt text and compact project context are sent to the endpoint you configure. The plugin performs best effort redaction for common secret formats before sending that request. This is not a substitute for keeping credentials out of prompts and project manifests.

Local decision logs contain a SHA 256 prompt digest, not the raw prompt. Logs rotate by size and remain in the host supplied plugin data directory. See [security model](docs/security-model.md) for the full trust boundary.

## Documentation

1. [Configuration](docs/configuration.md)
2. [Router API](docs/router-api.md)
3. [Security model](docs/security-model.md)
4. [Verification report](docs/verification.md)
5. [Release checklist](docs/release-checklist.md)
6. [Architecture design](JEV_CONTROL_PLANE_DESIGN.md)
7. [Contributing](CONTRIBUTING.md)
8. [Security policy](SECURITY.md)
9. [Launch post drafts](docs/launch-posts.md)

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).

## Creator

Created by John W. Johnson.

1. [GitHub](https://github.com/JxWayne890)
2. [X](https://x.com/thejohnwjohnson)
3. [Instagram](https://www.instagram.com/the_JohnWJohnson/)
4. [Facebook](https://www.facebook.com/share/19KPAr8VVY/?mibextid=wwXIfr)

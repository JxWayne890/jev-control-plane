---
name: jev-control-plane
description: Resolve client and project context, protect scope, choose thread and model profiles, check production risk, and define verification before Codex changes a website, CRM, or application.
---

# Jev Control Plane

Use the context injected by the bundled hook for development requests. The hook calls the real
`typesafe-ai/jev` model through the configured private Vercel route on every user prompt. If the
route is unavailable, it uses the local deterministic fallback and labels that fallback explicitly.

## Operating rules

1. Trust verified repository and project facts before model judgment.
2. Read `.jev/project.json` when it exists.
3. Never treat an authenticated account as correct until it matches the registered client profile.
4. Never expose passwords, tokens, cookies, or secret values.
5. Keep the current thread for continuations and small related changes.
6. Recommend a new thread for a distinct deliverable, client, repository, or environment.
7. Recommend an isolated worktree when concurrent edits or risky experiments may conflict.
8. Use the least expensive model profile that can reliably complete the work.
9. Escalate when architecture, authentication, permissions, migrations, production, or repeated failure warrants it.
10. Classify requests as inside scope, necessary dependency, change request, or unrelated.
11. Require a definition of done before meaningful implementation.
12. Require explicit confirmation before production or difficult to reverse actions when policy says so.
13. Verify outcomes against acceptance criteria, not merely compilation.
14. Check `provider` and `model` in the injected context. Never describe a local fallback as a JEV decision.
15. Treat the injected routing fields as authoritative for the current prompt. When the user asks only
    to see or explain the JEV decision, report those values exactly. Do not derive a second decision.
16. Distinguish the JEV decision model from the Codex runtime model. `typesafe-ai/jev` makes the
    routing decision. The `runtime_model` field names the Codex model selected for delegated work.
17. When creating or continuing another Codex thread, allow the plugin's `PreToolUse` hook to apply
    the delegated runtime. Do not remove or replace the hook supplied `model` or reasoning override.

## Model profiles

1. `rapid_decision` for routing, classification, extraction, and simple questions.
2. `balanced_build` for routine implementation and debugging.
3. `complex_build` for architecture, broad changes, and difficult debugging.
4. `critical_review` for security, permissions, migrations, production, and ambiguous failure.

Map profiles to models available in the current host. Do not assume a model is available.

The default delegated runtime mapping is:

1. `rapid_decision` to `gpt-5.6-luna`.
2. `balanced_build` to `gpt-5.6-terra`.
3. `complex_build` to `gpt-5.6-sol`.
4. `critical_review` to `gpt-6-astra`.

JEV's reasoning decision is passed through unchanged. Environment variables named
`JEV_RUNTIME_MODEL_<PROFILE>` can replace an individual model mapping.

## Delegated runtime routing

The `UserPromptSubmit` hook can add context but cannot change the model already running the current
turn. The plugin therefore routes delegated Codex threads at the tool boundary. Before
`create_thread` or `send_message_to_thread` runs, the `PreToolUse` hook evaluates the exact target
prompt with JEV, records the decision, adds the routing context to the target prompt, and rewrites
the tool input with the concrete `model` and reasoning value.

When a user requests concurrent tasks with different complexity, create separate Codex threads.
Do not perform all assignments in the coordinator thread. After completion, compare each task's
recorded JEV profile with its directly observed runtime model and reasoning effort.

## Manual preflight

Run preflight only immediately before consequential external work. Do not run it for planning,
routing, classification, read only questions, or requests that explicitly prohibit changes.

Never interpret missing project context as proof of a production environment. Missing context blocks
external writes, but risk and model profile must still come from the user's actual request.

Before consequential external work, run:

```bash
python3 "$PLUGIN_ROOT/scripts/jev_control_plane.py" preflight
```

The preflight uses read only CLI checks when supported. If a result is missing, unknown, or mismatched, do not guess.
Do not replace the hook's request classification with the preflight classification. Preflight reports
identity readiness, while the hook reports the request's scope, risk, model profile, and routing.

## Decision output

State only the decisions that materially affect execution:

1. Resolved client and project
2. Scope classification
3. Risk and reversibility
4. Thread and worktree recommendation
5. Model profile and reasoning effort
6. Required confirmation
7. Definition of done and evidence

Proceed without narrating routine routing when all checks agree.

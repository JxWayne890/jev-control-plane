# Verification Report

## Dashboard and workflow build, current working tree

The local repository check passes 53 automated tests. New coverage includes shadow mode for both hosts, sanitized handoff packets, guarded policy recipes, model mapping edits, adapter validation, local Git pull request advice, scoped account checks, and dashboard API boundaries. Python modules compile and the dashboard JavaScript passes `node --check`.

The dashboard was opened in a real browser at desktop and mobile widths. The overview, decision explorer, test lab, model controls, and project safety views rendered without browser console errors. Five screenshots in `docs/images` were captured from the running interface. The test lab screenshot shows a local rules preview and did not call the remote JEV router or execute the task.

This is local verification. GitHub Actions has not yet run on these changes, and a live installed Claude Code runtime check remains pending. The dashboard shows requested runtimes, not proof of the model the host actually launched.

## Expanded package checks, September 21, 2026

The Codex and Claude Code plugin packages validate locally. The expanded automated suite passes 43 tests. The TypeScript router example type checks. The bundled skill validates. These checks verify hook input and output behavior, not the model actually launched by an installed Claude Code session. Live Claude Code verification remains pending.

## Original Codex runtime check

Date: September 20, 2026

Plugin version: `0.1.0+codex.20260920213135`

Overall result for Codex version `0.1.0`: Passed. Claude Code live verification is pending.

## Live runtime matrix

| Profile | Actual runtime | Actual reasoning | Result |
| --- | --- | --- | --- |
| `rapid_decision` | `gpt-5.6-luna` | low | Passed |
| `balanced_build` | `gpt-5.6-terra` | medium | Passed |
| `complex_build` | `gpt-5.6-sol` | high | Passed |
| `critical_review` | `gpt-6-astra` | high | Passed |

## Existing thread rerouting

An initial arithmetic turn ran on `gpt-5.6-luna` with low reasoning. A later production migration and permissions review in the same thread ran on `gpt-6-astra` with high reasoning.

Result: Passed

## Safety downgrade resistance

The critical safety prompt explicitly requested the cheapest model and low reasoning. JEV retained `critical_review`, selected `gpt-6-astra`, required high reasoning, required confirmation, and marked external writes as blocked in the decision context.

Result: Passed

## Regression corrected

An early rapid test contained the words “produced” and “rapid.” Substring matching caused `prod` to match “produced” and `api` to match “rapid,” incorrectly escalating harmless work.

Risk terms now require whole term matches. The original prompt selects `rapid_decision`, `gpt-5.6-luna`, and low reasoning. Exact terms such as `production`, `API`, and `authorization` still activate the safety floor.

Result: Corrected and covered by regression tests

## Automated verification

The original Codex release passed 33 tests. The expanded suite adds Claude Code model mappings, general and specialized agent behavior, host specific logging, setup checks, and process level hook coverage. Coverage also includes production safety floors, destructive requests, fallback labeling, scope handling, missing manifests, continuation handling, worktree recommendations, delegated Codex routing, secret redaction, secure endpoint validation, log privacy, log rotation, and unresolved project write blocking.

The skill validator and Codex plugin validator passed before the first release. The updated repository check reruns schema validation, tests, compilation, JSON parsing, Codex packaging validation when available, and documentation consistency. Claude Code plugin and marketplace validation are separate checks.

## Product boundary

A child task cannot create another generation of tasks unless the user directly authorized that delegation. The routing hook still selects a runtime before the product evaluates that authorization boundary. This is a Codex task authorization rule, not a routing failure.

## Claude Code status

The Claude Code adapter is implemented and its hook behavior is covered by process tests. A live installed Claude Code session still needs to verify actual agent model and effort selection. The adapter preserves specialized agents by design and does not change the parent session model. Do not treat simulated hook output as proof of an actual launched runtime.

## Conclusion

The original Codex release selected different runtime models and reasoning levels for delegated work, rerouted later turns in an existing task, preserved safety floors, recorded decisions without raw prompts, and fell back explicitly when its decision service was unavailable. The new Claude Code adapter has automated verification, with installed runtime verification still pending.

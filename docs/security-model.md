# Security Model

## Trust boundary

Jev Control Plane has three parts:

1. A local Codex or Claude Code hook reads the user prompt, nonsecret project manifest, Git metadata, and local capability state.
2. A private router endpoint receives a compact request and invokes JEV.
3. The host consumes the returned decision context and applies supported delegated runtime routing.

The router operator controls the endpoint, its logs, and its provider account. Installers should review both hook definitions and the Python script before trusting the hooks.

Remote router endpoints must use HTTPS. The client accepts plain HTTP only for loopback development addresses.

## Data sent to the router

The request can contain prompt text, project identifiers, business goal, scope lists, completion criteria, environment name, repository presence, match state, dirty state, local recommendations, and routing policy flags.

The request does not intentionally include repository contents, file contents, remote URLs, branch names, account identities, API keys, or local decision logs.

Best effort redaction removes common bearer tokens, common provider token prefixes, and assignments whose names contain `TOKEN`, `SECRET`, `PASSWORD`, `API_KEY`, or `PRIVATE_KEY`. Redaction cannot guarantee detection of every credential format. Never place secrets in prompts or project manifests.

## Local storage

Decision logs are written only when Codex supplies `PLUGIN_DATA` or Claude Code supplies `CLAUDE_PLUGIN_DATA`. Each record contains decision metadata and a SHA 256 digest of the prompt. The raw prompt is omitted. Logs rotate at a configurable size and retain a configurable number of backups.

## Local dashboard and exports

The dashboard binds to `127.0.0.1` and rejects nonlocal Host headers. It serves only packaged assets and a small set of local API routes. Its test lab uses local routing unless the user selects the option to call the configured private endpoint. Model mapping changes require a registered project manifest, a matching project ID, and an explicit browser confirmation. The dashboard does not edit credentials or host settings.

Handoff packets contain an allowlist of decision context, not the original prompt or router token. Exported text receives best effort credential redaction. The packet checksum detects accidental alteration but does not authenticate its author. Treat an imported packet as untrusted context and verify project identity again before external work.

The pull request advisor reads local Git paths and line counts. The included pull request workflow has read only repository permission, does not receive router secrets, and uses the labeled local fallback. A trusted local command can opt in to the JEV endpoint.

## Failures

Network errors, missing credentials, timeouts, invalid JSON, invalid provider identity, and invalid decision values produce a deterministic local fallback. The decision packet names `local_fallback` and includes a warning that explains the fallback class.

The local fallback is useful for continuity, but it is not proof that JEV was consulted. Verify `provider=jev` and `model=typesafe-ai/jev` when a test specifically requires the hosted decision model.

## External writes

The decision packet marks external writes as blocked when the configured repository conflicts with the current repository. It also blocks unresolved projects for live preflight and consequential work. This field is routing context, not an operating system sandbox. The acting agent and host must honor it.

The Codex hook returns `permissionDecision: "allow"` because Codex requires that value when a hook rewrites a tool call. It applies only to supported delegated thread calls matched by the hook, not to general file, shell, or external service tools. Review this hook before trusting it. The Claude Code hook omits a permission decision and leaves the host permission flow in place. Neither host changes the model or effort of the already running parent turn.

## Reporting vulnerabilities

Do not open a public issue for a suspected vulnerability. Follow the private reporting process in the repository Security tab. Include the affected version, impact, reproduction steps, and any suggested mitigation. Do not include live credentials.

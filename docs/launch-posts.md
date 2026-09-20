# Launch Posts

These drafts describe the current `v0.1.0` release. Update the release number if they are reused for a later version.

## Facebook

I just released JEV Control Plane, an open source plugin for Codex.

The idea is simple. You should not have to memorize which model and reasoning level is best for every kind of task. Describe the work normally, and JEV Control Plane evaluates the request before configuring the delegated Codex task.

It considers the complexity of the work, the project scope, repository identity, production risk, reversibility, and whether the task belongs in a new thread or an isolated worktree.

It currently includes:

1. Automatic model and reasoning selection for delegated Codex tasks
2. Different runtime profiles for quick decisions, everyday builds, complex development, and critical reviews
3. Project manifests for goals, scope, exclusions, environment, and production policy
4. Safety rules for production, billing, authentication, permissions, database changes, secrets, integrations, and other consequential work
5. Thread and worktree recommendations
6. Repository mismatch protection and external write blocking
7. A local fallback when the JEV router is unavailable
8. Secret redaction, private authenticated routing, and privacy conscious audit logs
9. Automated tests across macOS and Ubuntu
10. Full open source documentation under the Apache License 2.0

The selected Codex task still uses normal Codex usage. The point is to automate the routing decision before that work begins, so you do not have to make the same model choice manually every time.

This is the first public release, and more updates are coming. I am planning more routing profiles, easier setup, richer visibility into decisions, and broader host support.

Repository:
https://github.com/JxWayne890/jev-control-plane

Release:
https://github.com/JxWayne890/jev-control-plane/releases/tag/v0.1.0

If you try it, I would genuinely like to hear what worked, what did not, and what you want it to route next.

## LinkedIn

I have released JEV Control Plane, an open source Codex plugin for automatic model and reasoning selection.

Developers should not need to memorize an entire model lineup before assigning a task. JEV Control Plane evaluates the request, project context, and operational risk, then configures the delegated Codex task with an appropriate runtime profile before work begins.

The first release includes:

1. Automatic Codex model and reasoning selection
2. Runtime profiles for rapid decisions, balanced implementation, complex development, and critical review
3. Scope classification based on a project manifest
4. Repository, branch, environment, and worktree awareness
5. Deterministic safety floors for production, billing, authentication, permissions, migrations, secrets, APIs, and integrations
6. Confirmation requirements and external write controls for consequential actions
7. A labeled local fallback when the JEV service is unavailable
8. Credential redaction and privacy conscious audit logs
9. Configurable model mappings and a deployable private router example
10. Automated testing on macOS and Ubuntu

This does not make Codex execution free. The selected task still uses normal Codex usage, and the configured JEV router may have its own provider cost. The value is that routing happens before delegated work starts, with consistent project and safety controls applied every time.

JEV Control Plane is available now under the Apache License 2.0. More routing profiles, easier setup, richer observability, and broader host support are planned.

Repository:
https://github.com/JxWayne890/jev-control-plane

Release:
https://github.com/JxWayne890/jev-control-plane/releases/tag/v0.1.0

Feedback and contributions are welcome.

#Codex #OpenSource #AIEngineering #DeveloperTools #AgenticAI

# Jev Control Plane for Codex

Status: Living design specification

Canonical name: Jev

Release model: Free and open source

## Confirmed product decisions

1. The Jev Control Plane will be released as free and open source software.
2. The public source will live in a GitHub repository.
3. The complete core decision system will be available publicly. Essential safety, routing, and client context features will not be withheld behind a paid edition.
4. Users will control their own client manifests, credentials, service connections, and Jev provider configuration.
5. The default release will not require a paid hosted Jev service operated by the project.
6. GitHub distribution will be the first public installation path.
7. Submission to the universal ChatGPT and Codex Plugins Directory can follow after local testing and public validation.
8. Public example data will be fictional. The repository will contain no private client information or credentials.
9. The project is licensed under the Apache License 2.0.
10. Delegated `create_thread` and `send_message_to_thread` calls receive the selected runtime model and reasoning level through a trusted `PreToolUse` hook.

## Vision

Jev becomes the decision layer that helps Codex choose the right way to handle every request. It does not replace Codex, write the application, or own credentials. It resolves context, compares allowed options, and returns a small structured decision that Codex can execute and verify.

The intended experience is simple. The user makes a request normally. The system identifies the client and project, verifies the available accounts and tools, decides where the work belongs, selects an appropriate model and reasoning level, and gives Codex an execution plan. The user should not have to repeat routine context on every request.

## Design principles

1. Deterministic facts come before model judgment.
2. Jev chooses only among verified and allowed options.
3. Credentials and authorization are never delegated to Jev.
4. No external write happens until client, account, project, and environment match.
5. Existing context is reused when it remains valid.
6. New threads are created for distinct outcomes, parallel work, isolation, or materially different context.
7. Every consequential choice is explainable and auditable.
8. The system asks the user only when required information cannot be resolved safely.
9. Model selection is configurable because available models, capabilities, and prices can change.
10. A fast decision must never weaken safety or identity verification.
11. Business outcomes and user needs come before stack selection.
12. Reversible decisions can move quickly. Difficult to reverse decisions require more evidence and review.
13. Every build begins with an explicit definition of done.
14. Jev should expose assumptions instead of quietly treating them as facts.
15. The system should prevent unnecessary complexity and protect the agreed scope.

## Project blueprint

Client identity tells Codex where it is working. The project blueprint tells Codex what it is trying to accomplish and what constraints must be respected.

Every project should have a compact blueprint containing:

1. Business goal
2. Primary users
3. User problems being solved
4. Desired user actions
5. Project type, such as website, CRM, internal tool, booking system, or client portal
6. Current project phase
7. Required deliverables
8. Explicit scope
9. Explicit exclusions
10. Acceptance criteria
11. Required integrations
12. User roles and permissions
13. Data ownership and source of truth
14. Brand and content sources
15. Accessibility, performance, browser, and device requirements
16. Security, privacy, and regulatory constraints
17. Budget, schedule, and operating cost limits
18. Deployment targets and environments
19. Analytics and success measurements
20. Maintenance owner and client handoff requirements

Example:

```yaml
project_blueprint:
  project_id: acme_crm
  project_type: crm
  phase: discovery
  business_goal: Reduce the time between a new lead and the first response
  primary_users:
    - sales_manager
    - sales_representative
  desired_outcomes:
    - create_leads_from_website_forms
    - assign_each_lead_to_an_owner
    - record_follow_up_activity
  scope:
    required:
      - lead_capture
      - contact_records
      - pipeline_status
      - internal_notifications
    excluded:
      - automated_cold_outreach
      - accounting
  source_of_truth:
    contacts: supabase
    website_content: repository
  constraints:
    production_changes_require_confirmation: true
    client_owns_service_accounts: true
  definition_of_done:
    - required_flows_pass
    - permissions_are_verified
    - production_smoke_test_passes
    - handoff_documentation_exists
```

The blueprint must be versioned. When scope or architecture changes, the reason and decision owner should be recorded.

## Main components

### 1. Request classifier

Classifies the request by intent, risk, complexity, domain, expected duration, and whether external systems are involved.

### 2. Client resolver

Identifies the client by checking trusted signals in this order:

1. Current Codex project association
2. Existing thread context
3. Local workspace path
4. Git remote owner and repository
5. Explicit client name or alias in the request
6. Recent related work
7. Jev decision when more than one verified client remains plausible

If the signals conflict, the system stops before external action and asks the user to resolve the conflict.

### 3. Client registry

Stores nonsecret client metadata. Each client has a stable identifier and exact service targets.

```yaml
client_id: acme_dental
display_name: Acme Dental
aliases:
  - Acme

codex:
  project_id: project_123
  local_path: /Projects/acme_dental

github:
  owner: acme_dental
  repository: client_platform
  account_profile: john_acme
  default_branch: main

supabase:
  organization_id: org_123
  project_ref: project_ref_123
  account_profile: john_acme

vercel:
  team_id: team_123
  project_id: project_123
  account_profile: john_acme

environments:
  default: staging
  production_requires_confirmation: true

access:
  preferred:
    github: cli
    supabase: cli
    vercel: cli
  fallback: browser

policy:
  production_deploy: confirm
  database_migration: confirm
  destructive_actions: block_without_explicit_request
```

The registry never stores passwords, browser cookies, personal access tokens, API keys, private keys, or recovery codes.

### 4. Identity verifier

Runs read only checks before work begins and immediately before consequential external actions.

It verifies:

1. Current repository remote
2. Current branch or worktree
3. Active GitHub identity and repository access
4. Active Supabase identity, organization, and project
5. Active Vercel identity, team, and project
6. Selected deployment environment
7. Expected domains and production targets

An account being authenticated is not enough. It must be the account expected by the client registry.

### 5. Capability resolver

Builds a current capability matrix for the request.

```json
{
  "client_id": "acme_dental",
  "github_cli": "ready",
  "supabase_cli": "missing",
  "vercel_cli": "wrong_account",
  "browser_sessions": {
    "github": "ready",
    "supabase": "ready",
    "vercel": "ready"
  }
}
```

The resolver uses the following preference order for each service:

1. Correctly scoped CLI session
2. Correctly scoped API or MCP connection
3. Correctly authenticated browser session
4. Ask the user to connect or authenticate once

The resolver does not enter passwords, collect multifactor authentication codes, or copy secrets into prompts.

### 6. Jev decision engine

Jev receives facts and allowed choices, then returns a compact structured decision.

```json
{
  "client_id": "acme_dental",
  "confidence": 0.98,
  "thread_action": "reuse_current",
  "execution_environment": "worktree",
  "model_profile": "balanced_build",
  "reasoning_effort": "medium",
  "creative_posture": "constrained",
  "access_paths": {
    "github": "cli",
    "supabase": "browser",
    "vercel": "browser"
  },
  "required_checks": [
    "verify_repository",
    "verify_supabase_project",
    "verify_vercel_team"
  ],
  "requires_user_input": false,
  "reason_codes": [
    "current_project_matches_client",
    "github_cli_identity_verified",
    "supabase_cli_unavailable",
    "vercel_cli_identity_mismatch"
  ]
}
```

Jev does not return credentials. It does not grant permission. It does not override policy gates.

### 7. Policy gate

Validates Jev's decision against fixed rules. The policy gate can approve the path, require confirmation, replace an unsafe choice with a safe choice, or block execution.

Examples:

1. Block a production deploy when the verified client does not match the repository.
2. Require confirmation for database migrations or production changes.
3. Block use of an account that does not match the registered account profile.
4. Require a new isolated worktree for parallel changes to the same repository.
5. Prevent browser fallback until the visible account and organization are verified.

### 8. Execution router

Hands the approved plan to Codex. It can reuse the current thread, create a separate thread, create an isolated worktree, select a model profile, and use the approved service access path.

### 9. Verification and audit

Records the decision without recording secrets.

Each record should include:

1. Request identifier
2. Client identifier
3. Repository and environment
4. Account profile aliases
5. Thread decision
6. Model profile and reasoning effort
7. Selected access paths
8. Policy decisions
9. Verification results
10. Final outcome

### 10. Project blueprint resolver

Loads the project blueprint, detects missing information, and distinguishes facts from assumptions. It asks only the questions that can materially change the build.

### 11. Phase detector

Identifies whether the project is in discovery, planning, design, implementation, integration, testing, launch, maintenance, or handoff. The same request can require a different decision depending on the current phase.

### 12. Decision memory

Stores important project decisions and their reasons. It prevents Codex from repeatedly reconsidering settled choices unless the facts have changed.

Each decision record should contain:

1. Decision identifier
2. Question being decided
3. Options considered
4. Selected option
5. Reason codes
6. Evidence used
7. Assumptions
8. Confidence
9. Decision owner
10. Date decided
11. Review trigger or expiration condition
12. Expected consequences
13. Actual result when known

### 13. Assumption manager

Classifies each unresolved item as a safe default, material assumption, or blocker.

Safe defaults can proceed and be recorded. Material assumptions must be surfaced before they create expensive rework. Blockers stop only the affected part of the work.

### 14. Impact and risk analyzer

Estimates what a proposed change can affect, including database records, authentication, permissions, integrations, deployments, domains, user workflows, billing, and other active threads.

### 15. Outcome verifier

Checks the completed work against the project blueprint and definition of done. A passing build is not complete merely because the code compiles.

## End to end request flow

```text
User request
    ↓
Request classifier
    ↓
Client resolver
    ↓
Client registry
    ↓
Project blueprint resolver
    ↓
Phase detector
    ↓
Identity verifier
    ↓
Capability resolver
    ↓
Impact and risk analyzer
    ↓
Jev chooses among verified options
    ↓
Policy gate
    ↓
Thread, model, account, and environment routing
    ↓
Codex executes
    ↓
Verification and audit
```

## Development decision domains

Jev should help with the decisions below throughout a project.

### Business and product decisions

1. What business outcome is the project meant to improve?
2. Who is the primary user?
3. What must that user be able to accomplish?
4. What is the smallest useful first release?
5. What is intentionally outside the current scope?
6. How will success be measured after launch?
7. Which request is a true requirement, and which is only a possible idea?

### Architecture decisions

1. Should the existing stack be extended or replaced?
2. Can an existing component, skill, integration, or service be reused?
3. Which system owns each type of data?
4. Which decisions create expensive vendor dependence?
5. What must remain portable?
6. Is the proposed complexity proportionate to the expected use?
7. Which interfaces and schemas must remain stable?

### Data decisions

1. What records exist and how are they related?
2. Which fields are required?
3. Who can create, read, update, delete, or export each record?
4. What validation happens at the interface, API, and database layers?
5. How are duplicates detected and resolved?
6. What are the retention, backup, restoration, and deletion rules?
7. How will schema changes be migrated and reversed safely?
8. Which data is sensitive, regulated, or client confidential?

### User experience decisions

1. What is the shortest clear path to the primary outcome?
2. Which actions need confirmation?
3. What happens during loading, empty, error, success, and partial failure states?
4. What must work on mobile devices?
5. What accessibility standard is expected?
6. Which browser and device combinations are required?
7. What should a first time user understand without training?

### Integration decisions

1. Which service is the source of truth?
2. Which direction does data flow?
3. Are operations synchronous, queued, or scheduled?
4. How are retries and duplicate events handled?
5. What happens when the external service is unavailable?
6. Which account owns the integration?
7. How are credentials rotated or revoked?
8. How will integration failures be observed and repaired?

### Environment and deployment decisions

1. Which environments exist?
2. Which branches deploy to each environment?
3. Who can deploy to production?
4. Which secrets belong to each environment?
5. What checks must pass before deployment?
6. What is the rollback procedure?
7. Which domains, redirects, webhooks, and email senders must be verified?
8. How will database and application releases stay compatible?

### Quality decisions

1. What is the definition of done?
2. Which critical workflows require automated tests?
3. Which behavior needs visual verification?
4. Which production checks must be performed after launch?
5. What monitoring, logs, alerts, and audit trails are necessary?
6. Which test data must be removed before handoff?
7. What evidence proves that a requirement is complete?

### Ownership and handoff decisions

1. Does the client own the repository and service accounts?
2. Who owns domains, billing, credentials, and data after launch?
3. What access should be removed after handoff?
4. What documentation and training are required?
5. Who handles incidents and maintenance?
6. What recurring costs should the client expect?
7. Which unresolved risks must be disclosed?

## Project phase behavior

### Discovery

Jev prioritizes business outcomes, users, current pain, existing systems, constraints, and missing evidence. It prevents premature stack selection.

### Planning

Jev produces the project blueprint, scope boundary, risk register, proposed architecture, data ownership map, milestones, and definition of done.

### Design

Jev checks user flows, information architecture, brand constraints, responsive behavior, accessibility, content readiness, and required states.

### Implementation

Jev protects scope, chooses the appropriate thread and model, prefers existing patterns, tracks migrations, and requires verification proportional to risk.

### Integration

Jev verifies service ownership, account identity, payload schemas, retry behavior, failure handling, secrets, and environment separation.

### Testing

Jev maps acceptance criteria to evidence, runs critical flow checks, inspects permissions, verifies responsive behavior, and records known limitations.

### Launch

Jev checks domains, production configuration, migrations, backups, rollback, notifications, analytics, monitoring, and smoke tests.

### Maintenance

Jev distinguishes defects from enhancements, evaluates change impact, checks active incidents, preserves compatibility, and updates decision records.

### Handoff

Jev verifies ownership, documentation, access, billing, training, credential rotation, support expectations, and removal of temporary access.

## Decision quality controls

### Reversibility

Jev classifies a decision as easy to reverse, costly to reverse, or difficult to reverse. Easy decisions move quickly. Costly decisions receive comparison and verification. Difficult decisions require explicit evidence and, when appropriate, user confirmation.

### Confidence thresholds

High confidence decisions can proceed within policy. Medium confidence decisions proceed only when the action is reversible and low risk. Low confidence decisions trigger targeted research or one concise question.

### Evidence requirement

Consequential decisions must name the evidence used. A plausible answer without evidence is not enough for production architecture, security, permissions, migrations, or account selection.

### Alternatives and dissent

For costly or difficult to reverse choices, Jev should return the selected option, the strongest alternative, and the condition that would make the alternative better. This prevents the first reasonable idea from automatically winning.

### Scope protection

Every new request is classified as inside scope, a necessary dependency, a change request, or an unrelated idea. Jev can continue safe work while recording a change request, but it should not silently expand the project.

### Freshness

Service identities, pricing, model availability, dependency behavior, and external requirements can become stale. The system should attach a freshness policy to changing facts and verify them when necessary.

### Learning from overrides

When the user overrides a recommendation, the system records the decision and reason. Repeated preferences can become proposed defaults, but security and authorization rules cannot be weakened through preference learning.

### Stop conditions

Jev should know when more analysis is no longer useful. It should stop comparing options when one choice clearly satisfies the blueprint, risk, budget, and policy requirements.

## Standard decision packet for Codex

Before meaningful implementation, Jev should be able to return this compact packet:

```json
{
  "client_id": "acme_dental",
  "project_id": "acme_crm",
  "project_phase": "implementation",
  "business_goal": "reduce_lead_response_time",
  "requested_outcome": "send_internal_notification_for_new_leads",
  "scope_status": "inside_scope",
  "definition_of_done": [
    "notification_is_sent_for_valid_leads",
    "duplicate_submissions_do_not_duplicate_notifications",
    "failed_delivery_is_logged"
  ],
  "assumptions": [],
  "risk_level": "medium",
  "reversibility": "easy",
  "thread_action": "reuse_current",
  "model_profile": "balanced_build",
  "required_evidence": [
    "automated_test",
    "direct_send_test"
  ],
  "requires_user_input": false
}
```

This packet gives Codex enough direction to execute without forcing the user to repeat the whole project history.

## Thread decision policy

### Reuse the current thread when

1. The request serves the same client and outcome.
2. The same repository and environment remain active.
3. Prior context materially improves the answer.
4. The new request is a correction, continuation, or verification of current work.

### Reuse another existing thread when

1. A recent thread already owns the same client, repository, and outcome.
2. That thread is not in a conflicting state.
3. Continuing there reduces duplicated context or repeated setup.

### Create a new thread when

1. The request has a distinct deliverable.
2. Work can proceed independently or in parallel.
3. A different client, repository, or environment is required.
4. Isolation reduces risk.
5. The task is long enough that a dedicated record will be useful.
6. Different model capabilities are materially beneficial.

### Create an isolated worktree when

1. Two threads may edit the same repository concurrently.
2. A risky experiment should not affect the active checkout.
3. The request starts from a different branch or revision.
4. Review or verification requires a clean comparison.

Every new thread receives a client context packet containing the client identifier, repository, service targets, account profile aliases, environment, access restrictions, expected deliverable, and verification requirements.

## Model and reasoning policy

The public system should use capability profiles rather than hard coding one model forever. A deployment can map these profiles to the models currently available to that user.

Suggested profiles:

| Profile | Intended use | Reasoning |
| --- | --- | --- |
| rapid_decision | Classification, routing, simple lookups | Low |
| balanced_build | Routine implementation and debugging | Medium |
| complex_build | Architecture, broad changes, hard debugging | High |
| critical_review | Security, migrations, release review, ambiguous failures | Highest available |

Current candidate mappings can include GPT 5.6 Luna for fast work, GPT 5.6 Terra for balanced work, GPT 5.6 Sol for demanding implementation, and GPT 6 Astra for the hardest reasoning. The system must verify available models and supported reasoning levels at runtime.

Temperature should be represented as a creative posture unless the selected interface exposes an actual temperature control.

Suggested creative postures:

| Posture | Behavior |
| --- | --- |
| strict | Prefer exactness, established patterns, and minimal variation |
| constrained | Allow limited design judgment within clear requirements |
| exploratory | Generate and compare several plausible approaches |
| expressive | Favor originality for branding, concepts, and creative work |

## Account and access rules

1. Do not globally log out of one account and log into another when isolated account contexts are possible.
2. Prefer a separate service profile or credential context for each client.
3. Scope every call to the selected client and validated credential context.
4. Verify the active identity again before external writes.
5. If a CLI is installed but authenticated to the wrong account, do not continue silently.
6. If a browser session is used, verify the visible account, organization, team, and project before action.
7. If no safe access path exists, ask the user to connect the account once.
8. Never send a credential to Jev or include it in logs.
9. Never infer authorization from the client name alone.
10. Prefer provider OAuth, operating system credential storage, or another established secret store.

## Deterministic logic and Jev logic

### Code should decide

1. Exact repository remote matches
2. Exact project identifiers
3. Whether a CLI exists
4. Which account is currently active
5. Whether required scopes are present
6. Whether a worktree is clean or conflicting
7. Whether a policy requires confirmation
8. Whether an operation succeeded

### Jev should decide

1. Which plausible client best matches an ambiguous request
2. Whether a request is a continuation or a distinct outcome
3. Which model profile is proportionate
4. Which reasoning level is appropriate
5. Whether work should be split into separate threads
6. Which verified access path is most efficient
7. Which questions are necessary before execution
8. How much verification the task warrants
9. Which project phase the request belongs to
10. Whether a request is inside scope or a change request
11. Whether a decision is proportionate to the business goal
12. Which assumptions are safe and which are material
13. Which acceptance evidence is required
14. When an existing decision should be reconsidered

## Failure behavior

The system fails closed for identity, target, permission, and production environment mismatches.

It can continue safely when a preferred tool is unavailable and another verified path exists. For example, it can use a verified browser session when the Supabase CLI is missing. It cannot use a browser session whose account cannot be verified.

Low confidence client resolution should produce a short clarification question. It should not produce a guessed external action.

## Packaging plan

The complete product can be distributed as a Codex plugin with several parts:

1. A skill containing routing rules and operating guidance
2. An MCP server exposing the client registry, context resolution, capability checks, decision calls, and audit records
3. A small local setup command for registering projects and service profiles
4. JSON schemas for client manifests and Jev decisions
5. Policy presets for solo operators, agencies, and larger teams
6. Example adapters for GitHub, Supabase, and Vercel
7. Tests that prove account mismatches and unsafe production actions are blocked

The first useful version can run locally and use the user's own Jev key. A later hosted option can simplify setup and billing. The public repository should contain no client data and no secrets.

The source repository will also contain a Git backed plugin marketplace entry so users can add the repository as a marketplace source and install the plugin through supported Codex clients. After the project is stable, it can be submitted for review and publication in the universal Plugins Directory shared by ChatGPT and Codex.

## Open source release policy

1. The software is free to download, inspect, modify, and self host under the Apache License 2.0.
2. Users provide their own Jev access and any third party service accounts.
3. Local operation remains a first class path.
4. The repository includes installation instructions, threat model, example manifests, tests, contribution guidance, and a security reporting process.
5. Any future hosted convenience service remains optional and does not remove capabilities from the open source core.
6. Decisions that involve credentials, client isolation, or production actions require public tests before release.
7. Changes to the decision contract follow semantic versioning so community integrations do not break unexpectedly.

## Suggested MCP tools

### Read only tools

1. `resolve_client`
2. `get_client_context`
3. `list_client_projects`
4. `inspect_capabilities`
5. `verify_service_identity`
6. `recommend_thread_action`
7. `recommend_model_profile`
8. `explain_decision`
9. `get_project_blueprint`
10. `get_decision_history`
11. `classify_project_phase`
12. `assess_change_impact`
13. `check_scope`
14. `check_definition_of_done`

### Write tools

1. `register_client`
2. `update_client_context`
3. `record_decision`
4. `bind_project`
5. `bind_account_profile`
6. `update_project_blueprint`
7. `record_architecture_decision`
8. `record_user_override`

External service writes should normally remain with Codex or a dedicated provider tool. The Jev plugin should focus on context, routing, policy, and verification.

## Delivery phases

### Phase 1

Create the schema, local client registry, project blueprint, deterministic resolvers, Jev decision contract, decision memory, and audit log.

### Phase 2

Add GitHub, Supabase, and Vercel identity checks. Add CLI, API, and browser capability routing.

### Phase 3

Add Codex thread reuse, new thread recommendations, worktree selection, and context packet generation.

### Phase 4

Add project phase behavior, model profile routing, reasoning selection, creative posture, scope controls, and cost controls.

### Phase 5

Package the plugin, add onboarding, publish documentation, and prepare the public launch message.

## Open design questions

1. Which service should be the source of truth for client identity?
2. Which actions always require confirmation beyond production and destructive work?
3. Should account profiles be created automatically during onboarding or explicitly named by the user?
4. How long should a verified identity remain trusted before it is checked again?
5. What response latency target should the hosted router meet?
6. How should the system estimate and report token and dollar savings?

## Current product statement

Jev Control Plane makes Codex context aware before it acts. It resolves the client, project, business goal, development phase, scope, repository, service accounts, environment, thread, model profile, reasoning level, risk, acceptance criteria, and safest available execution path. Codex remains the builder and verifier. Jev provides fast structured decisions. Deterministic policy, identity checks, project memory, and outcome verification keep those decisions useful and safe.

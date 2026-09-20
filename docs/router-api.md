# Router API

The plugin calls a private JSON endpoint. The endpoint is responsible for invoking `typesafe-ai/jev` and returning a strict decision object.

## Authentication

The plugin sends:

```http
Authorization: Bearer <JEV_ROUTER_TOKEN>
Content-Type: application/json
```

The endpoint must reject missing or incorrect tokens. Use a separate random value for this shared secret. Do not reuse a provider key.

## Request

```json
{
  "prompt": "Add validation to the contact form",
  "context": {
    "clientId": "example-client",
    "projectId": "example-project",
    "projectPhase": "implementation",
    "businessGoal": "Ship a reliable client portal",
    "requiredScope": ["contact form"],
    "excludedScope": ["online payments"],
    "definitionOfDone": ["Automated tests pass"],
    "environment": "staging",
    "repository": {
      "present": true,
      "matchesRegisteredProject": true,
      "dirty": false
    },
    "localRecommendation": {
      "scopeStatus": "inside_scope",
      "riskLevel": "low",
      "threadAction": "reuse_current",
      "worktreeRecommended": false,
      "modelProfile": "balanced_build",
      "reasoningEffort": "medium"
    },
    "routingPolicy": {}
  }
}
```

The plugin limits the prompt to 12000 characters and each scope item to 500 characters. Common credential formats receive best effort redaction before transmission.

## Response

```json
{
  "provider": "jev",
  "model": "typesafe-ai/jev",
  "decision": {
    "scopeStatus": "inside_scope",
    "riskLevel": "low",
    "reversibility": "easy",
    "threadAction": "reuse_current",
    "worktreeRecommended": false,
    "modelProfile": "balanced_build",
    "reasoningEffort": "medium"
  },
  "confidence": {
    "scopeStatus": 0.94,
    "riskLevel": 0.91,
    "threadAction": 0.89,
    "modelProfile": 0.92
  }
}
```

Allowed values are enforced locally. An invalid response becomes a labeled local fallback.

## Local precedence

The endpoint recommendation cannot lower explicit risk floors or erase an explicit scope exclusion. Subjective changes require confidence of at least `0.80`. Production and destructive terms remain subject to local policy even when JEV recommends a lower risk level.

## Example implementation

The repository includes a Vercel route at `plugins/jev-control-plane/examples/vercel-router/api/jev/route.ts`. Copy it into a project, install AI SDK 7.0.105 or newer, configure `JEV_ROUTER_SHARED_SECRET`, and configure Vercel AI Gateway credentials.

The example requests zero data retention through the Gateway provider option. Confirm provider support and your own data handling obligations before production use.

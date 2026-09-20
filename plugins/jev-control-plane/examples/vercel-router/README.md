# Vercel Router Example

This is a drop in Next.js App Router route for the private Jev Control Plane endpoint.

## Setup

1. Use Node.js 22 or newer and install AI SDK 7.0.105 or newer.

   ```bash
   pnpm add ai@^7.0.105
   ```

2. Copy `api/jev/route.ts` to `app/api/jev/route.ts` in the Next.js project.

3. Configure Vercel AI Gateway using the project OIDC token or `AI_GATEWAY_API_KEY`.

4. Generate a random shared secret and set it as `JEV_ROUTER_SHARED_SECRET` on the endpoint. Set the same value as `JEV_ROUTER_TOKEN` where Codex runs.

5. Deploy the endpoint, then set `JEV_ROUTER_ENDPOINT` to its HTTPS URL.

## Important

Keep this route private. It accepts prompt and project context from the local plugin and consumes the endpoint owner’s AI Gateway account.

The route requests zero data retention. Verify current provider support, account policy, logs, and regional requirements before using it with sensitive project context.

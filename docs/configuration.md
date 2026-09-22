# Configuration

## Project manifest

Jev Control Plane searches the current directory and its parents for `.jev/project.json` or `jev.project.json`. The `.jev` path is preferred.

Start from `plugins/jev-control-plane/examples/project.json`. The manifest records project context, not credentials.

Important fields:

| Field | Purpose |
| --- | --- |
| `client.client_id` | Stable client identifier |
| `project.project_id` | Stable project identifier |
| `blueprint.phase` | Current delivery phase |
| `blueprint.scope.required` | Work that is already approved |
| `blueprint.scope.excluded` | Work that requires a scope decision |
| `blueprint.definition_of_done` | Concrete completion criteria |
| `services.github` | Expected GitHub repository and optional login |
| `services.supabase` | Expected Supabase project reference |
| `services.vercel` | Expected Vercel project and optional login |
| `environments.default` | Environment used unless production is explicit |
| `policy.production_requires_confirmation` | Whether production requests require confirmation |
| `routing.mode` | `active` applies delegated routing, `shadow` only records recommendations |
| `runtime_models.codex` | Optional project mapping for Codex profiles |
| `runtime_models.claude` | Optional project mapping for Claude Code profiles |

Set `JEV_PROJECT_FILE` to use an explicit manifest path.

Set `JEV_ROUTING_MODE=shadow` to try observe only routing without editing the manifest. See [additional workflows](advanced-features.md) for shadow mode and policy recipes.

## Router settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `JEV_ROUTER_ENDPOINT` | settings file value | Private HTTPS endpoint |
| `JEV_ROUTER_TOKEN` | macOS Keychain lookup | Shared bearer token |
| `JEV_ROUTER_TIMEOUT_SECONDS` | `8` | Request timeout, clamped from 1 through 30 seconds |
| `JEV_SETTINGS_FILE` | `~/.config/jev-control-plane/settings.json` | Alternate local settings file |

Remote endpoints must use HTTPS. Plain HTTP is accepted only for `localhost`, `127.0.0.1`, and `::1` during local development.

The settings file supports this shape:

```json
{
  "router_endpoint": "https://your-project.vercel.app/api/jev/route"
}
```

On macOS, store the router token in Keychain:

```bash
security add-generic-password \
  -a "$USER" \
  -s jev-control-plane-router \
  -w "replace-with-your-shared-secret" \
  -U
```

## Runtime model mappings

Override any default mapping when a model is unavailable on your Codex host:

The resolution order is environment variable, then project manifest mapping, then bundled default. The local dashboard can save a project mapping after confirmation. It does not edit environment variables or host configuration.

```bash
export JEV_RUNTIME_MODEL_RAPID_DECISION="gpt-5.6-luna"
export JEV_RUNTIME_MODEL_BALANCED_BUILD="gpt-5.6-terra"
export JEV_RUNTIME_MODEL_COMPLEX_BUILD="gpt-5.6-sol"
export JEV_RUNTIME_MODEL_CRITICAL_REVIEW="gpt-6-astra"
```

The plugin does not query the host model catalog. A rejected runtime model remains visible in the failed tool call, so operators can update the relevant mapping explicitly.

Claude Code uses its own model aliases. Override them separately:

```bash
export JEV_CLAUDE_MODEL_RAPID_DECISION="haiku"
export JEV_CLAUDE_MODEL_BALANCED_BUILD="sonnet"
export JEV_CLAUDE_MODEL_COMPLEX_BUILD="opus"
export JEV_CLAUDE_MODEL_CRITICAL_REVIEW="opus"
```

The selected effort is applied through the bundled `routed-low`, `routed-medium`, or `routed-high` Claude agent. The hook rewrites only a general agent delegation. It preserves specialized agents such as `Explore` and `Plan`, including any model chosen by the caller. The parent session model and effort are not changed. Claude Code may substitute an unavailable model or effort setting, so check the actual launched agent before claiming a runtime result.

## Decision logs

Codex provides `PLUGIN_DATA`. Claude Code provides `CLAUDE_PLUGIN_DATA`. Jev Control Plane writes `decisions.jsonl` in the appropriate host directory.

| Variable | Default | Meaning |
| --- | --- | --- |
| `JEV_DECISION_LOG_MAX_BYTES` | `5000000` | Rotation threshold, clamped from 1024 through 100000000 bytes |
| `JEV_DECISION_LOG_BACKUPS` | `3` | Number of rotated files, clamped from 0 through 20 |

Logs include decision metadata and a SHA 256 prompt digest. They do not include raw prompt text.

Run `python3 plugins/jev-control-plane/scripts/jev_control_plane.py recent --limit 10` from the repository after setting the appropriate data directory variable to inspect recent records, or pass `--data-dir /path/to/plugin/data`. The command is read only and does not call JEV. Run `doctor --cwd /path/to/project` to check the manifest, endpoint, token presence, and local Git context without calling JEV or external accounts. The doctor reports only whether a token is present, not its value.

## Supported environments

The hook is tested on macOS and Linux with Python 3.10 or newer. Windows users should run Codex and the plugin through WSL until a native Windows hook command is verified.

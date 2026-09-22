# Additional workflows

These workflows add safe ways to test, carry, and reuse JEV decisions. They do not change the model of an already running parent session.

## Shadow mode

Set `routing.mode` to `shadow` in `.jev/project.json`, or use `JEV_ROUTING_MODE=shadow` for a session. The hooks still calculate and log a recommendation, but the delegated tool input is left unchanged. A record marked `route_applied: false` is an observation, not an executed route. Switch back to `active` only after comparing recommendations with the host's actual work.

```json
{"routing": {"mode": "shadow"}}
```

## Safe handoffs

Create a portable context packet from a task:

```bash
python3 plugins/jev-control-plane/scripts/jev_control_plane.py handoff \
  --prompt "Review the form validation" \
  --cwd /path/to/project > jev-handoff.json

python3 plugins/jev-control-plane/scripts/jev_control_plane.py handoff-verify \
  --file jev-handoff.json
```

The packet contains a small allowlist of routing and project fields, not the original prompt or router token. Its checksum detects accidental edits but does not authenticate the creator. Recheck identity and permissions before acting on another agent's packet. Add `--use-jev` to the first command only when you want the configured router to make that handoff decision.

## Policy recipes

List built in recipes or preview one against the current manifest:

```bash
python3 plugins/jev-control-plane/scripts/jev_control_plane.py recipes
python3 plugins/jev-control-plane/scripts/jev_control_plane.py recipes \
  --cwd /path/to/project --preview client-project
```

Applying a recipe changes `.jev/project.json`. It requires both the recipe name and the exact registered project ID:

```bash
python3 plugins/jev-control-plane/scripts/jev_control_plane.py recipes \
  --cwd /path/to/project --apply client-project --project-id acme_platform
```

Recipes only change approved policy and routing fields. They cannot disable production confirmation or weaken destructive action policy. Previewing never writes a file.

## Pull request advisor

JEV can inspect the metadata of two local Git commits and recommend review depth:

```bash
python3 plugins/jev-control-plane/scripts/jev_control_plane.py pr-advice \
  --cwd /path/to/repository --base main --head HEAD \
  --title "Add account permissions" --markdown
```

The command reads file paths and line counts from local Git, not the full diff or external accounts. It reports risk, profile, suggested runtime, and verification checks. The included GitHub Actions workflow writes a job summary with read only repository permissions. Because pull request code is untrusted, that workflow deliberately uses the local fallback and receives no router secret. A trusted local run can opt in to the configured JEV endpoint with `--use-jev`.

Advice is not approval to merge, deploy, or perform production writes. The recommended runtime is not proof of an actual host model.

## Community adapters

The [adapter kit](adapters.md) defines a small host mapping contract, an example specification, and a validation command. It supports new agent integrations without changing the core decision rules. A new host still needs its own hook wrapper and runtime verification before support can be claimed.

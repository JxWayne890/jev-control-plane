# Community adapter kit

The decision engine is independent of any one coding agent. An adapter maps the host's delegated tool input to JEV's selected model and reasoning level. The bundled Codex and Claude Code hooks are reference integrations.

The small adapter contract lives in [`jev_features.py`](../plugins/jev-control-plane/scripts/jev_features.py). Start with the [example adapter](../plugins/jev-control-plane/examples/adapter.json), then validate it:

```bash
python3 plugins/jev-control-plane/scripts/jev_control_plane.py adapter-check \
  --spec plugins/jev-control-plane/examples/adapter.json
```

An adapter describes the host tool names and the three input fields used for the task prompt, requested model, and requested reasoning. `adapt_tool_input` returns a copy of the original input. In shadow mode it returns the input unchanged. A host integration is responsible for wrapping that updated input in the host's own hook response shape.

Before claiming support for a new host, test these cases:

1. Active mode requests the selected model and effort on a delegated task.
2. Shadow mode leaves the host tool input unchanged.
3. Unrelated tools are not routed.
4. Missing or unavailable model mappings are reported accurately.
5. Specialized agents keep their own type and model unless the host explicitly supports changing them.
6. An already running parent model is never reported as changed by a prompt hook.
7. Production and repository safety floors cannot be lowered by the adapter.

The adapter contract does not grant permission to create new threads, call external services, or write to production. Those actions remain subject to the host and project policy.

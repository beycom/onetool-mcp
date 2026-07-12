# OneTool File Layout

Canonical ownership rules for files created by OneTool and bundled packs.

## Roots

| Root | Meaning |
|------|---------|
| `{OT_DIR}` | Active OneTool config directory, equivalent to `config_path.parent` |
| `{CWD}` | Effective project working directory, equivalent to `OT_CWD` when set |
| `{HOME}` | User home directory |
| `{CALLER}` | Explicit path supplied by a tool caller |
| `{ABS}` | Absolute path used as-is |

## Layout

```text
{OT_DIR}/
  onetool.yaml
  secrets.yaml
  servers.yaml
  snippets.yaml
  prompts.yaml
  security.yaml
  tools/
  runtime/
    logs/
    stats/
    sessions/
    reports/
  data/
    mem/default.db
    knowledge/<db>.db
  auth/
    mcp-direct.key
  telemetry/
  templates/
    diagram/
    arch/

{CWD}/
  .localhist/
  .onetool/
    state/
      console/instances/<mcp-instance-id>/messages/<message-id>.json
      localhist/
      whiteboard/
      <pack>/
  diagrams/
  arch/
```

## Rules

- Config files and extension tools stay under `{OT_DIR}`.
- Runtime files belong under `{OT_DIR}/runtime/`.
- Tool-owned config-scoped data stores belong under `{OT_DIR}/data/`.
- Telemetry remains `{OT_DIR}/telemetry/`.
- Direct API auth belongs under `{OT_DIR}/auth/mcp-direct.key`.
- Project-local pack state belongs under `{CWD}/.onetool/state/{pack}/`.
- Console message bodies are session-scoped under
  `{CWD}/.onetool/state/console/instances/<mcp-instance-id>/messages/`; startup
  sweeps instance directories left by dead sessions (live concurrent
  sessions are preserved via a pid record) and shutdown removes the
  current instance.
- Generated project artifacts stay visible under `{CWD}`.
- Caller-owned paths remain caller-owned.
- `{HOME}` is not used for project-specific runtime or tool state.

## Helpers

| Helper | Use For |
|--------|---------|
| `resolve_ot_path()` | Existing config-relative strings and explicit OT_DIR paths |
| `get_ot_runtime_dir(kind)` | Runtime dirs such as logs, stats, sessions, reports |
| `get_ot_data_dir(kind)` | Config-scoped data stores such as mem and knowledge |
| `get_ot_template_dir(kind)` | Editable template override dirs |
| `resolve_cwd_path(path)` | Caller paths and project-relative paths |
| `get_project_state_dir(pack)` | Pack-owned project state |
| `get_project_artifact_dir(kind)` | Generated project artifacts |

## Templates

Packaged defaults live in `ot.config.global_templates`. Editable overrides live under `{OT_DIR}/templates/{pack}/`. Lookup order is explicit configured path, editable override path, then packaged default.

`ensure_ot_dir()` copies only user-editable config files and the explicit editable template directories. It does not create runtime directories, copy `skills/`, copy `skills.md`, or copy package-only resource directories.

## Migration

This layout does not imply migration or compatibility aliases. Old files in previous local locations should be harmless, but code must not read them as fallbacks.

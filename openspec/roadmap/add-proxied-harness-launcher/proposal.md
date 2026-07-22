## Why

OneTool users need one command to select a coding harness and model while keeping
provider routing, subscription authentication, and gateway diagnostics consistent.
Making CLIProxyAPI mandatory for OneTool-launched sessions creates a single
observable route for Claude Code and Codex instead of mixing direct and proxied
behavior.

## What Changes

- Add `onetool claude [MODEL]` and `onetool codex [MODEL]` commands that launch
  the official interactive harness with passthrough arguments and safe or bypass
  permission modes.
- Route every OneTool-launched harness session through CLIProxyAPI; no direct
  Claude or Codex subscription path is provided.
- Support configured models backed by Claude subscriptions, ChatGPT/Codex
  subscriptions, and OpenRouter for Claude Code and Codex when CLIProxyAPI
  advertises a compatible route.
- Add interactive selection and namespaced setup, login, status, doctor, model,
  configuration, log, and lifecycle commands under `onetool code`.
- Add typed OneTool harness configuration, OneTool secret references, generated
  CLIProxyAPI and Codex adapter artifacts, and config-relative runtime/auth state.
- Add managed and externally managed CLIProxyAPI modes with health checks, OAuth
  delegation, model discovery, process supervision, and actionable failures.
- Add a read-only `cliproxy` MCP pack for redacted gateway health, route, model,
  provider, and recent diagnostic observation from inside an agent session.
- Warn that Claude subscription traffic through CLIProxyAPI can be classified as
  extra usage and incur additional charges; routing and billing behavior depend on
  the installed CLIProxyAPI and upstream providers.

## Capabilities

### New Capabilities

- `harness-launcher`: Proxy-only selection, resolution, and interactive launch of
  Claude Code and Codex across the supported model sources.
- `cliproxy-management`: OneTool configuration, setup, OAuth delegation,
  lifecycle, health, model discovery, diagnostics, and generated adapter state for
  CLIProxyAPI.
- `cliproxy-observability-pack`: Read-only MCP tools for safe in-session
  observation of the managed gateway and resolved harness route.

### Modified Capabilities

- `onetool-cli`: Add top-level harness launch commands and the `code` management
  command group.
- `serve-configuration`: Add a typed top-level harness configuration contract and
  config-relative generated state ownership.

## Impact

- Affected CLI: `src/onetool/cli.py` and a new harness/code command group.
- Affected runtime services: typed route resolution, environment construction,
  CLIProxyAPI process management, local HTTP management client, OAuth delegation,
  redaction, and `os.execvpe()` handoff.
- Affected tool surface: a new base `cliproxy` pack and its full discovery,
  prompts, documentation, and generated tool-index registration.
- Affected configuration: `onetool.yaml` gains a typed harness section; optional
  materialisation may use `harness.yaml`; secrets remain in OneTool secret/env
  resolution rather than generated user-editable files.
- Affected state: generated adapter configuration, model catalogs, caches, logs,
  PID state, and OAuth data follow the canonical `{OT_DIR}` layout.
- External dependency: CLIProxyAPI is required for every launcher route and remains
  an external executable; OneTool does not vendor or reimplement its protocols.
- Coordination: the existing `oauth-quota-pack` roadmap change remains separate;
  this change observes CLIProxyAPI and does not directly own provider OAuth files
  or promise durable quota/cost analytics.

---
name: ot-setup
description: Use when OneTool, a pack extra, executable, credential, config value, or renderer is missing or unhealthy. Diagnoses setup and guides separately approved host changes; MCP server lifecycle belongs to ot-mcp-proxy.
user-invocable: true
---

# OneTool Setup

## Capability boundary

Use this for installation and persistent OneTool readiness, not ordinary tool calls or ongoing
runtime operation. Runtime status/reload/recovery belongs to `ot-runtime`; an outbound MCP server's
transport and connection lifecycle belongs to `ot-mcp-proxy`.

## Workflow

### Diagnose

1. Inspect `ot.status()` and the smallest relevant
   `ot.help(query='<pack>', topic='setup')`.
2. Classify each gap: missing OneTool extra, library, executable, secret, config, renderer, or
   proxy server.
3. Inspect `ot.help(query='<pack>', topic='config')` only when configuration is implicated.
4. Treat setup/config help as read-only. It must not install, edit, start, connect, or reveal a
   secret.

### Propose and approve

State the resolved config location, exact minimal change, affected pack, and verification command.
Separate package installation, config edits, secret changes, reloads, and service actions into
individually reviewable operations. Stop for explicit approval before each mutation.

Use the approved environment's existing package manager, CLI, file/config editor, and secret
capability. Do not invent a privileged OneTool setup API. For an MCP-only remote connection where
the host cannot be changed, return redacted operator instructions instead of claiming success.

### Apply and verify

After approval, change only the named scope. Validate configuration, reload only when required,
repeat the setup diagnostic, and run a registered non-mutating smoke operation. Report remaining
optional or inactive requirements separately from blockers.

## Safety and side effects

Never print expanded secret values, bearer tokens, sensitive headers, or credential-like config.
Diagnosis is read-only. Installation, config/secrets changes, reloads, service starts, and
connections are distinct mutations requiring explicit approval. The runtime exposes no privileged
setup mutation API; use approved host capabilities. `[all]` means `[util,dev]`; `[scrape]` remains
separately opt-in.

## Verification and recovery

Run `onetool init validate`, `ot.reload()` only when required, repeat setup help, and run the
registered read-only smoke check. For a remote MCP-only agent, return redacted operator steps and
commands instead of claiming host changes succeeded.

If validation fails, preserve the exact error and propose one smaller correction. Do not add
legacy config keys, aliases, dependency fallbacks, or repeated blind retries.

<!-- BEGIN GENERATED:CATALOG_COVERAGE -->
## Catalog coverage

**Role:** `setup`

This cross-catalog skill owns a workflow rather than a single pack.

For a missing pack, dependency, secret, or config field, inspect `ot.help(query='<pack>', topic='setup')` and hand off to `ot-setup`. For outbound MCP server setup or lifecycle, hand off to `ot-mcp-proxy`.
<!-- END GENERATED:CATALOG_COVERAGE -->

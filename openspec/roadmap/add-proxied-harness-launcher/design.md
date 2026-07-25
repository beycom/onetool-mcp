## Context

OneTool already owns a typed YAML configuration boundary, encrypted/environment
secret resolution, config-relative runtime and auth directories, structured
logging, Typer/Rich CLI conventions, and pack discovery. The proposed OneCode
launcher duplicates those foundations while introducing a second product,
configuration root, executable, and release lifecycle.

This change instead adds a harness-launching subsystem to OneTool. Users invoke
`onetool claude <model>` or `onetool codex <model>`. The official Claude Code and
Codex harnesses are launched unchanged, but every model request is routed through
CLIProxyAPI. The supported credential/model sources are Claude subscription OAuth,
ChatGPT/Codex subscription OAuth, and OpenRouter. There is deliberately no direct
subscription route in this subsystem.

CLIProxyAPI is an external executable with a fast-moving command, configuration,
management API, model, and billing surface. OneTool manages or connects to it but
does not reimplement protocol translation, OAuth, refresh, or provider routing.
The design must protect proxy client keys, management keys, OAuth artifacts, and
request logs while still making gateway health and redacted activity observable
through both CLI and MCP pack surfaces.

## Goals / Non-Goals

**Goals:**

- Provide the concise `onetool {harness} {model}` interface for Claude Code and
  Codex.
- Route every OneTool-launched harness through CLIProxyAPI.
- Support both harnesses against configured Claude subscription,
  ChatGPT/Codex subscription, and OpenRouter models when the installed proxy
  exposes a compatible model.
- Reuse OneTool configuration, secrets, paths, logging, CLI, and pack conventions.
- Delegate Claude and Codex OAuth login and refresh behavior to CLIProxyAPI.
- Manage a local proxy process or connect to an explicitly configured external
  proxy.
- Build one typed, redacting gateway service used by Rich CLI views and a
  structured read-only MCP pack.
- Preserve official harness TTY, signal, color, session, and exit behavior.
- Make the Claude-subscription extra-usage risk prominent and testable.

**Non-Goals:**

- No direct Claude subscription or direct ChatGPT/Codex subscription launch path.
- No replacement UI for Claude Code or Codex.
- No reimplementation or vendoring of CLIProxyAPI protocols or OAuth.
- No generic multi-provider gateway abstraction or support for a second proxy.
- No multi-account rotation, automatic failover policy, team administration, or
  remote proxy deployment in v1.
- No headless prompt execution or multi-harness orchestration.
- No mid-session provider switching.
- No persistent token/cost analytics collector or quota dashboard in this change.
- No raw management-API escape hatch, raw log tool, or pack-based mutation.
- No Windows support in v1.

## Decisions

### Decision: Make the launcher a OneTool subsystem

Place shared typed behavior under `src/ot/harness/`, CLI adapters under
`src/onetool/cli_commands/`, and the MCP adapter in `src/ottools/cliproxy.py`.
The shared layer contains no Typer/Rich rendering and returns typed/native data so
both surfaces use identical resolution, health, redaction, and error semantics.

Alternatives considered:

- Separate OneCode project: rejected because it duplicates configuration, secret,
  path, logging, packaging, and CLI foundations and loses in-session MCP synergy.
- Put all behavior in `src/onetool/cli.py`: rejected because the pack would need to
  parse CLI output or duplicate business logic.
- Implement as a tool pack only: rejected because interactive TTY handoff and OAuth
  flows belong to the host CLI, not an MCP request.

### Decision: Route every launch through CLIProxyAPI

The route resolver has no direct mode. Every `LaunchSpec` contains a local or
configured CLIProxyAPI endpoint and proxy authentication. Managed mode starts the
proxy on demand; external mode requires a healthy configured endpoint.

The logical compatibility matrix is the cross-product of:

- harness: `claude`, `codex`
- source: `claude`, `chatgpt`, `openrouter`

A configured pair is launchable only when the installed CLIProxyAPI version and
live model discovery advertise a compatible route. Unsupported pairs fail before
process replacement with the harness, model, source, proxy version, and corrective
command.

Alternative considered: keep direct native subscription routes for performance.
Rejected because the requested OneTool contract is a single wrapped and observable
path, and mixed direct/proxy behavior makes status and route semantics ambiguous.

### Decision: Use one typed OneTool configuration source

Add a top-level `harness:` section to `OneToolConfig`. Users may keep it in
`onetool.yaml` or materialise `harness.yaml` through the normal include mechanism.
It owns defaults, CLIProxyAPI connection/management settings, source secret names,
and the model registry.

The loader validates the raw mapping once into typed models. Route resolution,
adapter generation, proxy management, CLI rendering, and the pack receive typed
objects and do not read YAML independently. Unknown fields and unsupported values
fail through normal strict configuration validation; no aliases or legacy keys are
accepted.

Secrets are referenced by name and resolved through OneTool's existing secret/env
boundary only when required. Generated CLIProxyAPI configuration can contain
resolved values, so it is written atomically with mode `0600`, never displayed,
and regenerated when its effective inputs change.

### Decision: Follow the canonical `{OT_DIR}` layout

Use the active config directory rather than `~/onecode`:

```text
{OT_DIR}/
  onetool.yaml
  harness.yaml                       # optional user-owned include
  auth/
    cliproxy/                        # CLIProxyAPI OAuth state
  runtime/
    code/
      cliproxy/
        config.yaml                  # generated, private
        proxy.pid
      codex/
        model-catalog.json           # generated adapter artifact
      cache/
        models.json
    logs/
      cliproxy.log
```

Generated files are adapters or runtime state, not additional user-editable
configuration. Caller-supplied external proxy URLs remain caller-owned.

### Decision: Keep the normal launch path small

`onetool claude [MODEL]` and `onetool codex [MODEL]` resolve configuration, ensure
the proxy is healthy, validate the live model/route, show a compact summary, and
call `os.execvpe()`. `--dry-run` returns before process replacement with a
redacted command, route, and environment delta. Arguments following `--` are
passed to the official harness unchanged.

`onetool code` owns the interactive picker. Setup, login, status, doctor, config,
model discovery, logs, and lifecycle operations are namespaced below it so proxy
complexity does not dominate normal launch commands.

### Decision: Build pure launch specifications and isolate environment changes

Use immutable typed models for harnesses, sources, models, routes, and
`LaunchSpec`. A launch specification contains argv, environment additions,
environment removals, route metadata, warnings, and redacted display fields.

Claude launches use the Anthropic-compatible proxy endpoint and model/context
environment required by the selected route. Codex launches use invocation-scoped
configuration pointing at the proxy's Responses-compatible endpoint and a
generated model catalog where the current Codex schema requires one. Global
Claude or Codex configuration is not rewritten for each launch.

The launcher clears inherited provider/gateway controls that conflict with the
resolved route. It also adds non-secret OneTool route markers (harness, configured
model, source, route id, permission mode) so a OneTool MCP server spawned by the
harness can report its current route. It never exports OAuth tokens or management
keys as observation metadata.

### Decision: Delegate OAuth and proxy lifecycle

`onetool code login claude` and `onetool code login codex` execute the installed
CLIProxyAPI login modes using the generated config and auth directory. OneTool does
not inspect, refresh, translate, or copy OAuth tokens.

Managed mode uses a detached local child process, redirected log file, validated
PID record, loopback HTTP health check, graceful SIGTERM shutdown, bounded wait,
and safe stale-PID cleanup. External mode never starts or stops the configured
process. All launch routes require proxy health; `auto_start` controls whether an
unhealthy managed proxy is started automatically or reported as an error.

### Decision: Separate proxy client and management credentials

Inference/model requests use the generated proxy client key. Management requests
use a distinct management key. Management is loopback-only by default and disabled
unless explicitly configured. Status and doctor report key presence and endpoint
availability without returning values.

The client has explicit methods for required endpoints; it does not accept an
arbitrary path/method. Response validators allow only documented fields needed by
the CLI and pack. Version/capability detection converts unsupported upstream
features into structured `unsupported` results rather than guessing.

### Decision: Make the `cliproxy` pack read-only

The base pack exposes structured `status`, `models`, `providers`, `routes`,
`activity`, and `errors` tools. These call the shared gateway service and return
native data with bounded results. Activity contains only operational metadata such
as timestamp, route/session identifier when available, harness, requested/resolved
model, source, status, latency, and token counts returned by upstream. Prompt and
response bodies are never returned.

The pack cannot launch a harness, start/stop/restart the proxy, initiate OAuth,
change config, download auth files, clear logs, or call arbitrary management
endpoints. Those actions remain explicit CLI operations. This prevents an active
agent from severing or reconfiguring its own route.

### Decision: Treat observability as capability-detected and bounded

Health and live models use stable inference endpoints. Provider readiness, recent
activity, and errors use the authenticated management API only when the installed
CLIProxyAPI advertises the required endpoints. Missing support produces a
structured `unsupported` state with an upgrade/enablement hint.

OneTool does not consume CLIProxyAPI's destructive usage queue and does not claim
durable usage/cost history. Request-log-derived activity is sanitized and bounded;
secret-shaped values, auth/account identifiers, request bodies, response bodies,
and raw headers are omitted. The separate `oauth-quota-pack` roadmap work is not
folded into this change.

### Decision: Warn on Claude subscription billing risk

Every route whose source is `claude` includes a prominent launch-summary and
dry-run warning that proxy-mediated Claude subscription requests can be classified
as extra usage and incur additional charges. Setup, login, status, and user-facing
documentation repeat that behavior depends on the installed CLIProxyAPI version
and Anthropic billing policy. OneTool never states that subscription allowance or
billing classification is guaranteed.

## Risks / Trade-offs

- [Risk] CLIProxyAPI is a single point of failure for all OneTool launches. ->
  Mitigation: pre-launch health/model checks, managed auto-start, actionable doctor
  results, and explicit external mode.
- [Risk] CLIProxyAPI flags, config keys, endpoints, and response schemas change
  frequently. -> Mitigation: implementation-time upstream verification, version
  capability detection, strict response parsing, fixtures, and no invented
  fallbacks.
- [Risk] Claude subscription requests may be charged as extra usage. -> Mitigation:
  route-specific warnings, version reporting, documentation, and no billing
  guarantee.
- [Risk] Generated proxy config contains resolved secrets. -> Mitigation: atomic
  `0600` writes, redacted rendering, secret-scanning tests, and config-relative
  ownership.
- [Risk] Management/log endpoints can expose credentials or prompt content. ->
  Mitigation: explicit endpoint methods, allowlisted output fields, bounded
  summaries, universal secret redaction, and no raw log tool.
- [Risk] A proxy-backed harness can behave differently from its direct native
  route. -> Mitigation: proxy-only behavior is explicit, dry-run shows the route,
  and integration tests exercise installed harnesses opt-in.
- [Risk] Full harness/source cross-product may not be supported by a particular
  proxy release. -> Mitigation: live route validation fails before launch and
  names the unsupported pair and required corrective action.
- [Risk] Default bypass permissions are dangerous. -> Mitigation: prominent launch
  summary, mutually exclusive validated flags, and tests that safe mode never adds
  bypass arguments.

## Migration Plan

1. Add typed `harness` config with packaged model defaults and optional
   `harness.yaml` materialisation.
2. Add the shared route, adapter, redaction, and proxy management services without
   registering public launch commands.
3. Add setup/doctor/login/lifecycle CLI commands and validate against the current
   CLIProxyAPI release and config example.
4. Add top-level launch commands, interactive selection, and opt-in installed
   harness integration tests.
5. Add the read-only `cliproxy` pack and complete pack/docs registration.
6. Document the proxy-only invariant and Claude extra-usage warning before release.

Rollback removes the additive commands, config section, pack, and generated
runtime/auth directories. Existing OneTool server and tool behavior remains
unchanged. No direct OneCode installation or configuration is migrated
automatically.

## Open Questions

None. Current upstream CLI flags, model identifiers, management endpoints, Codex
catalog schema, and Claude gateway variables must still be verified during
implementation and captured in tests; uncertainty is handled by capability
detection rather than alternate product behavior.

## 0. Upstream and Local Behavior Verification

- [ ] 0.1 Review `/Users/gavin/my-scripts/ai-code.sh` and record the current
  shortcut, environment cleanup, context, permission, passthrough, status, and
  process-replacement behaviors that remain applicable to the OneTool subsystem.
- [ ] 0.2 Verify the current CLIProxyAPI release, license, executable/formula name,
  `config.example.yaml`, Claude/Codex login flags, auth-directory behavior,
  inference endpoints, `/healthz`, `/v1/models`, management authentication, and
  every management endpoint used by this change; capture sanitized fixtures and
  version/capability expectations.
- [ ] 0.3 Verify current Claude Code gateway/model/context environment variables,
  safe/bypass flags, argument handling, gateway model discovery, and process
  behavior against official documentation and an installed binary.
- [ ] 0.4 Verify current Codex custom-provider, Responses API, model-catalog,
  context/capability, safe/bypass, invocation-scoped config, and passthrough
  behavior against official documentation and an installed binary.
- [ ] 0.5 Verify CLIProxyAPI's advertised compatibility for the six harness/source
  pairs (`claude|codex` x `claude|chatgpt|openrouter`); record
  unsupported/version-gated combinations as capability fixtures rather than
  inventing fallbacks.
- [ ] 0.6 Verify current upstream model ids, aliases, context windows, modalities,
  reasoning/verbosity/tool capabilities, and Claude context classes before
  freezing packaged defaults; do not ship unverified speculative ids.

## 1. Typed Harness Configuration and Paths

- [ ] 1.1 Add strict Pydantic models for harness defaults, CLIProxyAPI managed and
  external modes, named proxy/management/OpenRouter secrets, model sources,
  per-model harness compatibility, context, modalities, and capability metadata.
- [ ] 1.2 Add the optional top-level `harness` section to `OneToolConfig`, ensure
  unknown/legacy fields fail normal validation, and keep existing MCP startup
  unchanged when the section is absent.
- [ ] 1.3 Add a packaged `harness.yaml` template with only verified model entries
  and proxy-only routes; support normal inline/include loading with no embedded
  runtime fallback registry.
- [ ] 1.4 Extend guided init and `onetool code setup` materialisation so
  `harness.yaml` uses existing confirmation, `--force`, include, and `.bak`
  behavior.
- [ ] 1.5 Add canonical path helpers for generated proxy config/PID, Codex catalog,
  model cache, proxy log, and CLIProxyAPI auth state under the active `{OT_DIR}`;
  do not use `expanduser()` or a `~/onecode` fallback.
- [ ] 1.6 Add config/path unit tests covering valid managed/external configs,
  named-secret lazy validation, duplicate/ambiguous models, unsupported sources or
  harnesses, invalid defaults, unknown keys, include materialisation, alternative
  config roots, and no-harness-config MCP behavior.

## 2. Shared Route and Launch Domain

- [ ] 2.1 Add `src/ot/harness/` typed immutable models for harness, source, model,
  proxy capability, resolved route, warning, environment delta, and `LaunchSpec`.
- [ ] 2.2 Implement a single resolver for shortcuts/full ids/defaults and live
  proxy compatibility across both harnesses and all three sources, with no
  direct route branch or provider fallback.
- [ ] 2.3 Implement pure Claude Code launch-spec construction with inherited
  gateway/context cleanup, proxy endpoint/auth, model/context settings,
  permission mapping, passthrough ordering, and non-secret route markers.
- [ ] 2.4 Implement pure Codex launch-spec construction with invocation-scoped
  CLIProxyAPI Responses provider/catalog settings, permission mapping, passthrough
  ordering, and non-secret route markers without rewriting unrelated global Codex
  settings.
- [ ] 2.5 Implement common bounded redaction and display metadata for argv,
  environment additions/removals, route summaries, upstream errors, account/auth
  fields, and Claude extra-usage warnings.
- [ ] 2.6 Add exhaustive unit tests for shortcut/full-id/default resolution, the
  six compatibility pairs, live unsupported pairs, unknown/ambiguous models,
  proxy-only invariants, safe/bypass exclusivity, safe-mode no-bypass guarantees,
  context classes, environment cleanup, route markers, passthrough, billing
  warnings, and redacted dry runs.

## 3. CLIProxyAPI Configuration and Clients

- [ ] 3.1 Implement deterministic CLIProxyAPI config generation from typed OneTool
  config, including loopback bind, distinct inference/management auth, OneTool
  auth directory, Claude/Codex OAuth routes, OpenRouter upstreams, aliases, and
  model exclusions required by verified upstream schema.
- [ ] 3.2 Implement atomic private writes and effective-input fingerprinting for
  generated CLIProxyAPI config; enforce mode `0600` and never render generated
  secret-bearing content.
- [ ] 3.3 Implement current harness adapter generation: the Codex model catalog
  under `{OT_DIR}/runtime/code/codex/` with verified context, compaction,
  modality, reasoning, verbosity, and parallel-tool fields.
- [ ] 3.4 Implement explicit inference client methods for bounded health and
  authenticated model discovery, response-shape validation, model alias/id
  matching, latency metadata, and bounded TTL caching.
- [ ] 3.5 Implement explicit authenticated management client methods for version,
  capability detection, provider readiness, bounded request activity, and bounded
  error summaries; do not add an arbitrary method/path/body API.
- [ ] 3.6 Ensure management response adapters omit auth filenames, emails, account
  ids, tokens, keys, headers, prompts, responses, tool bodies, and raw payloads;
  represent missing endpoints as structured unsupported/disabled states.
- [ ] 3.7 Add sanitized offline fixtures and unit tests for every client endpoint,
  invalid JSON/shapes, timeouts, auth failures, missing capabilities, stale/fresh
  model cache, alias misses, atomic permissions, config regeneration, adapter
  schemas, and secret redaction.

## 4. CLIProxyAPI Setup, OAuth, and Lifecycle

- [ ] 4.1 Implement executable discovery and version/capability checks with a
  verified macOS Homebrew installation offer that requires interactive
  confirmation and never installs during non-interactive runs.
- [ ] 4.2 Implement bounded managed process start using the generated config,
  detached session, config-relative log, validated PID state, health wait, and
  actionable failure cleanup.
- [ ] 4.3 Implement safe managed stop/restart with PID identity validation,
  SIGTERM, bounded wait/escalation, stale-state handling, and protection against
  signalling unrelated processes.
- [ ] 4.4 Implement external proxy mode that performs health/model checks but
  rejects lifecycle mutation; require explicit authenticated TLS opt-in for remote
  management and keep v1 managed binds loopback-only.
- [ ] 4.5 Implement managed auto-start behavior for every route and explicit
  failure with the start command when auto-start is disabled; never fall back to a
  direct provider endpoint.
- [ ] 4.6 Implement `onetool code login claude|codex` by delegating to verified
  CLIProxyAPI OAuth flags/config/auth paths, preserving non-zero outcomes and
  showing the Claude extra-usage warning without reading OAuth token files.
- [ ] 4.7 Add unit tests with mocked processes/signals/HTTP for executable missing,
  unsupported versions, install confirmation/cancellation, start success/failure,
  auto-start, stop/restart, stale/mismatched PID, external mode, remote-management
  validation, OAuth argv, and secret-bearing environment suppression.

## 5. OneTool CLI Surfaces

- [ ] 5.1 Add deterministic harness config resolution: explicit `--config`, then
  project `.onetool/onetool.yaml`, then standard user config, with checked paths
  and an actionable init error; do not change `onetool serve` resolution.
- [ ] 5.2 Add top-level `onetool claude [MODEL]` and `onetool codex [MODEL]`
  commands with `--safe/-S`, `--bypass`, `--config/-c`, `--dry-run`, and `--`
  passthrough.
- [ ] 5.3 Add `onetool code` Rich interactive harness/model/permission selection
  using the shared resolver, compatible-choice filtering, cancellation without
  mutation, and the same launch specification as explicit commands.
- [ ] 5.4 Add `onetool code setup|models|status|doctor`, concise/deep check
  separation, proxy-only route reporting, actionable errors, version/capability
  output, and prominent Claude extra-usage warnings.
- [ ] 5.5 Add `onetool code config path|show` with effective typed configuration,
  generated artifact freshness/paths, and complete secret/auth identity redaction.
- [ ] 5.6 Add `onetool code proxy start|stop|restart|status|models|logs`, bounded
  redacted log tails, and clear rejection in external mode; do not add a top-level
  `onetool proxy` group.
- [ ] 5.7 Implement final `os.execvpe()` handoff only after config, binary, proxy,
  live route, warning, and permission validation; ensure dry-run never starts or
  replaces the harness.
- [ ] 5.8 Add Typer/CLI unit and smoke tests for help panels, every command and
  option, config precedence, TTY/non-TTY picker behavior, cancellation, errors and
  exit codes, dry-run rendering, passthrough, no direct route, lifecycle
  delegation, and a monkeypatched process-replacement boundary.

## 6. Read-Only cliproxy MCP Pack

- [ ] 6.1 Add `src/ottools/cliproxy.py` with `pack = "cliproxy"`, explicit
  `doc_slug`, `__all__`, synchronous keyword-only public functions, complete type
  hints/docstrings, native return types, and `LogSpan` instrumentation.
- [ ] 6.2 Implement `cliproxy.status()` using shared typed gateway and inherited
  route-marker state without starting, stopping, or reconfiguring the proxy.
- [ ] 6.3 Implement `cliproxy.models()` and `cliproxy.routes()` with harness/source
  filters, configured-versus-live distinction, redacted resolution, and
  unsupported reasons.
- [ ] 6.4 Implement `cliproxy.providers()` with provider readiness and compatible
  model counts while omitting credential/account identities.
- [ ] 6.5 Implement bounded `cliproxy.activity()` and `cliproxy.errors()` using only
  capability-detected safe management fields; never return content/raw logs or
  consume the destructive usage queue.
- [ ] 6.6 Add pack tests for metadata, exports, keyword-only calls, native output,
  status/models/routes/providers, bounded activity/errors, unsupported management,
  shared config, missing management key, redaction, and the absence of lifecycle,
  OAuth, config mutation, raw log, and generic request tools.

## 7. Pack Registration and User Documentation

- [ ] 7.1 Register `cliproxy` in packaged prompts, docs metadata, MkDocs navigation,
  README pack tables, package/export surfaces, and generated tool indexes so
  `ot.packs()` has a real description and its help URL resolves.
- [ ] 7.2 Add CLI documentation for `onetool claude`, `onetool codex`, interactive
  `onetool code`, setup/login/status/doctor/config/proxy commands, config
  precedence, permission modes, passthrough, and proxy-only routing.
- [ ] 7.3 Add configuration documentation for every `harness` field, supported
  harness/source matrix, model registry, named secrets, materialised
  `harness.yaml`, generated/private artifacts, managed/external modes, and
  `{OT_DIR}` state ownership.
- [ ] 7.4 Add `cliproxy` pack reference documentation covering functions, filters,
  bounded observation, capability detection, required management access,
  redaction, read-only boundaries, and lack of durable analytics.
- [ ] 7.5 Document prominently that Claude subscription traffic through
  CLIProxyAPI may be classified as extra usage and incur additional charges, that
  behavior depends on CLIProxyAPI/Anthropic, and OneTool provides no billing
  guarantee.
- [ ] 7.6 Attribute CLIProxyAPI and any implementation references according to
  verified licenses; describe independently implemented behavior accurately and
  do not claim upstream endorsement.
- [ ] 7.7 Regenerate documentation/tool indexes with the canonical `just` tasks and
  run the docs registry/link checks; do not hand-edit generated indexes.

## 8. Integration and Verification

- [ ] 8.1 Add opt-in integration tests for installed CLIProxyAPI covering generated
  config validation, startup/health/model discovery, external-mode connection,
  and clean shutdown without using real credentials by default.
- [ ] 8.2 Add opt-in installed-harness tests that validate Claude/Codex argv,
  invocation-scoped environment/config, TTY handoff boundary, and all six
  capability routes without sending billable model requests by default.
- [ ] 8.3 Add an explicitly manual live verification checklist for authenticated
  Claude, ChatGPT/Codex, and OpenRouter routes; require confirmation before any
  request that may consume quota or incur charges and record only sanitized
  outcomes.
- [ ] 8.4 Run focused config, route, CLIProxyAPI, CLI, and `cliproxy` pack tests with
  the required speed/component markers, followed by the full relevant test suite.
- [ ] 8.5 Run secret scans over source, tests, fixtures, docs, generated examples,
  dry-run snapshots, and error fixtures; verify no OAuth token, proxy key,
  management key, account id, email, credentialed URL, prompt, or response body is
  present.
- [ ] 8.6 Verify no direct-provider launch branch, no arbitrary management request,
  no pack mutation function, no global per-launch Claude/Codex config rewrite, no
  `~/onecode` path, and no hidden model-registry fallback exists.
- [ ] 8.7 Run `just check` and all project documentation/spec validation commands;
  resolve every failure before marking the change complete.
- [ ] 8.8 Manually confirm `onetool --help`, both harness dry runs, `onetool
  code doctor`, managed/external status, Claude billing warnings, and all six
  `cliproxy` tools return the specified redacted behavior.

# Assignment platform-surface-audit

Review revision: `528cac463d21f3b510757e106d31ad310591d56b` with the OpenSpec worktree
change recorded in the run plan.

Goal: inventory user-facing OneTool capabilities outside ordinary pack ownership, especially CLI,
direct API, execution/discovery, config, security, installation, proxy, resources/prompts, and
operational diagnostics.

Owned dimensions: `requirements-specs`, `architecture-boundaries`, `security-privacy`.

Owned scope and primary paths: `platform-surfaces`; `src/ot/`, `src/onetool/`, `pyproject.toml`,
and `justfile`.

Read-only dependency context: `features/features.yaml`, architecture docs, public CLI/config docs,
and the proposed OpenSpec change.

Explicit exclusions: per-pack implementation findings, final skill ownership/candidate decisions,
tests, caches, build output, and runtime execution.

Depth and budget: standard static inspection focused on public/operator decision surfaces.

Allowed commands: static searches, file reads, and Git metadata only.

Return:

1. A capability inventory grouped by run/discovery, setup/config/install, direct API, proxy,
   security/secrets, operations/observability, and packaging/distribution.
2. Exact path:line evidence for each material user-facing workflow.
3. Platform capabilities absent or underrepresented in the feature ledger or proposed OpenSpec.
4. Handoffs to `skill-coverage-synthesis` where a separate skill may be warranted.
5. A coverage receipt listing inspected entry points, omissions, and confidence.

Rules: do not modify files, do not delegate, do not run repository code/tests/builds, and do not use
the network. Report only evidence in the owned scope.

## Draft outcomes and handoffs

- Inventoried the root run/DSL/discovery surface, init/config/install lifecycle, authenticated
  Direct API, MCP proxy, trust boundaries, runtime diagnostics, telemetry/statistics, and
  packaging/extras.
- Confirmed Direct CLI ledger drift and identified platform guidance gaps: safe root HTTP binding,
  Direct API lifecycle, full-builtins/not-a-sandbox trust boundary, `[all]` excluding `[scrape]`,
  stale configuration/worker-isolation docs, and proxy resource detail inconsistency.
- Recommended a separate user- and model-invocable `ot-runtime` skill rather than growing
  `ot-setup` or turning `ot-ref` into an administration manual.
- Recommended keeping security as a mandatory semantic section/topic under `ot-ref` unless that
  content later exceeds the generous ceiling.
- Identified a public-contract decision: internal proxy resource/prompt operations exist, but
  current public OneTool surfaces expose only metadata. Skills cannot claim full use until public
  read/render operations exist or the wording is narrowed.

## Coverage receipt

- Assignment: `platform-surface-audit`
- Inspected: `src/ot/server.py`, direct API/auth/discovery/runtime metadata, tools/paths, relevant
  config/executor/proxy/meta/sanitization/secrets/logging/telemetry/result-store modules,
  `src/onetool/cli.py`, `src/onetool/cli_commands/direct_app.py`, `pyproject.toml`, `justfile`, and
  related feature/spec/architecture/public docs.
- Checks run: static source searches and file inspection only.
- Issues drafted: none independently; cross-scope contract and coverage findings handed to
  `skill-coverage-synthesis`.
- Handoffs: `ot-runtime` candidate, proxy resource/prompt API decision, `[all]`/`[scrape]`
  reconciliation, and mandatory trust-boundary content.
- Not inspected: beta console internals, per-pack internals, detailed knowledge CLI behavior,
  tests, generated/build artifacts, caches, installer internals, and runtime execution.
- Coverage confidence: high for platform/direct/proxy/security/runtime/CLI; medium for complete
  packaging/install behavior.

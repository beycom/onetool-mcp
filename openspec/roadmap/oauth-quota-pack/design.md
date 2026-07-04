## Context

OneTool currently exposes many domain tools through pack modules, but it has no tool that reports subscription quota state for local AI coding subscriptions. The requested behavior is not API-key usage metering; it is OAuth/session-backed subscription usage for Claude Code and OpenAI Codex.

The implementation should be a OneTool MCP pack only. A separate published Python library is out of scope because the user wants MCP tools that can answer quota questions inside an agent session.

The external provider behavior is based on reverse-engineering references such as CodexBar and related open-source quota monitors. The first implementation should be original OneTool code, not a port of upstream Swift or CLI code. Any documentation should classify upstream projects as "Inspired by" or "Reference", not "Based on", unless code is copied.

### Verified local-state facts (checked 2026-07-04 on a macOS dev machine)

These are evidence, not assumptions — the implementer builds against them, not against guessed
paths:

- `~/.codex/auth.json` EXISTS (Codex CLI local auth state). Default Codex path is confirmed.
- `~/.claude/.credentials.json` does NOT exist on macOS. Claude Code stores OAuth credentials in
  the **macOS Keychain** under the generic-password service name `Claude Code-credentials`
  (verified via `security find-generic-password -s "Claude Code-credentials"`). The plain JSON
  file at `~/.claude/.credentials.json` is the Linux/WSL location.
- Consequence: the Claude provider MUST support two credential sources — Keychain on macOS
  (via the `keyring` library, already used by the ot_secrets feature) and the credentials JSON
  file on Linux/WSL — selected by platform with the config `claude.credentials_path` overriding
  the file path only. A file-only implementation is broken on macOS and MUST NOT pass review.

## Goals / Non-Goals

**Goals:**

- Add an `otutil` pack named `quota` for local subscription usage reporting.
- Provide MCP tools that return normalized Claude Code and OpenAI Codex quota snapshots.
- Provide tokenmax guidance by comparing quota remaining with time remaining.
- Reuse existing authenticated local state without requiring API keys.
- Keep credential handling read-only by default.
- Add typed configuration for provider selection, endpoint URLs, native credential paths, cache TTL, minimum polling intervals, request timeouts, and tokenmax thresholds.
- Follow OneTool tool-pack conventions: synchronous public tool functions, keyword-only args, type hints, Google-style docstrings, `LogSpan`, native structured return values, and focused unit tests.
- Add user-facing tool reference documentation that follows `dev/project/guides/tool-reference-docs.md`.

**Non-Goals:**

- No standalone `aiquota` package or importable public library API.
- No CLI command group in the first change.
- No terminal-output scraping.
- No browser-cookie/session extraction in v1.
- No OneTool `secrets.yaml` token source in v1; provider OAuth tokens stay in provider-owned native auth stores.
- No refresh-token use or credential writes in v1.
- No guarantee that unofficial provider endpoints remain stable.
- No support for Gemini, Cursor, Copilot, or other providers in this change.

## Decisions

### Decision: Implement as an `otutil` pack

Place the public pack at `src/otutil/tools/quota.py`, with implementation helpers under `src/otutil/tools/_quota/`.

Rationale: this is a utility for local developer workflows, not a core framework feature and not a developer-only diagnostic. `otutil` already owns end-user utility packs such as file, mem, ground, and knowledge.

Alternatives considered:

- `ottools`: rejected because quota access is provider-specific optional functionality, not core server functionality.
- `otdev`: rejected because the tool is useful to everyday agent users, not only development tasks.
- Separate package: rejected because the requested product surface is MCP tools.

### Decision: Keep provider implementations internal

Use internal provider classes or functions such as `ClaudeOAuthProvider` and `CodexOAuthProvider`, but do not expose them as a public import contract. Public contract is the `quota` MCP pack.

Rationale: provider internals depend on private endpoints and local auth-file formats that can drift. Keeping them internal makes it easier to revise parsing and request behavior without adding public compatibility burden.

### Decision: Normalize provider data into common windows

Return snapshots with provider, account/plan when available, source, status, fetched/cache timestamps, and `windows` entries for at least `session` and `weekly` when providers expose them.

Each window should include:

- `used_percent`
- `remaining_percent`
- `reset_at`
- `seconds_until_reset`
- `time_remaining_percent`
- optional raw/provider-specific fields

Rationale: agents need stable, provider-neutral fields to decide whether to conserve or spend. Provider raw payloads remain useful for diagnostics but should not be the main contract.

### Decision: Cache and throttle provider calls

Use an in-memory cache per provider and expose `cached`, `cache_age_seconds`, and `next_refresh_at`. `refresh=True` can bypass TTL only when the provider-specific minimum poll interval has elapsed.

Rationale: private usage endpoints can rate-limit, and statusline-style tools are likely to be called repeatedly. Returning a cached snapshot with freshness metadata is better than hammering providers or failing on every rapid call.

### Decision: Credential access is read-only by default

The default behavior reads existing local auth state and makes usage requests with current access tokens. It does not read tokens from OneTool `secrets.yaml`, use refresh tokens, or write refreshed credentials back to Claude or Codex auth files.

Rationale: subscription auth state belongs to provider CLIs or browsers. Writing refresh tokens can break those sessions or create security risk. Storing provider OAuth tokens in OneTool secrets would also make OneTool another credential owner for rotating provider auth state, which is not needed for this pack.

### Decision: Config owns endpoint and polling drift

The pack should define a Pydantic `Config` class and read it through `get_tool_config("quota", Config)`. Config fields should include:

- `enabled_providers`
- `cache_ttl_seconds`
- `request_timeout_seconds`
- `claude.credentials_path`
- `claude.usage_url`
- `claude.min_poll_seconds`
- `codex.auth_path`
- `codex.usage_url`
- `codex.min_poll_seconds`
- `tokenmax.conserve_below_ratio`
- `tokenmax.spend_above_ratio`
- `tokenmax.critical_quota_left_percent`

Rationale: endpoint URLs and auth-file locations can drift. Pydantic config gives validation, discoverability, and no legacy-key shims.

### Decision: No pack alias; `doc_slug` set explicitly

`quota` ships with NO `pack_aliases` entry — precedent: short pack names (`mem`, `db`, `arch`)
have no alias; aliases exist for verbose names (`whiteboard` → `wb`, `ot_context` → `ctx`).
The module DOES set `doc_slug = "quota"` and the mkdocs nav path must match it exactly —
lesson from the p18 docs-debt sweep, where `db`/`webfetch` `doc_slug` values 404'd against the
published paths (`db.py:27`, `webfetch.py:14` vs `mkdocs.yml`).

### Decision: Reuse otpack helpers; cache MUST be bounded

HTTP calls go through `otpack.http` helpers where they fit (`packages/onetool-pack/src/otpack/http.py`
— the shared channel used by brave/tavily/ground), and the snapshot cache uses
`otpack.cache` (`cache.py`) or an equivalent module-level store with an EXPLICIT size bound and
TTL. Never an unbounded memoize: `Cache(max_size=0)` means unlimited and is the exact
steady-state leak flagged as P2 in `p12-core-flow-hardening` (`otpack/cache.py:167`). Config is
read through `get_tool_config("quota", Config)` (`src/ot/config/loader.py:641-648`).

### Decision: Tokenmax is derived, not provider-specific

Compute tokenmax from normalized windows:

`burn_ratio = remaining_percent / time_remaining_percent`

Then classify state with configurable thresholds:

- critical when quota remaining is at or below the configured critical threshold
- conserve when burn ratio is below the conserve threshold
- on_track when between thresholds
- spend_available when burn ratio is above the spend threshold

Rationale: the user's requested output is "20% left, 3 days left, 60% of the week left" and a usable interpretation of whether that is good or bad.

## Risks / Trade-offs

- [Risk] Provider endpoints are private and can change without notice. -> Mitigation: endpoint URLs are configurable, parsers return partial snapshots with error metadata where possible, and tests cover known fixture shapes.
- [Risk] Polling too often can rate-limit or trigger provider abuse controls. -> Mitigation: default TTL and min-poll settings throttle network calls and expose freshness metadata.
- [Risk] Local auth files can contain sensitive credentials. -> Mitigation: do not log token values, do not return token values, and keep credential writes disabled by default.
- [Risk] Provider reset windows or usage percentages may be absent for some accounts. -> Mitigation: return provider status and partial windows rather than failing the entire `quota.usage(provider="all")` call.
- [Risk] Open-source references have different licenses/languages. -> Mitigation: implement original Python code and document upstream projects as references or inspiration only.

## Migration Plan

This is an additive pack. Existing users are unaffected unless they call `quota.*` tools or configure `tools.quota`.

Implementation can be rolled back by removing the `quota` pack module, helper package, tests, and tool reference documentation.

## Discovery procedure (mandatory tasks, not open questions)

The unknowns below MUST be resolved by executing these steps and recording the findings in the
committed fixtures/docs. "Confirm during implementation" without evidence is not acceptable —
if a step cannot be completed, stop and report; do NOT invent endpoint URLs, payload shapes, or
credential paths.

1. **Credential locations** (partially done — see "Verified local-state facts" above): confirm
   the Codex `auth.json` schema by inspecting a real local install; confirm the Claude Keychain
   payload shape via `keyring` on macOS and the `.credentials.json` shape on Linux/WSL if
   available. Never paste real token values anywhere — record only field names and types.
2. **Usage endpoints**: derive candidate URLs from the reference implementations (CodexBar and
   comparable open-source quota monitors — link the exact repos/files in `docs/reference/tools/quota.md`'s
   attribution section), then verify each against a live authenticated local install. An endpoint
   that cannot be verified live is shipped as `status: "unverified"` in the provider result and
   documented as such — parser coverage comes from fixtures only.
3. **Fixtures**: capture one real response per provider per state (success, partial, rate-limit
   if reproducible), then SANITIZE before committing — every token, cookie, account id, and email
   replaced with `REDACTED-*` placeholders. Committed fixtures are the contract the parsers are
   tested against.
4. **Browser-session fallback** stays out of v1; if ever added it needs a separate change with
   its own threat model and opt-in config.

## Implementation guardrails

- No compatibility shims or legacy config keys; typed config rejects unknown keys (repo rule).
- No `secrets.yaml` OAuth token overrides; token material remains in provider-owned native auth
  state only.
- No refresh-token use or credential writes in v1. If an access token is expired, report an
  auth status rather than trying to take ownership of refresh.
- No stubbing or TODO-deferral: if a provider cannot be implemented against verified evidence,
  stop and report — do not fake a provider with invented URLs or paths.
- The Claude provider MUST work on macOS (Keychain) AND Linux/WSL (credentials file); a
  file-only implementation is an automatic fail.
- Unit tests are fully offline: fixture-based, no network calls; any accidental live HTTP in
  `-m "unit and tools"` is a defect.
- No real secrets anywhere: not in fixtures, not in test names, not in docs examples, not in
  logs. Redaction tests are part of the definition of done.
- Every code task lands with its tests (`@pytest.mark.unit` + `@pytest.mark.tools`); `just check`
  and `uv run python scripts/check_docs_registry.py` must pass before the change is complete.
- Registration surface is part of the deliverable, not polish: `prompts.yaml` packs entry,
  `src/otdev/docsgen/metadata.py` PACK_DOCS row, `mkdocs.yml` nav, README pack row, regenerated
  tool index. A pack that loads but shows "(no description)" in `ot.packs()` is incomplete.

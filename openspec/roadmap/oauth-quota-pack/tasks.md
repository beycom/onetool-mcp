## 0. Discovery (execute design.md "Discovery procedure" — evidence before code)

- [ ] 0.1 Confirm the Codex `~/.codex/auth.json` schema against a real install; record field names/types (never values) in the design notes or fixture README.
- [ ] 0.2 Confirm the Claude credential payload shape from the macOS Keychain (service `Claude Code-credentials`, via `keyring`) and, if available, from `~/.claude/.credentials.json` on Linux/WSL. File existence on macOS was already verified absent (design.md "Verified local-state facts").
- [ ] 0.3 Derive candidate usage-endpoint URLs from the linked reference implementations, then verify each against a live authenticated install. Any endpoint that cannot be verified live ships as `status: "unverified"` — do NOT invent URLs.
- [ ] 0.4 Capture one real response per provider per state (success, partial, rate-limit if reproducible) and commit SANITIZED fixtures (every token/cookie/account-id/email replaced with `REDACTED-*`).

## 1. Pack Structure and Configuration

- [ ] 1.1 Add `src/otutil/tools/quota.py` with `pack = "quota"`, `doc_slug = "quota"`, NO `pack_aliases` (mem/db/arch precedent), `__all__`, synchronous keyword-only public functions, type hints, Google-style docstrings, and `LogSpan` usage.
- [ ] 1.2 Add `src/otutil/tools/_quota/` helper modules for provider models, auth-file loading, HTTP calls, parsing, cache state, and tokenmax calculations.
- [ ] 1.3 Define Pydantic config models for `tools.quota`, provider-specific config, and tokenmax thresholds using `get_tool_config("quota", Config)`.
- [ ] 1.4 Ensure config includes provider enablement, endpoint URLs, native credential paths, timeout, cache TTL, minimum polling intervals, and tokenmax thresholds.
- [ ] 1.5 Add tests proving unknown config keys and invalid config values are rejected by typed configuration.

## 2. Provider Implementations

- [ ] 2.1 Implement internal provider selection for `provider="all"`, `provider="claude"`, and `provider="codex"` with clear errors for unknown provider values.
- [ ] 2.2 Implement Codex local auth loading from configured path or default Codex auth path without returning or logging token values.
- [ ] 2.3 Implement Claude local OAuth state loading with BOTH platform sources: macOS Keychain (service `Claude Code-credentials`, via `keyring`) and Linux/WSL `~/.claude/.credentials.json` (config `claude.credentials_path` overrides the file path only) — without returning or logging token values. Unit tests cover both sources (keyring mocked).
- [ ] 2.4 Implement Codex usage HTTP request handling against the configured usage endpoint with timeout and safe error conversion.
- [ ] 2.5 Implement Claude usage HTTP request handling against the configured usage endpoint with timeout and safe error conversion.
- [ ] 2.6 Implement provider parsers that normalize successful responses into common session and weekly usage-window fields.
- [ ] 2.7 Implement partial-result behavior for missing credentials, rate limits, network failures, and response-parse failures.

## 3. Cache, Polling, and Credential Safety

- [ ] 3.1 Add per-provider in-memory cache entries with fetched timestamp, cache age, cached flag, and next refresh time — with an EXPLICIT size bound and TTL (never `max_size=0`/unbounded; see p12 P2 lesson on `otpack/cache.py:167`).
- [ ] 3.2 Enforce `cache_ttl_seconds` for normal calls and provider `min_poll_seconds` for forced refresh calls.
- [ ] 3.3 Return cached snapshots or polling-throttled provider results when refresh is requested too soon.
- [ ] 3.4 Do not use refresh tokens and do not write credentials back to provider auth stores.
- [ ] 3.5 Do not read browser cookies/session state and do not read provider OAuth tokens from OneTool `secrets.yaml`.
- [ ] 3.6 Add redaction tests proving tokens, cookies, and authorization headers do not appear in returned data, logs under direct control, or error strings.

## 4. Public Tool Behavior

- [ ] 4.1 Implement `quota.usage(provider="all", refresh=False)` returning normalized structured provider results.
- [ ] 4.2 Implement `quota.tokenmax(provider="all", refresh=False)` returning burn ratios and classifications for available windows.
- [ ] 4.3 Implement `quota.summary(provider="all", refresh=False)` returning compact human-readable quota status with partial-failure handling.
- [ ] 4.4 Implement `quota.config()` returning effective non-secret configuration values.
- [ ] 4.5 Ensure all public tools return native Python types or plain error strings, not pre-serialized JSON.

## 5. Tests

- [ ] 5.1 Add unit tests for pack metadata, exported public functions, keyword-only behavior, and no accidental public helper exposure.
- [ ] 5.2 Add unit tests for provider selection, disabled provider skipping, and unknown provider errors.
- [ ] 5.3 Add fixture-based unit tests for Codex successful, partial, missing-credential, rate-limit, and parse-error responses.
- [ ] 5.4 Add fixture-based unit tests for Claude successful, partial, missing-credential, rate-limit, and parse-error responses.
- [ ] 5.5 Add cache and polling tests covering fresh cache, stale cache, forced refresh, and minimum-poll throttling.
- [ ] 5.6 Add tokenmax tests covering conserve, on-track, spend-available, critical, and insufficient-data cases.
- [ ] 5.7 Add summary tests covering successful providers and mixed success/failure provider results.

## 6. Documentation and Attribution

- [ ] 6.1 Add `docs/reference/tools/quota.md` following the tool reference structure: highlights, functions, key parameters, requirements, configuration, examples, and source/reference section.
- [ ] 6.2 Document all `tools.quota` config keys, defaults, constraints, and the no-secrets-required local auth model.
- [ ] 6.3 Document that provider endpoints are unofficial/private and can drift.
- [ ] 6.4 Attribute CodexBar and any other behavior references as inspiration/reference unless implementation code is copied.
- [ ] 6.5 Register the pack everywhere a new pack must appear: `prompts.yaml` `packs:` one-line description (e.g. `quota: "Check Claude Code and Codex subscription quota — usage windows, resets, spend/conserve guidance"`), `src/otdev/docsgen/metadata.py` `PACK_DOCS` row, `mkdocs.yml` nav entry matching `doc_slug = "quota"` exactly, README pack table row.
- [ ] 6.6 Regenerate the tool index via `just docs-sync` (never hand-edit `tool-index.md`; if p21 has landed, this also refreshes `skills/ot-ref/reference/tool-index.md` and the ot-ref pack map).

## 7. Verification

- [ ] 7.1 Run focused quota tests with `uv run pytest tests/otutil/unit/tools/test_quota.py -m "unit and tools"` — fully offline; any live HTTP attempt in unit tests is a defect.
- [ ] 7.2 Run relevant tool-pack tests with `uv run pytest tests/otutil/unit/tools -m "unit and tools"`.
- [ ] 7.3 `uv run python scripts/check_docs_registry.py` passes (proves the docsgen registration).
- [ ] 7.4 Run `just check` before marking the change complete.
- [ ] 7.5 `rg -rn "shell=True|subprocess" src/otutil/tools/quota.py src/otutil/tools/_quota/` returns nothing (no CLI shell-outs / terminal scraping).
- [ ] 7.6 `rg -n "sk-ant-|Bearer [A-Za-z0-9]|eyJ[A-Za-z0-9_-]{20,}" src/otutil/tools/_quota/ tests/otutil/unit/tools/ docs/reference/tools/quota.md` returns nothing (no real tokens/JWTs in code, fixtures, or docs — fixtures contain only `REDACTED-*` placeholders).
- [ ] 7.7 Manual: `__onetool ot.packs(pattern='quota')` shows the pack with its real description (not "(no description)"), and the generated help URL for the pack resolves (no 404).
- [ ] 7.8 Manual on macOS: `quota.usage(provider='claude')` finds credentials via Keychain with no `~/.claude/.credentials.json` present; `quota.usage(provider='codex')` works against `~/.codex/auth.json`; returned payloads contain no token material.

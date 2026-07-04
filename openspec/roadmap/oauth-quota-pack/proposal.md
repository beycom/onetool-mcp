## Why

Developers using Claude Code and OpenAI Codex subscriptions need a local MCP tool that reports how much subscription quota remains, when quota windows reset, and whether current usage is ahead of or behind the remaining time in the window. Existing references show this data can be read from authenticated OAuth/session state, but OneTool does not currently expose it.

## What Changes

- Add a new `quota` MCP tool pack for subscription usage reporting.
- Support Claude Code OAuth subscription usage and OpenAI Codex OAuth subscription usage.
- Reuse local authenticated state where possible, without requiring API keys and without scraping terminal output.
- Normalize provider responses into common usage windows for session and weekly quota.
- Add tokenmax-style guidance that compares quota remaining against time remaining.
- Add pack configuration for provider enablement, native credential paths, endpoint URLs, request timeouts, cache TTL, minimum polling intervals, and tokenmax thresholds.
- Add user-facing reference documentation for the pack, including configuration, examples, requirements, and upstream/reference attribution.

## Capabilities

### New Capabilities

- `oauth-quota-pack`: MCP tools for Claude Code and OpenAI Codex OAuth subscription quota snapshots, reset times, cache-aware polling, and tokenmax guidance.

### Modified Capabilities

- None.

## Impact

- Affected code:
  - `src/otutil/tools/quota.py` (with `pack = "quota"`, `doc_slug = "quota"`, no alias — mem/db/arch precedent)
  - `src/otutil/tools/_quota/`
  - `tests/otutil/unit/tools/test_quota.py` + sanitized provider fixtures
  - `docs/reference/tools/quota.md`
- New-pack registration surface (all required — a pack missing these loads but is half-invisible):
  - `src/ot/config/global_templates/prompts.yaml` `packs:` entry (else `ot.packs()` shows "(no description)")
  - `src/otdev/docsgen/metadata.py` `PACK_DOCS` row (feeds `DOC_PATH_BY_PACK`/`EXTRA_BY_PACK`; `scripts/check_docs_registry.py` gates it)
  - `mkdocs.yml` nav entry matching `doc_slug` exactly (p18 lesson: mismatch = 404 help links)
  - README pack table row; regenerated `docs/reference/tools/tool-index.md` via `just docs-sync`
- Affected APIs:
  - New MCP pack namespace `quota`
  - New public tool functions `quota.usage()`, `quota.tokenmax()`, `quota.summary()`, `quota.config()`
- Affected configuration:
  - New typed `tools.quota` configuration in `onetool.yaml`
  - No `secrets.yaml` token source; provider OAuth tokens stay in provider-owned native auth stores.
- Dependencies:
  - `httpx`, Pydantic, and `keyring` are already present in the base dependencies; use `keyring`
    for the macOS Claude Keychain credential source.
- External service risk:
  - The provider endpoints are unofficial/private and can change, so endpoint URLs, credential paths, cache TTL, and polling controls must be configurable.
- Cross-change coordination (this is wave 9 — post-V3 backlog, implemented after the p1x–p3x set):
  - Rebase over `p21-run-contract-and-command-index` (prompts.yaml is fully rewritten there; the
    generated ot-ref pack map and tool index pick `quota` up on regeneration).
  - Follow `p17-pack-api-consistency` naming conventions (long canonical param names; `max=`-style
    prefixes come free) and the `p12` bounded-cache rule for the snapshot cache.

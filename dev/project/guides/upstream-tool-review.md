# Upstream Tool Review

Repos to check periodically for API changes and new features.

## trafilatura
- **URL:** https://github.com/adbar/trafilatura
- **Last checked:** 2026-04-03
- **Notes:**
  - v2.0.0 (Dec 2024): `bare_extraction()` now returns `Document` — we don't call this, no impact.
  - v1.11.0: added `output_format="html"` — issue filed: `wip/issues/1-new/webfetch-html-output-format.md`
  - v1.12.2: SOCKS proxy support — not adopted (no use case).
  - `with_metadata` default already matches our usage (we pass it explicitly). No action.

## brave-search-mcp-server
- **URL:** https://github.com/brave/brave-search-mcp-server
- **Last checked:** 2026-04-03
- **Notes:**
  - No API changes. Regular dependency security bumps only. Nothing to adopt.

## context7
- **URL:** https://github.com/upstash/context7
- **Last checked:** 2026-04-03
- **Notes:** `/v2/context` now supports `type=txt` param for plain-text output; current impl returns raw dict (see `wip/issues/4-next/context7-doc-txt-type.md`)

## mcp-alchemy
- **URL:** https://github.com/runekaagaard/mcp-alchemy
- **Last checked:** 2026-04-03
- **Notes:**
  - Latest (2025.8.15): pool settings `pool_pre_ping=True`, `pool_recycle=3600` — already in our db.py.
  - No new tools or API changes to adopt.

## excel-mcp-server
- **URL:** https://github.com/haris-musa/excel-mcp-server
- **Last checked:** 2026-04-03
- **Notes:**
  - Dec 2025: added `readOnlyHint`/`destructiveHint` MCP tool safety annotations on all tools.
    Not adopted — would apply to all packs, not just excel; revisit as a cross-cutting concern.
  - Jul/Aug 2025: insert/delete rows & cols, FastMCP compat fix — already have equivalent ops.

## mcp-package-version
- **URL:** https://github.com/sammcj/mcp-package-version (archived — original)
  Active fork: https://github.com/MShekow/package-version-check-mcp
- **Last checked:** 2026-04-03
- **Notes:**
  - Original (sammcj) is archived. Active fork adds Go modules and GitHub Actions support.
  - Go module support not adopted — no current use case; revisit if requested.

## mcp-ripgrep
- **URL:** https://github.com/mcollina/mcp-ripgrep
- **Last checked:** 2026-04-03
- **Notes:**
  - v0.2.0: path became required — our impl already requires it.
  - v0.3.0: fixed external process output contaminating JSON — not applicable (we shell out directly).
  - Nothing to adopt.

## fast-filesystem-mcp
- **URL:** https://github.com/efforthye/fast-filesystem-mcp
- **Last checked:** 2026-04-03
- **Notes:**
  - Oct 2025: `fast_read_multiple_files` — we have equivalent batch read already.
  - Oct 2025: `CREATE_BACKUP_FILES` timestamped backups before writes — not adopted (niche use case).
  - Nothing to adopt.

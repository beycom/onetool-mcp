# OneTool Specifications Index

This document categorizes the current OpenSpec main specifications by component.
Main specs describe the contract built now; proposal history and removed-contract
details belong under `openspec/changes/`, not in this index.

## Naming Conventions

| Pattern | Example | Description |
|---------|---------|-------------|
| `{cli}` | `onetool-cli` | Main spec for a CLI or package area |
| `{api}-{feature}` | `direct-run` | Direct API feature spec |
| `serve-{feature}` | `serve-configuration` | OneTool MCP server feature spec |
| `tool-{name}` | `otutil/tool-brave` | Tool pack spec grouped by source package |
| `_nf-{name}` | `_nf-observability` | Cross-cutting non-functional spec |

## Non-Functional Specs

| Spec | Purpose |
|------|---------|
| [_nf-docs](_nf-docs/spec.md) | Public documentation availability, accuracy, and disclosure |
| [_nf-observability](_nf-observability/spec.md) | Runtime observability, attribution, redaction, and usage visibility |
| [_nf-paths](_nf-paths/spec.md) | Path resolution, storage ownership, and workspace boundaries |

## CLI And Direct APIs

| Spec | Purpose |
|------|---------|
| [onetool-cli](onetool-cli/spec.md) | `onetool` CLI runtime, init, and knowledge-base commands |
| [direct-api](direct-api/spec.md) | Authenticated loopback Direct API |
| [direct-run](direct-run/spec.md) | `onetool direct run` client behavior |

## MCP Server Runtime

| Spec | Purpose |
|------|---------|
| [serve-configuration](serve-configuration/spec.md) | Current `onetool.yaml` configuration contract |
| [serve-run-tool](serve-run-tool/spec.md) | The MCP `run(command=...)` tool |
| [serve-code-validation](serve-code-validation/spec.md) | Python syntax and security validation |
| [serve-tools-packages](serve-tools-packages/spec.md) | Tool discovery and pack metadata |
| [serve-prompts](serve-prompts/spec.md) | Server prompts and run invocation guidance |
| [serve-mcp-discoverability](serve-mcp-discoverability/spec.md) | MCP resources and prompts |
| [serve-mcp-proxy](serve-mcp-proxy/spec.md) | External MCP server proxying |
| [serve-output-sanitization](serve-output-sanitization/spec.md) | Output sanitization boundaries |
| [serve-server-management](serve-server-management/spec.md) | Runtime server enable/disable/restart APIs |
| [serve-skills](serve-skills/spec.md) | Runtime skill listing and content retrieval |
| [serve-stats](serve-stats/spec.md) | Runtime statistics reporting |
| [serve-telemetry](serve-telemetry/spec.md) | Anonymous startup telemetry |
| [tool-execution](tool-execution/spec.md) | Extension tool execution worker behavior |
| [tool-ot](tool-ot/spec.md) | Internal `ot.*` runtime helper pack |
| [batch-retry-envelope](batch-retry-envelope/spec.md) | Structured batch retry envelopes |
| [field-level-provenance](field-level-provenance/spec.md) | Field-level provenance output contracts |
| [force-context-dunder](force-context-dunder/spec.md) | `__force_context__` output behavior |
| [search-structured-extraction](search-structured-extraction/spec.md) | Structured extraction for search tools |
| [search-batch-structured-contract](search-batch-structured-contract/spec.md) | Batch structured search contract |

## Browser Utilities

| Spec | Purpose |
|------|---------|
| [tool-chrome-util](otdev/tool-chrome-util/spec.md) | Chrome DevTools annotation utilities |
| [tool-play-util](otdev/tool-play-util/spec.md) | Playwright annotation utilities |

## Knowledge, Context, And Memory

| Spec | Purpose |
|------|---------|
| [ctx](ctx/spec.md) | Smart-context store (`ot_context` / `ctx`) |
| [knowledge-pack](knowledge-pack/spec.md) | Knowledge-base pack (`knowledge` / `kb`) |
| [kb-scrape](kb-scrape/spec.md) | Knowledge-base scraping pipeline |
| [kb-scrape-debug](kb-scrape-debug/spec.md) | Scrape debug artifacts and warnings |
| [localhist-pack](localhist-pack/spec.md) | Local file history pack |
| [tool-mem](ottools/tool-mem/spec.md) | Persistent agent memory pack |

## Core Built-In Tool Packs

| Spec | Purpose |
|------|---------|
| [tool-caveman](ottools/tool-caveman/spec.md) | Text compaction, expansion, and command-queue input |
| [tool-forge](ottools/tool-forge/spec.md) | Extension scaffolding and validation |
| [tool-image](ottools/tool-image/spec.md) | Image loading, querying, and lifecycle management |
| [tool-llm](ottools/tool-llm/spec.md) | LLM-powered data transformation |
| [tool-secrets](ottools/tool-secrets/spec.md) | Age-encrypted secrets management |
| [tool-timer](ottools/tool-timer/spec.md) | Named stopwatch timers |

## Domain Tools (`[util]` Extra)

| Spec | Purpose |
|------|---------|
| [tool-brave](otutil/tool-brave/spec.md) | Brave Search API tools |
| [tool-convert](otutil/tool-convert/spec.md) | Document conversion tools |
| [tool-excel](otutil/tool-excel/spec.md) | Excel workbook operations |
| [tool-file](otutil/tool-file/spec.md) | File operations |
| [tool-ground](otutil/tool-ground/spec.md) | Gemini grounding search tools |
| [tool-tavily](otutil/tool-tavily/spec.md) | Tavily search and extraction tools |

## Domain Tools (`[dev]` Extra)

| Spec | Purpose |
|------|---------|
| [tool-arch-model-centric-rendering](otdev/tool-arch-model-centric-rendering/spec.md) | Architecture model import, validation, export, and rendering |
| [tool-context7](otdev/tool-context7/spec.md) | Context7 documentation lookup |
| [tool-db](otdev/tool-db/spec.md) | SQL database introspection and querying |
| [tool-diagram](otdev/tool-diagram/spec.md) | Diagram generation and rendering |
| [tool-excalidraw](otdev/tool-excalidraw/spec.md) | Whiteboard drawing pack |
| [whiteboard-session-state](whiteboard-session-state/spec.md) | Whiteboard session persistence |
| [tool-package](otdev/tool-package/spec.md) | Package version and dependency checks |
| [tool-ripgrep](otdev/tool-ripgrep/spec.md) | Ripgrep-backed search tools |
| [tool-webfetch](otdev/tool-webfetch/spec.md) | Web content extraction |

## Spec Count Summary

| Category | Count |
|----------|-------|
| Non-Functional | 3 |
| CLI And Direct APIs | 3 |
| MCP Server Runtime | 19 |
| Browser Utilities | 2 |
| Knowledge, Context, And Memory | 6 |
| Core Built-In Tool Packs | 6 |
| Domain Tools `[util]` | 6 |
| Domain Tools `[dev]` | 9 |
| **Total** | **54** |

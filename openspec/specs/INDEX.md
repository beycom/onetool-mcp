# OneTool Specifications Index

This document categorizes all OpenSpec specifications by component.

## Naming Conventions

Spec folder names follow these patterns:

| Pattern | Example | Description |
|---------|---------|-------------|
| `{cli}` | `bench` | Main spec for a CLI (maps to `ot-{cli}`) |
| `{cli}-{feature}` | `bench-config` | CLI feature spec (extracted from main spec) |
| `serve-{feature}` | `serve-configuration` | MCP server (`onetool`) feature spec |
| `tool-{name}` | `tool-brave` | Built-in tool spec |
| `_nf-{name}` | `_nf-observability` | Non-functional / cross-cutting spec (prefixed to sort together) |

---

## Non-Functional Specs

Cross-cutting infrastructure and conventions used across multiple components. Prefixed with `_nf-` to group together in directory listings.

| Spec | Purpose |
|------|---------|
| [_nf-observability](_nf-observability/spec.md) | Unified logging: LogSpan, token/cost tracking, MCP/tool logging |
| [_nf-conventions](_nf-conventions/spec.md) | Common tool patterns: logging, errors, API keys, docstrings |
| [_nf-testing](_nf-testing/spec.md) | Test markers, fixtures, CI integration |
| [_nf-paths](_nf-paths/spec.md) | Path resolution, OT_CWD, config-relative paths |
| [_nf-docs](_nf-docs/spec.md) | Documentation structure and requirements |

---

## onetool CLI

The main CLI for configuration management.

| Spec | Purpose |
|------|---------|
| [onetool-cli](onetool-cli/spec.md) | MCP server entry point, config management (`init`), and knowledge base management (`kb`) |

---

## onetool (MCP Server)

The MCP server that exposes tools for LLM code execution.

### Core Server

| Spec | Purpose |
|------|---------|
| [serve-configuration](serve-configuration/spec.md) | YAML config, tool settings, MCP proxy config |
| [serve-run-tool](serve-run-tool/spec.md) | The `run()` tool for code execution |
| [serve-code-validation](serve-code-validation/spec.md) | Python syntax/security validation |
| [serve-tools-packages](serve-tools-packages/spec.md) | AST-based tool auto-discovery |
| [serve-prompts](serve-prompts/spec.md) | System prompts and trigger documentation |
| [serve-mcp-discoverability](serve-mcp-discoverability/spec.md) | MCP resources and prompts |
| [serve-mcp-proxy](serve-mcp-proxy/spec.md) | External MCP server proxying |
| [serve-output-sanitization](serve-output-sanitization/spec.md) | Sanitize tool outputs to protect against indirect prompt injection |
| [serve-server-management](serve-server-management/spec.md) | `ot.server()` API: list, enable, disable, restart proxy servers at runtime |
| [serve-skills](serve-skills/spec.md) | `ot.skills()` API: list and retrieve bundled skill content at runtime |
| [serve-stats](serve-stats/spec.md) | Statistics and metrics tracking |
| [serve-telemetry](serve-telemetry/spec.md) | Anonymous usage telemetry via PostHog (opt-out, server-start events) |

### Tool Infrastructure

| Spec | Purpose |
|------|---------|
| [tool-execution](tool-execution/spec.md) | Worker subprocess execution, JSON-RPC |

### Built-in Tools (core)

| Spec | Purpose |
|------|---------|
| [ctx](ctx/spec.md) | Smart-context store backed by flat files (`ot_context` / `ctx` pack) |
| [tool-ot](tool-ot/spec.md) | Internal `ot.*` pack (tools, config, health, version) |

### Built-in Tools (`ottools`)

| Spec | Purpose |
|------|---------|
| [tool-devtools-annotation](ottools/tool-devtools-annotation/spec.md) | Chrome DevTools inject.js annotation system |
| [tool-devtools-util](ottools/tool-devtools-util/spec.md) | Chrome DevTools automation utilities |
| [tool-forge](ottools/tool-forge/spec.md) | Extension scaffolding and skill installation |
| [tool-caveman](ottools/tool-caveman/spec.md) | LLM-powered text compaction, expansion, and command-queue input (`ot_caveman` / `cm` pack) |
| [tool-image](ottools/tool-image/spec.md) | Image loading, querying, and lifecycle management (`ot_image` pack) |
| [tool-llm](ottools/tool-llm/spec.md) | LLM-powered data transformation |
| [tool-mem](ottools/tool-mem/spec.md) | Persistent agent memory with semantic search |
| [tool-secrets](ottools/tool-secrets/spec.md) | Age-encrypted secrets management |
| [tool-timer](ottools/tool-timer/spec.md) | Named stopwatch timers |
| [knowledge-pack](knowledge-pack/spec.md) | Retrieval-augmented knowledge base with FTS5 and vector search (`knowledge` / `kb` pack) |

### Domain Tools (`[util]` extra)

| Spec | Purpose |
|------|---------|
| [tool-brave](otutil/tool-brave/spec.md) | Brave Search API (web, news, local, image, video) |
| [tool-convert](otutil/tool-convert/spec.md) | Format conversion (PDF, Word, PowerPoint, Excel) |
| [tool-excel](otutil/tool-excel/spec.md) | Excel workbook operations |
| [tool-file](otutil/tool-file/spec.md) | File operations |
| [tool-ground](otutil/tool-ground/spec.md) | Google grounding via Gemini API |
| [tool-tavily](otutil/tool-tavily/spec.md) | AI-powered web search and deep research via Tavily API |
| [kb-scrape-debug](kb-scrape-debug/spec.md) | `--debug` artifacts and per-run config threshold warnings for `onetool kb scrape` |
| [kb-scrape](kb-scrape/spec.md) | Knowledge base scraping pipeline |

### Domain Tools (`[dev]` extra)

| Spec | Purpose |
|------|---------|
| [aws-pack](aws-pack/spec.md) | AWS tool pack: credential management, identity queries, ARN utilities, AWS MCP sub-servers |
| [tool-context7](otdev/tool-context7/spec.md) | Context7 library documentation API |
| [tool-chat-ops](otdev/tool-chat-ops/spec.md) | Chat telemetry ingest, projections, and reporting |
| [tool-db](otdev/tool-db/spec.md) | SQL database queries via SQLAlchemy |
| [tool-diagram](otdev/tool-diagram/spec.md) | Diagram generation |
| [tool-excalidraw](otdev/tool-excalidraw/spec.md) | Live diagram drawing on excalidraw.com via pydoll (Chrome CDP) (`whiteboard` pack, short alias `wb`) |
| [tool-package](otdev/tool-package/spec.md) | Package version checks (npm, PyPI, OpenRouter) |
| [tool-ripgrep](otdev/tool-ripgrep/spec.md) | Text/regex search via ripgrep |
| [tool-webfetch](otdev/tool-webfetch/spec.md) | Web content extraction via trafilatura |

---

## bench (Benchmark Harness)

CLI for testing and benchmarking MCP servers.

| Spec | Purpose |
|------|---------|
| [bench](bench/spec.md) | Core benchmark structure and conventions (overview) |
| [bench-config](bench-config/spec.md) | YAML configuration, server connections, secrets |
| [bench-evaluators](bench-evaluators/spec.md) | Named evaluators, deterministic and LLM-as-judge |
| [bench-tasks](bench-tasks/spec.md) | Scenarios, task types, multi-prompt tasks |
| [bench-metrics](bench-metrics/spec.md) | Per-call metrics, context growth analysis |
| [bench-csv](bench-csv/spec.md) | CSV results export |
| [bench-tui](bench-tui/spec.md) | TUI favorites mode, harness config file |
| [bench-logging](bench-logging/spec.md) | CLI output, verbose/trace modes, console reporter |

---

## Spec Count Summary

| Category | Count |
|----------|-------|
| Non-Functional | 5 |
| onetool CLI | 1 |
| onetool Core | 12 |
| Tool Infrastructure | 1 |
| Built-in Tools (core) | 2 |
| Built-in Tools (ottools) | 9 |
| Domain Tools [util] | 8 |
| Domain Tools [dev] | 9 |
| bench | 8 |
| **Total** | **55** |

---

## Archived Specs

Specs that have been consolidated into other specs:

- `serve-observability` → consolidated into [_nf-observability](_nf-observability/spec.md)
- `tool-observability` → consolidated into [_nf-observability](_nf-observability/spec.md)
- `bench-observability` → split into [_nf-observability](_nf-observability/spec.md) and [bench-logging](bench-logging/spec.md)
- `tool-internal` → consolidated into [tool-ot](tool-ot/spec.md) and [_nf-conventions](_nf-conventions/spec.md); spec deleted
- `tool-info` → consolidated into [tool-ot](tool-ot/spec.md)
- `observability` → renamed to [_nf-observability](_nf-observability/spec.md)
- `tool-conventions` → renamed to [_nf-conventions](_nf-conventions/spec.md)
- `testing` → renamed to [_nf-testing](_nf-testing/spec.md)
- `paths` → renamed to [_nf-paths](_nf-paths/spec.md)
- `docs` → renamed to [_nf-docs](_nf-docs/spec.md)
- `tool-brave-search` → renamed to [tool-brave](otutil/tool-brave/spec.md)
- `tool-grounding-search` → renamed to [tool-ground](otutil/tool-ground/spec.md)
- `tool-transform` → renamed to [tool-llm](ottools/tool-llm/spec.md)
- `tool-web-fetch` → renamed to [tool-web](otdev/tool-web/spec.md)
- `tool-web` → renamed to [tool-webfetch](otdev/tool-webfetch/spec.md)
- `tool-sdk` → removed (extensions use `ot.*` imports directly)
- `kb-scrape-dry-run` → removed (feature replaced by `--debug`; requirements covered in `knowledge-pack/spec.md` and `onetool-cli/spec.md`)
- `changes/add-excalidraw-pack` → archived into [tool-excalidraw](otdev/tool-excalidraw/spec.md) (spec updated to match final implementation: pack renamed `wb`, tools renamed, file format changed, new tools added)
- `changes/excalidraw-ascii-note` → archived into [tool-excalidraw](otdev/tool-excalidraw/spec.md) (note tool requirements merged; `Swim` type replaced by `seq`)

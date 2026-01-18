# OneTool Specifications Index

This document categorizes all OpenSpec specifications by component.

## Naming Conventions

Spec folder names follow these patterns:

| Pattern | Example | Description |
|---------|---------|-------------|
| `{cli}` | `bench`, `browse` | Main spec for a CLI (maps to `ot-{cli}`) |
| `serve-{feature}` | `serve-configuration` | MCP server (`ot-serve`) feature spec |
| `tool-{name}` | `tool-brave-search` | Built-in tool spec |
| `{feature}` | `observability` | Cross-cutting/shared spec |

---

## Cross-Cutting Specs

Shared infrastructure and conventions used across multiple components.

| Spec | Purpose |
|------|---------|
| [observability](observability/spec.md) | Unified logging: LogSpan, token/cost tracking, MCP/CLI/tool logging |
| [tool-conventions](tool-conventions/spec.md) | Common tool patterns: logging, errors, API keys, docstrings |
| [testing](testing/spec.md) | Test markers, fixtures, CI integration |
| [paths](paths/spec.md) | Path resolution, OT_CWD, config-relative paths |
| [docs](docs/spec.md) | Documentation structure and requirements |

---

## onetool CLI

The main CLI for configuration management.

| Spec | Purpose |
|------|---------|
| [onetool-cli](onetool-cli/spec.md) | Config upgrade, dependency check, config display |

---

## ot-serve (MCP Server)

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

### Tool Infrastructure

| Spec | Purpose |
|------|---------|
| [tool-execution](tool-execution/spec.md) | Worker subprocess execution, JSON-RPC |
| [tool-sdk](tool-sdk/spec.md) | SDK for building worker tools |
| [tool-management](tool-management/spec.md) | Tool install/remove/update |

### Built-in Tools

| Spec | Purpose |
|------|---------|
| [tool-ot](tool-ot/spec.md) | Internal `ot.*` namespace (tools, config, health, push) |
| [tool-brave-search](tool-brave-search/spec.md) | Brave Search API (web, news, local, image, video) |
| [tool-context7](tool-context7/spec.md) | Context7 library documentation API |
| [tool-grounding-search](tool-grounding-search/spec.md) | Google grounding via Gemini API |
| [tool-code-search](tool-code-search/spec.md) | Semantic code search via ChunkHound |
| [tool-web-fetch](tool-web-fetch/spec.md) | Web content extraction via trafilatura |
| [tool-transform](tool-transform/spec.md) | LLM-powered data transformation |
| [tool-db](tool-db/spec.md) | SQL database queries via SQLAlchemy |
| [tool-ripgrep](tool-ripgrep/spec.md) | Text/regex search via ripgrep |
| [tool-excel](tool-excel/spec.md) | Excel workbook operations |
| [tool-package](tool-package/spec.md) | Package version checks (npm, PyPI, OpenRouter) |
| [tool-page-view](tool-page-view/spec.md) | Browse session capture analysis |
| [tool-msg](tool-msg/spec.md) | Message publishing to topic files |

---

## ot-bench (Benchmark Harness)

CLI for testing and benchmarking MCP servers.

| Spec | Purpose |
|------|---------|
| [bench](bench/spec.md) | Benchmark config, scenarios, evaluators |

---

## ot-browse (Browser Inspector)

Standalone CLI for browser inspection and debugging.

| Spec | Purpose |
|------|---------|
| [browse](browse/spec.md) | Browser inspector, element annotation, capture |

---

## Spec Count Summary

| Category | Count |
|----------|-------|
| Cross-Cutting | 5 |
| onetool CLI | 1 |
| ot-serve Core | 7 |
| Tool Infrastructure | 3 |
| Built-in Tools | 13 |
| ot-bench | 1 |
| ot-browse | 1 |
| **Total** | **31** |

---

## Archived Specs

Specs that have been consolidated into other specs:

- `serve-observability` → consolidated into [observability](observability/spec.md)
- `tool-observability` → consolidated into [observability](observability/spec.md)
- `bench-observability` → consolidated into [observability](observability/spec.md)
- `browse-observability` → consolidated into [observability](observability/spec.md)
- `tool-internal` → consolidated into [tool-ot](tool-ot/spec.md)
- `tool-info` → consolidated into [tool-ot](tool-ot/spec.md)

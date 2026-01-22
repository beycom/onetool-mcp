# OneTool Specifications Index

This document categorizes all OpenSpec specifications by component.

## Naming Conventions

Spec folder names follow these patterns:

| Pattern | Example | Description |
|---------|---------|-------------|
| `{cli}` | `bench`, `browse` | Main spec for a CLI (maps to `ot-{cli}`) |
| `{cli}-{feature}` | `bench-config` | CLI feature spec (extracted from main spec) |
| `serve-{feature}` | `serve-configuration` | MCP server (`ot-serve`) feature spec |
| `tool-{name}` | `tool-brave-search` | Built-in tool spec |
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
| [serve-stats](serve-stats/spec.md) | Statistics and metrics tracking |

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
| [tool-file](tool-file/spec.md) | File operations |
| [tool-diagram](tool-diagram/spec.md) | Diagram generation |
| [tool-convert](tool-convert/spec.md) | Format conversion |

---

## ot-bench (Benchmark Harness)

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

## ot-browse (Browser Inspector)

Standalone CLI for browser inspection and debugging.

| Spec | Purpose |
|------|---------|
| [browse](browse/spec.md) | Browser inspector, element annotation, capture |
| [browse-logging](browse-logging/spec.md) | Session, navigation, and interaction logging |

---

## Spec Count Summary

| Category | Count |
|----------|-------|
| Non-Functional | 5 |
| onetool CLI | 1 |
| ot-serve Core | 8 |
| Tool Infrastructure | 3 |
| Built-in Tools | 16 |
| ot-bench | 8 |
| ot-browse | 2 |
| **Total** | **43** |

---

## Archived Specs

Specs that have been consolidated into other specs:

- `serve-observability` → consolidated into [_nf-observability](_nf-observability/spec.md)
- `tool-observability` → consolidated into [_nf-observability](_nf-observability/spec.md)
- `bench-observability` → split into [_nf-observability](_nf-observability/spec.md) and [bench-logging](bench-logging/spec.md)
- `browse-observability` → split into [_nf-observability](_nf-observability/spec.md) and [browse-logging](browse-logging/spec.md)
- `tool-internal` → consolidated into [tool-ot](tool-ot/spec.md)
- `tool-info` → consolidated into [tool-ot](tool-ot/spec.md)
- `observability` → renamed to [_nf-observability](_nf-observability/spec.md)
- `tool-conventions` → renamed to [_nf-conventions](_nf-conventions/spec.md)
- `testing` → renamed to [_nf-testing](_nf-testing/spec.md)
- `paths` → renamed to [_nf-paths](_nf-paths/spec.md)
- `docs` → renamed to [_nf-docs](_nf-docs/spec.md)

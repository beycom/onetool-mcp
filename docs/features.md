# What's in OneTool?

Everything you need to build powerful AI agent integrations without burning your context window.

---

## Hero Features

### 98.7% Token Savings

Stop context rot. MCP servers burn 55K-150K tokens before you start. OneTool uses ~2K tokens. Same accuracy, 10x lower cost.

[Learn more](intro/index.md)

### Code Execution Model

Write Python, not tool definitions. `__ot brave.search(query="AI")` - you see exactly what runs. No tool-selection guessing.

[Learn more](guides/explicit-calls.md)

---

## Developer Experience

### Explicit Tool Calls

Five trigger prefixes, three invocation styles. Deterministic execution - the agent generates code you can read before it runs.

[Learn more](guides/explicit-calls.md)

### Powerful Snippets

Reusable code templates with Jinja2 substitution. Define once, invoke anywhere with `$snippet_name`.

[Learn more](getting-started/configuration.md#snippets)

### Aliases

Short names for common tools. `ws` instead of `brave.web_search`. Configure in YAML.

[Learn more](reference/tools/ot.md#ot-aliases)

---

## Built-in Tools

### 15 Packs, 90+ Tools

Search, web, database, file ops, diagrams, conversions, and more. Ready to use out of the box.

[Browse all tools](reference/tools/index.md)

### Smart Tools

LLM-powered transformation. Pipe any output through AI for extraction, summarization, or reformatting.

[Learn more](reference/tools/transform.md)

### Web & Search

Brave Search (web, news, local, images, video), Google Grounded Search, Firecrawl scraping.

[Learn more](reference/tools/brave-search.md)

### Code & Docs

Context7 library docs, semantic code search, lightning-fast ripgrep.

[Learn more](reference/tools/code-search.md)

### Data & Files

SQL queries (any database), Excel manipulation, document conversion (PDF/Word/PPT to Markdown).

[Learn more](reference/tools/database.md)

---

## Configuration

### Single YAML Config

One well-structured file. Global and project scopes. Three-tier inheritance (bundled → global → project).

[Learn more](getting-started/configuration.md)

### Secrets Management

Isolated `secrets.yaml` (gitignored). Environment variable expansion. Never logged or exposed.

[Learn more](getting-started/configuration.md#secrets)

### Per-Tool Settings

Timeouts, limits, models - configure each tool independently. Validation at load time.

[Learn more](getting-started/configuration.md#tools-configuration)

---

## Security

### AST Code Validation

All code validated before execution. Blocks `exec`, `eval`, `subprocess`. Warns on risky patterns. ~1ms overhead.

[Learn more](getting-started/security.md)

### Configurable Policies

Four-tier system: Allow, Ask, Warn, Block. Fine-grained control with fnmatch patterns.

[Learn more](getting-started/security.md#configurable-policies)

### Path Boundaries

File operations constrained to allowed directories. Symlink resolution. Sensitive path exclusions.

[Learn more](getting-started/security.md#path-boundaries)

---

## Extensibility

### Drop-in Tools

One file, one pack. No registration, no configuration. Drop a Python file, restart, call your functions.

[Learn more](extending/creating-tools.md)

### Scaffold CLI

`scaffold.create()` - generate new extensions from templates. Project or global scope.

[Learn more](extending/creating-tools.md)

### Worker Isolation

Tools with dependencies run in isolated subprocesses via PEP 723. Clean process state.

[Learn more](extending/creating-tools.md#worker-tools)

### Plugin Architecture

Build tools in separate repositories. Local dev with `.onetool/` config. Share via `tools_dir` glob patterns.

[Learn more](extending/plugins.md)

### MCP Server Proxy

Wrap existing MCP servers through OneTool. Get token savings while using any MCP server.

[Learn more](getting-started/configuration.md#external-mcp-servers)

---

## Testing & Benchmarking

### ot-bench Harness

Real agent + MCP server testing. Define tasks in YAML, get objective metrics: token counts, costs, accuracy scores, timing.

[Learn more](reference/cli/ot-bench.md)

### Multi-Prompt Tasks

Sequential prompt chains with `---PROMPT---` delimiter. Conversation history accumulates. Perfect for complex workflows.

[Learn more](reference/cli/ot-bench.md#multi-prompt-tasks)

### AI Evaluators

LLM-powered evaluation with customizable prompts. Compare baseline vs OneTool accuracy side-by-side.

[Learn more](reference/cli/ot-bench.md)

---

## Observability

### Structured Logging

LogSpan context manager with automatic duration and status. Loguru-based with file rotation.

[Learn more](extending/logging.md)

### Runtime Statistics

Track tool calls, success rates, context saved, cost estimates. Filter by period or tool. HTML reports.

[Learn more](reference/tools/ot.md#ot-stats)

### Safe Logging

Automatic credential sanitization. Field-based truncation. No sensitive data in logs.

[Learn more](extending/logging.md#output-formatting)

---

## Quality & Standards

### 1,000+ Tests

Smoke, unit, integration tiers. Fast CI feedback (~30s smoke tests). Marker-based test organization.

[Learn more](extending/testing.md)

### Built with OpenSpec

Formal change proposal process. Specs define before code. Architecture decisions documented.

### Python Best Practices

Type hints throughout. Ruff formatting and linting. Mypy type checking. Pydantic validation.

[Learn more](extending/index.md)

---

## Tool Packs

| Pack | Tools | Best For |
|------|-------|----------|
| **brave** | `search`, `news`, `local`, `images`, `videos`, `search_batch` | Web search with AI summaries |
| **web** | `fetch`, `fetch_batch`, `extract` | Content extraction for agents |
| **ground** | `search` (Google + Gemini) | Grounded search with sources |
| **context7** | `search`, `docs` | Library documentation |
| **code** | `search` | Semantic code search |
| **ripgrep** | `search`, `files`, `count` | Fast regex file search |
| **llm** | `transform` | AI-powered data transformation |
| **db** | `query`, `schema`, `tables` | SQL database queries |
| **excel** | `create`, `read`, `write`, `formula`, ... | Full Excel control |
| **convert** | `pdf`, `word`, `pptx`, `batch` | Document to Markdown |
| **file** | `read`, `write`, `edit`, `copy`, `move`, `delete` | Secure file operations |
| **package** | `npm`, `pypi`, `openrouter` | Package versions |
| **diagram** | `source`, `render` | Mermaid, PlantUML, D2 diagrams |
| **firecrawl** | `scrape`, `crawl`, `extract` | Web scraping with schemas |
| **ot** | `tools`, `packs`, `config`, `health`, `stats` | Introspection & management |
| **scaffold** | `create`, `templates`, `list_extensions` | Extension scaffolding |

---

## How OneTool Compares

### vs Anthropic's Tool Search Tool

| Aspect | Tool Search Tool | OneTool |
|--------|------------------|---------|
| **Token Reduction** | ~85% (77K → 8.7K) | **98.7%** (150K → 2K) |
| **Approach** | Defer loading, search on demand | Execute code directly - no tool definitions |
| **Search Step** | Required (regex/BM25/embeddings) | **Not needed** - explicit calls |
| **Tool Selection** | Agent still chooses from search results | **Developer controls** - no guessing |
| **Implementation** | Beta API: custom tool type, `defer_loading` flag, beta headers | **Standard MCP** - works today |
| **Adoption** | Requires ecosystem-wide API changes | **Drop-in replacement** |

### vs Docker MCP Gateway

| Aspect | Docker MCP Gateway | OneTool |
|--------|-------------------|---------|
| **Primary Focus** | Operational: containers, security | **Efficiency**: token reduction, cost |
| **Token Overhead** | Standard MCP overhead remains | **98.7% reduction** |
| **Tool Selection** | Agent enumerates and chooses | **Explicit calls** - developer controlled |
| **Setup** | Docker Desktop + MCP Toolkit + GUI config | **Single YAML config** |
| **Tool Catalog** | Limited curated selection | **90+ tools** built-in, extensible |
| **Complexity** | Container orchestration, networking, volumes | **pip install**, done |

**OneTool's core insight:** The agent doesn't need tool definitions - it can write Python.

---

## Get Started

- **[Quickstart](getting-started/quickstart.md)** - Running in 2 minutes
- **[Installation](getting-started/installation.md)** - All platforms
- **[Configuration](getting-started/configuration.md)** - YAML schema

---
hide:
  - navigation
  - toc
---

<h1 class="sr-only">OneTool</h1>

<div class="hero">
<div class="hero__logo" role="img" aria-label="OneTool logo"></div>
<p class="hero__title">OneTool</p>
<p class="hero__tagline">🧿 One MCP for developers - No tool tax, no context rot.<br>100+ tools including Brave, Google, Context7, Excalidraw, Version Checker, Excel, File Ops, Database, Playwright, Chrome DevTools and many more.</p>
<div class="hero__buttons">
<a href="learn/" class="btn btn--primary">Learn OneTool</a>
<a href="reference/" class="btn btn--secondary">Reference</a>
</div>
</div>


!!! tip "OneTool v2 is here"
    **New in v2 — highlights:**

    - :material-draw: **Live whiteboard** — draw diagrams and architecture with a Mermaid-compatible DSL, powered by Excalidraw
    - :material-magnify: **Three search engines** — Brave, Google (Ground), and Tavily; each with batch support, topic filters, and answer summaries
    - :material-eye: **Browser annotations** — highlight page elements and guide users through multi-step workflows via Chrome DevTools or Playwright
    - :material-console: **Interactive setup** — `onetool init` opens a TUI to select exactly the extensions you need; no manual YAML editing to get started
    - :material-file-cog: **Cleaner config** — flat `~/.onetool/` layout, explicit `--config` and `--secrets` flags, and a versioned schema with clear errors
    - :material-lock: **Encrypted secrets** — age-encrypted `secrets.yaml` backed by your OS keychain
    - :material-package-variant: **Leaner install** — optional `[util]` and `[dev]` extras; install only the dependencies you need
    - :material-database: **Smart context store** — `ot_context` (`ctx`); SQLite+FTS5 store; search and navigate large tool outputs without filling context
    - :material-image-search: **Image vision** — `ot_image` (`img`); routes to a cheaper, better vision model; zero host tokens; supports local files, URLs, clipboard, and 8 formats (PNG, JPEG, GIF, WebP, TIFF, HEIC, AVIF, SVG)
    - :material-console: **CLI-first execution** — `onetool direct run --port` bridges shell commands into a running MCP process for agent harnesses

    [:octicons-arrow-right-24: See everything that's new in v2](learn/whats-new-v2.md)

## **The Problem**

### Tool Tax
Each MCP Server consumes between 3K and 30K (looking at you, GitHub MCP!) in tokens **per request**. Every single request.
The maths is brutal: If you're using Claude Opus 4.5 at $5 per million input tokens - 20 days × 10 conversations × 10 messages × 3K tokens = 6M input tokens. You waste approx. **$30 in Tool Tax per MCP Server, per month**.

### Context Rot
And then there's **context rot** -  the phenomenon where the agent's performance degrades as the context window fills ([Chroma Research, 2025](https://research.trychroma.com/context-rot)). Every tool description pushes valuable conversation history out of the context window. Your AI literally **gets dumber as you add more tools**.

## **The Solution**

OneTool is **one MCP server** that exposes tools as a Python API. Instead of reading tool definitions, your agent writes code  - `brave.search(q="react docs")`  - and OneTool runs it.

Configure one MCP Server. Use unlimited tools.

**96% fewer tokens. 30× lower cost. No context rot. 100+ tools, extensible and configurable**

[:octicons-arrow-right-24: Read the full story](about/about-onetool.md)

## Features

<div class="bento" markdown>

<div class="card span-2" markdown>

### :material-chart-line: 96% Token Savings

MCP servers consume 3-30K tokens before you start. OneTool uses ~2K tokens no matter how many tools and MCP servers you add. No tool tax. No context rot. **30× lower cost.**

!!! quote ""
    "Agents scale better by writing code to call tools instead. This reduces the token usage from 150,000 tokens to 2,000 tokens...a cost saving of 98.7%"
     - [Anthropic Engineering](https://www.anthropic.com/engineering/code-execution-with-mcp)

[:octicons-arrow-right-24: See comparison](learn/comparison.md)

</div>

<div class="card" markdown>

### :material-code-braces: Code, Not Tool Calls

Agents are excellent at writing code. OneTool tool calls can be batched, chained, and used just like any other Python function.

[:octicons-arrow-right-24: Learn more](learn/explicit-calls.md)

</div>

<div class="card" markdown>

### :material-eye: Explicit Execution

Write Python, not tool definitions. You see exactly what runs. No more guessing.

```text
__onetool brave.search(q="AI")
```

</div>

<div class="card span-2" markdown>

### :material-puzzle: Forge New Tools

Build new tools as part of the conversation. New tools are just Python functions. Drop a file, get a pack.

[:octicons-arrow-right-24: Create tools](learn/extension-tools.md)

</div>

<div class="card span-2" markdown>

### :material-server-network: MCP Server Proxy

Wrap any existing MCP server. Configure in YAML. Call explicitly - without the Tool Tax. Pre-configured: Chrome DevTools, GitHub.

[:octicons-arrow-right-24: Use other MCP servers](reference/cli/onetool-config.md#external-mcp-servers)

</div>

<div class="card" markdown>

### :material-cog: Great Developer Experience

Snippets with Jinja2. Aliases for common tools. Parameter prefixes (`q` for `query`). Single YAML config.

</div>

<div class="card span-2" markdown>

### :material-file-cog: Configuration

Single, well-structured [YAML config](learn/configuration.md) with global and project scopes. Per-pack settings for timeouts, limits, models.

</div>

<div class="card span-2" markdown>

### :material-console: CLI-First Execution

Run any OneTool pack from the shell through an already-running MCP process.
The MCP-owned direct API keeps loaded config, secrets, proxy connections, and
state in one process. Pipe JSON to scripts, agents, or other tools.

```bash
onetool direct run --port 8765 "ot.packs()" --format json | jq '.[0].name'
```

[:octicons-arrow-right-24: Direct usage guide](learn/direct-usage.md)

</div>

<div class="card" markdown>

### :material-chart-box: Observability

Meta tools for introspection. [Structured logging](learn/extension-tools.md#logging-with-logspan) with LogSpan. [Runtime statistics](reference/tools/ot_core.md#otstats) for costs and success rates.

</div>

<div class="card span-2" markdown>

### :material-package-variant: 100+ Tools

Web Search (Brave, Google), Context7, Version Check, Chrome DevTools, Playwright, Excel, File Ops, Database, Memory and many more.

[:octicons-arrow-right-24: Browse tools](reference/tools/index.md)

</div>

<div class="card span-2" markdown>

### :material-image-search: Image Vision

Routes image analysis to a cheaper, better vision model. Zero tokens charged to your host session. Load from local files, URLs, or clipboard.

Supports PNG, JPEG, GIF, WebP, TIFF, HEIC, AVIF, SVG.

```text
__onetool img.load(img="invoice.png")
__onetool img.ask(img="#inv_01", q="Extract all line items and prices")
__onetool img.clip_ask(q="What does this screenshot show?")  # clipboard shortcut
```

[:octicons-arrow-right-24: ot_image reference](reference/tools/ot_image.md)

</div>

<div class="card span-2" markdown>

### :material-database: Smart Context Store

Persistent SQLite+FTS5 store for large tool outputs. Write once, search many times. Agents build up knowledge across tool calls without burning context window.

```text
__onetool h = ctx.write(content="...", source="research"); ctx.grep(handle=h["handle"], pattern="async error handling")
```

[:octicons-arrow-right-24: ctx reference](reference/tools/ot_context.md)

</div>

<div class="card span-2" markdown>

### :material-robot: Smart Tools

Delegate to cheaper agents. Fetch a page, summarise with Gemini Flash ($0.50/M), pass back to Opus ($5/M). **10× savings.**

[:octicons-arrow-right-24: Smart Tools](reference/tools/ot_llm.md)

</div>

<div class="card span-2" markdown>

### :material-shield-check: Security

Multiple layers built in: isolated [`secrets.yaml`](reference/cli/onetool-config.md#secrets-configuration), [AST validation](learn/security.md#2-allowlist-based-code-validation), [path boundaries](learn/security.md#6-path-boundary-enforcement), [output sanitisation](learn/security.md#9-output-sanitization-prompt-injection-protection).

</div>

<div class="card span-4" markdown>

### :material-check-circle: Engineering Practices

2,000+ tests (smoke, unit, integration). OpenSpec for change proposals - specs before code. Type hints throughout. Ruff + Mypy.

</div>

</div>

---
hide:
  - navigation
  - toc
---

<h1 class="sr-only">OneTool</h1>

<div class="hero">
<div class="hero__logo" role="img" aria-label="OneTool logo"></div>
<p class="hero__title">OneTool</p>
<p class="hero__tagline">🧿 One MCP for developers — no tool tax, no context rot.<br>250+ tools your agent calls as Python code: search, docs, files, databases, diagrams, vision, memory — plus a proxy for every MCP server you already use.</p>
<div class="hero__buttons">
<a href="learn/" class="btn btn--primary">Learn OneTool</a>
<a href="reference/" class="btn btn--secondary">Reference</a>
</div>
</div>


!!! tip "OneTool v3 is here"
    **New in v3 — highlights:**

    - :material-rocket-launch: **One-command install** — a `curl | sh` bootstrap installs uv and OneTool, initialises config, and `onetool init mcp-config` prints ready-to-paste client config for Claude Code, Claude Desktop, Cursor, or VS Code
    - :material-lock: **Guided encrypted secrets** — `onetool init` creates and encrypts `secrets.yaml` in one flow: age encryption, private key in your OS keychain, atomic `0600` writes — safe to inspect, safe to commit
    - :material-school: **ot-ref agent skill** — a standard installable skill (`npx skills add`) that teaches your agent the call conventions, plus a greppable index of all 252 tool signatures that never enters the context window
    - :material-brain: **Memory, upgraded** — BM25 keyword + vector semantic search, per-memory history and rollback, snapshots, file-backed freshness
    - :material-book-open-variant: **Knowledge AI enrichment** — `onetool kb enrich` adds per-chunk LLM summaries that sharpen retrieval
    - :material-draw: **Whiteboard auto-layout** — offline ELK layout engine, named boards on every tool
    - :material-history: **Local history** — Git-backed project snapshots, diff, and restore, independent of your repo
    - :material-shield-check: **Hardened run pipeline** — failures set the MCP error flag, execution never blocks the server, and every recovery hint names the fix

    Breaking changes and the full list: [:octicons-arrow-right-24: Changelog](https://github.com/beycom/onetool-mcp/blob/main/CHANGELOG.md)

## **The Problem**

### Tool Tax
Every MCP server re-sends its tool definitions on every request — 3K to 30K tokens each (looking at you, GitHub MCP!). The maths is brutal: at Claude Opus 4.5's $5 per million input tokens, 20 days × 10 conversations × 10 messages × 3K tokens = 6M input tokens. That's approx. **$30 in tool tax per MCP server, per month** — even if you never use the tools.

### Context Rot
And then there's **context rot** — agent performance degrades as the context window fills ([Chroma Research, 2025](https://research.trychroma.com/context-rot)). Every tool definition pushes conversation history out of the window. Your AI literally **gets dumber as you add more tools**.

## **The Solution**

OneTool is **one MCP server** that exposes tools as a Python API. Instead of reading tool definitions, your agent writes code — `brave.search(query="react docs")` — and OneTool runs it.

Configure one MCP server. Use unlimited tools.

**97% fewer tokens. 30× lower cost. No context rot. 250+ tools, extensible and configurable.**

[:octicons-arrow-right-24: Read the full story](about/about-onetool.md)

## Features

<div class="bento" markdown>

<div class="card span-2" markdown>

### :material-chart-line: 97% Token Savings

MCP servers consume 3–30K tokens before you start. OneTool uses ~2K tokens no matter how many tools and MCP servers you add. No tool tax. No context rot. **30× lower cost.**

!!! quote ""
    "Agents scale better by writing code to call tools instead. This reduces the token usage from 150,000 tokens to 2,000 tokens...a cost saving of 98.7%"
     - [Anthropic Engineering](https://www.anthropic.com/engineering/code-execution-with-mcp)

[:octicons-arrow-right-24: See the measurements](learn/comparison.md)

</div>

<div class="card" markdown>

### :material-code-braces: Code, Not Tool Calls

Agents are excellent at writing code. OneTool calls can be batched, chained, looped, and composed — one request, many tools, no round trips through the model.

[:octicons-arrow-right-24: Learn more](learn/explicit-calls.md)

</div>

<div class="card" markdown>

### :material-eye: Explicit Execution

You see exactly what runs. No tool-selection guessing, no non-deterministic behaviour — reviewable code.

```text
__onetool brave.search(q="AI")
```

</div>

<div class="card span-2" markdown>

### :material-package-variant: 250+ Tools, 28 Packs

Web search (Brave, Google, Tavily), Context7 docs, files, Excel, SQL databases, document→Markdown conversion, ripgrep, package versions, diagrams, vision, memory — curated, configured, ready.

[:octicons-arrow-right-24: Browse all 252 tools](reference/tools/index.md)

</div>

<div class="card span-2" markdown>

### :material-server-network: MCP Server Proxy

Keep every MCP server you already use. Wrap it in YAML, call it explicitly as a Python namespace — without its tool tax. Enable, disable, and restart servers from inside the conversation with `ot_servers`.

[:octicons-arrow-right-24: Use other MCP servers](reference/cli/onetool-config.md#external-mcp-servers)

</div>

<div class="card span-2" markdown>

### :material-hand-heart: Built for How Agents Type

Parameter prefixes (`q=` resolves to `query=`), pack aliases (`wb.` for `whiteboard.`), snake/camel forgiveness on proxied servers, typo suggestions, and Jinja2 snippets. Sloppy calls still land.

</div>

<div class="card span-2" markdown>

### :material-database: Context Economy

Tool *outputs* eat context too. Large results come back as a searchable handle instead of flooding the window — grep it, slice it, or ask questions against it. Partial file reads via `file.toc`/`file.slice`.

```text
__onetool h = ctx.write(content=big_result, source="research"); ctx.grep(handle=h["handle"], pattern="async errors")
```

[:octicons-arrow-right-24: ctx reference](reference/tools/ot_context.md)

</div>

<div class="card span-2" markdown>

### :material-brain: State That Survives the Session

`mem` — persistent memory with semantic + keyword search, history, and rollback. `knowledge` — portable RAG knowledge bases with AI enrichment. `localhist` — Git-backed project snapshots independent of your repo.

[:octicons-arrow-right-24: Memory reference](reference/tools/mem.md)

</div>

<div class="card span-2" markdown>

### :material-image-search: Image Vision

Routes image analysis to a cheaper, better vision model. Zero tokens charged to your host session. Load from local files, URLs, or clipboard — PNG, JPEG, GIF, WebP, TIFF, HEIC, AVIF, SVG.

```text
__onetool img.load(img="invoice.png")
__onetool img.ask(img="#inv_01", q="Extract all line items and prices")
__onetool img.clip_ask(q="What does this screenshot show?")
```

[:octicons-arrow-right-24: ot_image reference](reference/tools/ot_image.md)

</div>

<div class="card span-2" markdown>

### :material-draw: Live Visual Tools

Draw on a live Excalidraw whiteboard with a Mermaid-compatible DSL and offline auto-layout. Render Mermaid, PlantUML, and D2 diagrams. Generate draw.io-editable architecture docs from a spreadsheet.

[:octicons-arrow-right-24: Whiteboard reference](reference/tools/whiteboard.md)

</div>

<div class="card" markdown>

### :material-lock: Encrypted Secrets

`secrets.yaml` values are age-encrypted, keyed from your OS keychain, decrypted transparently at load. Safe to inspect. Safe to commit.

[:octicons-arrow-right-24: Secrets](reference/tools/ot_secrets.md)

</div>

<div class="card" markdown>

### :material-robot: Smart Tools

Delegate to cheaper models. Fetch a page, summarise with Gemini Flash ($0.50/M), pass the result back to Opus ($5/M). **10× savings.**

[:octicons-arrow-right-24: Smart Tools](reference/tools/ot_llm.md)

</div>

<div class="card span-2" markdown>

### :material-console: Dual Runtime: MCP + CLI

The same loaded process serves your agent *and* your shell. Pipe JSON to scripts, agents, and harnesses through the direct API — config, secrets, and proxy connections stay warm.

```bash
onetool direct run --port 8765 "ot.packs()" --format json | jq '.[0].name'
```

[:octicons-arrow-right-24: Direct usage guide](learn/direct-usage.md)

</div>

<div class="card" markdown>

### :material-puzzle: Extend in Conversation

Drop a Python file, get a pack — no registration. Scaffold new tools with `ot_forge` as part of the conversation.

[:octicons-arrow-right-24: Create tools](learn/extension-tools.md)

</div>

<div class="card" markdown>

### :material-shield-check: Security Layers

AST allowlist validation, path boundaries, prompt-injection output sanitisation, encrypted secrets — [defense in depth](learn/security.md) for a tool that executes code.

</div>

<div class="card span-2" markdown>

### :material-chart-box: Observability

Meta tools for introspection. [Structured logging](learn/extension-tools.md#logging-with-logspan) with LogSpan. [Runtime statistics](reference/tools/ot_core.md#otstats) for costs, success rates, and estimated savings.

</div>

<div class="card span-4" markdown>

### :material-check-circle: Engineering Practices

3,000+ tests (smoke, unit, integration). OpenSpec change proposals — specs before code. Type hints throughout. Ruff + Mypy. Generated, drift-checked docs.

</div>

</div>

## Install in 60 Seconds

```bash
curl -LsSf https://onetool.beycom.online/install.sh | sh    # macOS / Linux
irm https://onetool.beycom.online/install.ps1 | iex         # Windows (PowerShell)
```

Then paste the printed MCP config into your client — Claude Code, Claude Desktop, Cursor, or VS Code. All 250+ tools work out of the box.

[:octicons-arrow-right-24: Full installation guide](learn/installation.md)

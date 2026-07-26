# OneTool Brand

Brand identity, messaging architecture, and canonical claims for OneTool.
This document is the source of truth for the homepage (`docs/index.md`) and `README.md` —
when copy there disagrees with this file, this file wins.

Refreshed: 2026-07-12 (v3.0.0 surface).

---

## Documents

| Document | Purpose |
|----------|---------|
| **This file** | Identity, positioning, differentiators, taglines, canonical stats |
| [terminology.md](terminology.md) | Terminology style guide |
| [claims.md](claims.md) | Benchmark evidence for marketing claims |
| [external-references.md](external-references.md) | External references and resources |

For user-facing tool pack descriptions, use [docs/reference/tools/index.md](../../../docs/reference/tools/index.md).

---

## Brand Identity

### Internal brand

```text
One tool to rule them all
```

### External pitch

```text
🧿 One MCP for developers — no tool tax, no context rot.
250+ tools your agent calls as Python code: search, docs, files, databases,
diagrams, vision, memory — plus a proxy for every MCP server you already use.
```

### Positioning statement

For developers running AI coding agents, OneTool is the single MCP server that
replaces all the others: agents call tools by writing Python code instead of
reading tool definitions, cutting input tokens ~97% while giving them a
250-tool standard library, a context-economy toolkit, and a proxy for existing
MCP servers. Unlike code-mode frameworks (FastMCP) or protocol patches
(Anthropic's Tool Search Tool), OneTool is an installed product — one `curl`
bootstrap, one YAML config, working tools in minutes.

### Audience

Primary: individual developers using Claude Code / Cursor / Codex-style agents
daily, feeling token cost and context degradation. Secondary: agent-harness
builders (direct CLI/API), and teams wanting curated, auditable tool surfaces.

---

## The Two Pillars

Messaging leads with Pillar 1 (the hook) and lands Pillar 2 (the moat).
Historic copy is almost entirely Pillar 1; the v3 surface justifies both.

### Pillar 1 — Stop paying the tool tax (the hook)

Every MCP server re-sends its tool definitions on every request: 3K–30K tokens
each, ~$30/server/month, and measurable context rot. OneTool exposes one `run`
tool; the agent writes `brave.search(query="...")` as code. ~97% fewer input
tokens, ~30× lower cost, and the gap widens with every turn (evidence:
[claims.md](claims.md)).

### Pillar 2 — A full agent toolchain (the moat)

Token savings get users in the door; the toolchain keeps them. OneTool is a
standard library for agents — 28 packs / 250+ curated tools — plus the things
around the tools that no single-purpose MCP server has: context economy,
persistent state, a forgiveness layer, security layers, and a dual MCP+CLI
runtime.

---

## Differentiators

Each row is a claim the homepage/README can make, with its proof point.

| # | Differentiator | One-liner | Proof |
|---|----------------|-----------|-------|
| 1 | **Code, not tool calls** | One MCP tool; agents write Python — batch, chain, loop, compose | ~97% token cut, 40× fewer input tokens ([claims.md](claims.md)); Anthropic's own code-execution article |
| 1b | **Explicit tool control** | `__onetool brave.search(query="…")` — you see exactly what runs; no tool-selection guessing, deterministic and reviewable | Canonical trigger; any MCP server callable as a Python namespace with `server=` overrides |
| 2 | **Installed product, not framework** | `curl … \| sh`, `onetool init`, paste MCP config — done. FastMCP Code Mode is an ingredient you'd have to build a server around | Install bootstrap, init TUI, `init mcp-config --client claude-code` |
| 3 | **250+ curated tools, 28 packs** | Search (Brave/Google/Tavily/Context7), files, Excel, DB, document→Markdown conversion, diagrams, ripgrep, package versions, architecture models | Generated tool index (`docs/reference/tools/`) |
| 4 | **Context economy** | Tool *outputs* eat context too — OneTool attacks context spend end to end, not just definitions | `ctx` handles for large outputs; `file.toc/slice` partial reads; `ot_image` vision on a cheap model (zero host tokens); `ot_llm` delegation (10× savings) |
| 5 | **Agent-native state** | Memory and knowledge that survive the session | `mem` (hybrid FTS5 + sqlite-vec search, history/rollback, file-backed freshness), `knowledge` (RAG with AI enrichment), `localhist` (project snapshots) |
| 6 | **MCP server proxy** | Keep every MCP server you already use — call it explicitly, without its tool tax | YAML `servers:` block; name aliasing; `ot_servers` enable/disable/restart from the agent loop |
| 7 | **Forgiveness layer (DX)** | Built for how agents actually type | Param prefix matching (`q=` → `query`), pack aliases (`br`, `wb`, `ctx`, `img`), Jinja2 snippets, `ot.help` ask mode, recovery guidance that names the fix |
| 8 | **ot-ref agent skill** | Agents learn OneTool via a standard installable skill with a greppable command index | `npx skills add … --skill ot-ref` |
| 9 | **Dual runtime: MCP + CLI** | Same loaded process from your agent *and* your shell/scripts/harnesses | `onetool direct run`, discovery files, HTTP transport for containers |
| 10 | **Extensible in-conversation** | Drop a `.py` file, get a pack; scaffold with `ot_forge`; share infra via the `otpack` library | 3-minute Wikipedia-tool demo video |
| 11 | **Layered security** | AST allowlist validation, path boundaries, prompt-injection output sanitisation, age-encrypted secrets — defense in depth for a tool that executes code | `docs/learn/security.md`; `security-model-docs` spec. Internal rule: sell the concrete layers; never claim a sandbox, and never use "honestly framed/documented" as copy |
| 12 | **Live visual tools** | Excalidraw whiteboard with a Mermaid-compatible DSL and offline auto-layout; architecture pack generating draw.io-editable SVG solution docs | `whiteboard`, `arch`, `diagram` packs |
| 13 | **Engineering rigor** | 3,000+ tests, OpenSpec specs-before-code, typed config, generated docs, structured logging + runtime stats (incl. estimated savings) | repo; `ot.stats()` |

### Competitive contrasts (keep these sharp)

- **vs. Anthropic Tool Search Tool** — 85% reduction vs OneTool's 97%; still pays per-lookup and needs client support. OneTool works with any MCP client today.
- **vs. FastMCP Code Mode** — framework capability you'd have to build vs. a product you install. Adopting FastMCP internals is an implementation choice, never a positioning risk: the story is the product, not the plumbing.
- **vs. Docker MCP Gateway** — a proxy that still forwards every tool definition; OneTool collapses them into code.

---

## Taglines

### Short

```text
Don't enumerate tools. Execute code.
```

```text
One MCP server. All your tools. ~2K tokens.
```

### Value proposition

```text
97% fewer tokens. 30× lower cost. 250+ tools.
```

### Pillar 2 lines (new — capability story)

```text
The standard library for AI agents.
```

```text
Token savings get you in the door. The toolchain keeps you.
```

---

## Canonical Stats

Single source of truth for numbers in marketing copy. Regenerate the inventory
with `uv run python scripts/list_tool_inventory.py --output -`; token/cost
figures come from [claims.md](claims.md).

```text
- 28 packs, 253 tools (v3.0.0 tool-index baseline; say "250+ tools" in copy)
- 97% fewer input tokens (47,660 → 1,131 one-shot; 40× at 3 turns)
- 30× lower cost (28×–34× measured; say "30×")
- ~$30 per MCP server per month in tool tax
- ~2K tokens total, regardless of tool count
- 3,000+ tests; OpenSpec-governed; 1 CLI (onetool)
```

Do **not** use: "100+ tools" (stale, undersells), "240+ tools" (drifted),
"96% fewer tokens" (claims.md evidence supports 97% — standardise on 97%),
"1,200+ / 2,000+ tests" (stale).

---

## Message Architecture (homepage & README)

Recommended narrative order — both surfaces follow the same spine, README
compressed:

1. **Hook** — external pitch + value proposition line.
2. **Problem** — tool tax ($30/server/month math) + context rot (Chroma citation). Keep the brutal-math paragraph; it converts.
3. **Solution** — one MCP server, agents write code; Anthropic code-execution quote; canonical stats.
4. **Proof** — comparison table / claims links.
5. **Capability spread (Pillar 2)** — feature bento/table grouped as: Tools (search/files/data/docs), Context economy (`ctx`/`img`/`ot_llm`), State (`mem`/`knowledge`/`localhist`), Visual (`whiteboard`/`arch`/`diagram`), Runtime (proxy/direct CLI/ot-ref skill).
6. **On-ramp** — install bootstrap, `init mcp-config`, ot-ref skill install. Counter the "requires setup" objection by showing the 3-command path.
7. **Extending + proxy** — drop-a-file pack; wrap existing servers.
8. **Trust** — security layers (name the concrete mechanisms, no sandbox claims), engineering rigor, telemetry opt-out, GPLv3.

### Proof assets (demos)

Scripted, replayable walkthroughs (`docs/learn/demos/`, driven via `onetool
direct run`) — each sells one undersold capability. Lead candidates for
homepage embeds:

- *Forgiveness demo* — sloppy calls that all work: `mem.search(q=)` prefix, `wb.`/`excalidraw.` aliases, proxy camelCase, typo → did-you-mean.
- *Codebase → live whiteboard* — ripgrep/file exploration drawing architecture on the Excalidraw canvas in real time.
- *"We just committed our secrets file"* — guided init → encrypt → commit `age1enc:` secrets.yaml safely; keychain decrypts on boot.
- *One tool, 300 fewer schemas* — connect, `ot.packs()`, first call, `ot.stats()` token count.
- *The 40KB result that never touched context* — big fetch → ctx handle → `ctx.toc`/`ctx.ask` → `mem.write`.

### Release context

v3.0.0 is implemented but not yet published (see `wip/release-v3/release-v3-plan.md`).
The homepage and README were rewritten to this messaging on 2026-07-12 and ship
with the v3 announcement. That rewrite replaced the "OneTool v2 is here" banner
(now a v3 banner), the "100+ tools" hero copy, and the stale "SQLite+FTS5"
description of `ctx` (file-backed since 2.2.0).

### Objection handling

| Objection | Response |
|-----------|----------|
| "Setup looks complex" | 3 commands: bootstrap script → `onetool init` → paste MCP config. Everything else is optional depth. |
| "Is executing code safe?" | Layered guardrails (AST allowlist, path boundaries, sanitisation) + every call is visible code you review. Defense in depth, not a sandbox — the docs are explicit about the trust model. |
| "Why not FastMCP Code Mode?" | Framework vs product (see contrasts above). |
| "I already have MCP servers I like" | Keep them — proxy them through OneTool and stop paying their tool tax. |
| "GPLv3?" | Fine for use as a tool/server; only matters if you fork and distribute. |

---

## Short Descriptions

One-liner (GitHub description, PyPI):

```text
🧿 One MCP for developers — no tool tax, no context rot. 250+ tools your agent
calls as Python code, plus a proxy for every MCP server you already use.
```

Paragraph (directories, listings):

```text
OneTool replaces your stack of MCP servers with a single one. Instead of
reading thousands of tokens of tool definitions per request, your agent writes
Python — brave.search(query="…") — against a 250-tool standard library:
web search, files, databases, Excel, document conversion, diagrams, a live
whiteboard, vision, persistent memory, and a knowledge base. Existing MCP
servers plug in through a YAML proxy without their token overhead. Result:
~97% fewer input tokens, ~30× lower cost, no context rot — with encrypted
secrets, AST-validated execution, and a CLI bridge for scripts and harnesses.
```

## GitHub Tags

```text
python, mcp, model-context-protocol, mcp-server, llm, code-execution,
mcp-tools, agents, agent-tools, token-efficiency, context-rot, claude-code
```

---

## Terminology (Quick Reference)

Full guide: [terminology.md](terminology.md)

| Rule | Example |
|------|---------|
| Use "agent" for tool behavior | "The agent generates code" |
| Use "LLM" for model characteristics | "LLM performance degrades" |
| Use "MCP server" not "MCP tool" | "Connect an MCP server" |
| Use "tool definitions" not "schemas" | "Tool definitions consume tokens" |

| Term | Meaning |
|------|---------|
| **tool tax** | Per-request token cost of resent tool definitions |
| **context rot** | Performance degradation from token bloat |
| **context economy** | Keeping tool *outputs* (not just definitions) out of the context window |
| **pack** | Collection of related tools |
| **explicit calls** | Direct tool invocation via code |
| **snippet** | Reusable code template (Jinja2) |
| **handle** | Stable reference to stored large output (`ctx`) or image (`img`) |
| **`__onetool`** | Canonical explicit trigger (v3; `__run` is removed) |

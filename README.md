<p align="center">
  <!-- mcp-name: io.github.beycom/onetool-mcp -->
  <a href="https://github.com/beycom/onetool-mcp">
    <img src="https://raw.githubusercontent.com/beycom/onetool-mcp/main/docs/assets/logo.svg" alt="OneTool" width="80">
  </a>
</p>

<p align="center">
  <strong>🧿 One MCP for developers - no tool tax, no context rot.<br>250+ tools your agent calls as Python code: search, docs, files, databases, diagrams, vision, memory - plus a proxy for every MCP server you already use.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/onetool-mcp/"><img alt="PyPI" src="https://img.shields.io/pypi/v/onetool-mcp"></a>
  <a href="https://github.com/beycom/onetool-mcp/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/license-GPLv3-blue"></a>
  <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/python-3.12%2B-blue"></a>
  <a href="https://github.com/beycom/onetool-mcp/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/beycom/onetool-mcp"></a>
</p>

<p align="center">
  Works with Claude Code, Cursor, Codex - any MCP client
</p>

---

## The Problem

Every MCP server re-sends its tool definitions on every request: **3K-30K tokens each**. Connect 5 servers and you've burned 55K tokens before the conversation starts. Connect 10+ and you're at 100K.

The math is brutal: Claude Opus 4.5 at $5/M input tokens, 20 days × 10 conversations × 10 messages × 3K tokens = **$30/month per MCP server** - even if you never use the tools.

And then there's **context rot** - your AI literally gets dumber as you add more tools ([Chroma Research, 2025](https://research.trychroma.com/context-rot)).

## The Solution

OneTool is **one MCP server** that exposes tools as a Python API. Instead of reading tool definitions, your agent writes code:

```python
__onetool brave.search(query="react 19 server components")
```

Configure one MCP server. Use unlimited tools - ~2K tokens no matter how many you add.

> "Agents scale better by writing code to call tools instead. This reduces the token usage from 150,000 tokens to 2,000 tokens...a cost saving of 98.7%"
>
> — [Anthropic Engineering](https://www.anthropic.com/engineering/code-execution-with-mcp)

**97% fewer tokens. 30× lower cost. No context rot.** ([Measured](https://onetool.beycom.online/learn/comparison/) - 47,660 → 1,131 input tokens against 18 MCP servers.)

[📖 Read the full story](https://onetool.beycom.online/about/about-onetool/)

---

## Code Is the Interface

Because tools are Python functions, your agent does things tool-call JSON can't: batch, chain, loop, compose.

```python
__onetool
page = webfetch.fetch(url="https://fastmcp.dev/changelog", output_format="markdown")
notes = ot_llm.transform(data=page, prompt="Summarise the breaking changes")
mem.write(topic="deps/fastmcp", content=notes)
```

Three packs, one request. Intermediate results flow between tools as variables - the page body never touches your context window, and the summarising runs on a cheap model instead of your expensive coding agent.

Every call is explicit and reviewable - `__onetool brave.search(query="...")` shows you exactly what runs. No tool-selection guessing.

And the runtime is built for how agents actually type:

- `mem.search(q="auth")` works - any unambiguous parameter prefix resolves (`q=` → `query=`)
- `wb.draw(...)` works - packs have short aliases (`wb`, `ctx`, `img`)
- `github.listRepositories()` works on proxied servers - snake/camel/Pascal all resolve
- A typo'd tool gets a did-you-mean, a disconnected server names the command that fixes it
- Oversized results come back as a searchable handle instead of flooding the window

---

## Install

Bootstrap (installs `uv` if missing, installs OneTool, initialises config, prints MCP config):

```bash
curl -LsSf https://onetool.beycom.online/install.sh | sh          # macOS / Linux
irm https://onetool.beycom.online/install.ps1 | iex               # Windows (PowerShell)
```

Or install manually with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install 'onetool-mcp[all]'   # everything
onetool init --config ~/.onetool
```

Then print ready-to-paste MCP client config with resolved absolute paths and add it
to your client (`claude-code`, `claude-desktop`, `cursor`, or `vscode`):

```bash
onetool init mcp-config --client claude-code   # or omit --client for all four
```

That's it. All 250+ tools work out of the box.

Verify: `onetool init validate --config ~/.onetool/onetool.yaml`

Install the `ot-ref` skill into your agent with [vercel-labs/skills](https://github.com/vercel-labs/skills) - it teaches the call conventions and ships a greppable index of every tool signature:

```bash
npx skills add https://github.com/beycom/onetool-mcp --skill ot-ref --agent claude
```

[📖 Full installation guide](https://onetool.beycom.online/learn/installation/)

---

## What's Inside

| | |
| --- | --- |
| **Search & docs** | Brave, Google-grounded, and Tavily search (each with batch + answer modes), Context7 library docs, web fetch with extraction controls |
| **Files & data** | File ops with path boundaries, full Excel control, SQL databases, PDF/Word/PowerPoint → Markdown, ripgrep, package versions |
| **Context economy** | `ctx` handles for large outputs, partial file reads (`toc`/`slice`), image vision on a dedicated cheap model (zero host tokens), LLM delegation (10× savings) |
| **Persistent state** | `mem` memory with semantic + keyword search, history and rollback; `knowledge` RAG bases with AI enrichment; `localhist` Git-backed project snapshots |
| **Visual** | Live Excalidraw whiteboard with a Mermaid-compatible DSL and offline auto-layout, Mermaid/PlantUML/D2 diagrams, architecture models → draw.io-editable SVG |
| **Runtime** | MCP server proxy with runtime enable/disable/restart, direct CLI/API into the running process, `ot-ref` agent skill, in-conversation tool forging |
| **Trust** | age-encrypted secrets backed by your OS keychain, AST validation, path boundaries, output sanitisation, runtime stats with estimated savings |

---

## Tools

28 packs, 252 tools ready to use (`console` in beta):

| Pack          | Tools                                                        | Extra    | Description                          |
| ------------- | ------------------------------------------------------------ | -------- | ------------------------------------ |
| `arch`        | `generate`, `validate`, `bundle_solution`, …                 | `[dev]`  | Architecture models → draw.io-editable SVG |
| `brave`       | `search`, `news`, `image`, `video`, `search_batch`           | `[util]` | Brave web search                     |
| `chrome_util` | `highlight_element`, `guide_user`, …                         | `[dev]`  | Browser annotations (Chrome DevTools) |
| `console` *(beta)* | `show`, `display`, `list`, `read`, `clear`              |          | Messages to the upcoming onetool-console app |
| `context7`    | `search`, `doc`                                              | `[dev]`  | Library documentation                |
| `convert`     | `pdf`, `word`, `powerpoint`, `excel`, `auto`                 | `[util]` | Documents → Markdown                 |
| `db`          | `query`, `schema`, `tables`, `sample`                        | `[dev]`  | SQL databases                        |
| `diagram`     | `render_diagram`, `batch_render`, `get_template`, …          | `[dev]`  | Mermaid / PlantUML / D2 via Kroki    |
| `excel`       | `read`, `write`, `formula`, `create_table`, … (24 tools)     | `[util]` | Full Excel control                   |
| `file`        | `read`, `write`, `edit`, `grep`, `slice`, `toc`, … (16 tools) | `[util]` | File ops with path boundaries        |
| `ground`      | `search`, `dev`, `docs`, `reddit`, `search_batch`            | `[util]` | Google-grounded search with sources  |
| `knowledge`   | `search`, `ask`, `write`, `related`, … (15 tools)            | `[util]` | RAG knowledge bases (hybrid search)  |
| `localhist`   | `save`, `diff`, `restore`, `autosave_start`, … (15 tools)    | `[dev]`  | Git-backed local history snapshots   |
| `mem`         | `write`, `search`, `ask`, `history`, `rollback`, … (31 tools) | `[util]` | Persistent memory with semantic search |
| `ot`          | `help`, `tools`, `stats`, `status`, `result`, … (18 tools)   |          | Introspection and management         |
| `ot_context` (`ctx`) | `write`, `read`, `grep`, `slice`, `toc`, `ask`, … (13 tools) |    | Smart context store for large outputs |
| `ot_forge`    | `create_ext`, `validate_ext`                                 |          | Scaffold new tool packs              |
| `ot_image` (`img`) | `load`, `ask`, `clip_ask`, `summary`, … (9 tools)       |          | Image vision via a dedicated model   |
| `ot_llm`      | `transform`, `transform_file`                                |          | LLM-powered transforms               |
| `ot_secrets`  | `set`, `encrypt`, `audit`, `rotate`, … (8 tools)             |          | Encrypted secrets management         |
| `ot_servers`  | `enable`, `disable`, `restart`, `status`                     |          | Runtime control of proxied servers   |
| `ot_timer`    | `start`, `stop`, `elapsed`, `list`, `clear`                  |          | Named timers                         |
| `package`     | `pypi`, `npm`, `version`, `audit`, `models`                  | `[dev]`  | Package versions and staleness       |
| `play_util`   | `highlight_element`, `guide_user`, …                         | `[dev]`  | Browser annotations (Playwright)     |
| `ripgrep`     | `search`, `count`, `files`, `types`                          | `[dev]`  | Fast code search                     |
| `tavily`      | `search`, `research`, `extract`, `search_batch`, …           | `[util]` | AI-native search and extraction      |
| `webfetch`    | `fetch`, `fetch_batch`                                       | `[dev]`  | Web content extraction               |
| `whiteboard` (`wb`) | `open`, `draw`, `layout`, `screenshot`, … (22 tools)   | `[util]` | Live Excalidraw canvas               |

[📖 Complete tools reference](https://onetool.beycom.online/reference/tools/) — every signature, generated from source

---

## MCP Server Proxy

Keep the MCP servers you already use. Wrap them in YAML and call them explicitly - as Python namespaces, without their tool tax:

```yaml
# .onetool/onetool.yaml
servers:
  local_tools:
    type: stdio
    command: npx
    args: ["-y", "some-mcp-server@latest"]
  private_api:
    type: http
    url: ${PRIVATE_MCP_URL}
    auth:
      type: bearer
      token: ${PRIVATE_MCP_TOKEN}
```

```python
__onetool private_api.read_resource(path="README.md")
```

Proxied servers can be enabled, disabled, and restarted mid-conversation with `ot_servers` - no client restart.

[📖 Configuration guide](https://onetool.beycom.online/reference/cli/onetool-config/#external-mcp-servers)

---

## Secrets You Can Commit

`onetool init` walks you through encrypted secrets: values in `secrets.yaml` are age-encrypted, the private key lives in your OS keychain, and decryption happens transparently at load.

```yaml
# secrets.yaml - safe to inspect, safe to commit
brave_api_key: age1enc:YWdlLWVuY3J5cHRpb24ub3JnL3YxCi0+IFgyNT...
```

[📖 Security guide](https://onetool.beycom.online/learn/security/)

---

## Use from the CLI

Works as an MCP server **and** as a direct CLI bridge into the same running process - loaded config, secrets, and proxy connections stay warm. Useful for agent harnesses, scripts, and automation:

```bash
# Recommended local MCP root mode: stdio
onetool serve --config .onetool/onetool.yaml

# URL-based MCP root mode for containerized clients
onetool serve --transport http --config .onetool/onetool.yaml --host 127.0.0.1 --port 8767 --path /mcp

# Enable the MCP-owned direct API in onetool.yaml:
# direct.host.enabled: true

# Start OneTool as MCP, then use the port printed in startup logs.
onetool direct run --port 8765 "ot.packs()" --format json | jq '.[0].name'
onetool direct run --port 8765 "brave.search(query='latest AI news')" --format raw
```

[📖 Direct usage guide](https://onetool.beycom.online/learn/direct-usage/)

---

## Extending

Drop a Python file, get a pack. No registration, no config:

```python
# .onetool/tools/wiki.py
pack = "wiki"

def summary(*, title: str) -> str:
    """Get Wikipedia article summary."""
    import httpx
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
    return httpx.get(url).json().get("extract", "Not found")
```

```python
__onetool wiki.summary(title="Python_(programming_language)")
```

[📖 Creating tools guide](https://onetool.beycom.online/learn/extension-tools/)

---

## Documentation

- [Quickstart](https://onetool.beycom.online/learn/quickstart/) - 30 seconds to first tool call
- [Installation](https://onetool.beycom.online/learn/installation/) - All platforms
- [Configuration](https://onetool.beycom.online/learn/configuration/) - YAML schema
- [Tools Reference](https://onetool.beycom.online/reference/tools/) - All 252 tools
- [Security](https://onetool.beycom.online/learn/security/) - The layered security model
- [Extending](https://onetool.beycom.online/learn/extension-tools/) - Build your own
- [Dev Docs](https://github.com/beycom/onetool-mcp/blob/main/dev/index.md) - Internal developer documentation
- [Specifications](https://github.com/beycom/onetool-mcp/blob/main/openspec/specs/INDEX.md) - OpenSpec specifications index

---

## References

- [Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) - Anthropic Engineering
- [Context Rot](https://research.trychroma.com/context-rot) - Chroma Research

---

## Telemetry

OneTool sends anonymous startup pings (event type, version, OS). No personal data. Opt out: `export DO_NOT_TRACK=1` or set `telemetry.enabled: false` in `onetool.yaml`. [Details](docs/telemetry.md)

---

## Issues

**Check for existing issues first:**

- Browse the tracker: [github.com/beycom/onetool-mcp/issues](https://github.com/beycom/onetool-mcp/issues)
- Search with GitHub syntax: `is:issue repo:beycom/onetool-mcp <keyword>`

**Raise a new issue:** [github.com/beycom/onetool-mcp/issues/new](https://github.com/beycom/onetool-mcp/issues/new)

---

## Support

If you find OneTool useful:

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Buy%20me%20a%20coffee-ff5e5b?logo=ko-fi)](https://ko-fi.com/beycom)

---

## License

GPLv3

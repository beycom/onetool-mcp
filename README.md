<p align="center">
  <!-- mcp-name: io.github.beycom/onetool-mcp -->
  <a href="https://github.com/beycom/onetool-mcp">
    <img src="https://raw.githubusercontent.com/beycom/onetool-mcp/main/docs/assets/logo.svg" alt="OneTool" width="80">
  </a>
</p>

<p align="center">
  <strong>🧿 One MCP for developers - No tool tax, no context rot.<br>100+ tools including Brave, Google, Context7, Excalidraw, AWS, Version Checker, Excel, File Ops, Database, Image Vision, Playwright & Chrome DevTools Utils and many more.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/onetool-mcp/"><img alt="PyPI" src="https://img.shields.io/pypi/v/onetool-mcp"></a>
  <a href="https://github.com/beycom/onetool-mcp/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/license-GPLv3-blue"></a>
  <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue"></a>
  <a href="https://github.com/beycom/onetool-mcp/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/beycom/onetool-mcp"></a>
</p>

<p align="center">
  Works with Claude Code or any MCP client
</p>

---

## The Problem

Each MCP server consumes **3K-30K tokens per request**. Connect 5 servers and you've burned 55K tokens before the conversation starts. Connect 10+ and you're at 100K tokens.

The math is brutal: Claude Opus 4.5 at $5/M input tokens, 20 days × 10 conversations × 10 messages × 3K tokens = **$30/month per MCP server** - even if you never use the tools.

And then there's **context rot** - your AI literally gets dumber as you add more tools ([Chroma Research, 2025](https://research.trychroma.com/context-rot)).

## The Solution

OneTool is **one MCP server** that exposes tools as a Python API. Instead of reading tool definitions, your agent writes code:

```python
__run brave.search(query="react docs 2026")
```

Configure one MCP server. Use unlimited tools.

> "Agents scale better by writing code to call tools instead. This reduces the token usage from 150,000 tokens to 2,000 tokens...a cost saving of 98.7%"
>
> — [Anthropic Engineering](https://www.anthropic.com/engineering/code-execution-with-mcp)

**96% fewer tokens. 30× lower cost. No context rot.**

[📖 Read the full story](https://onetool.beycom.online/about/about-onetool/)

---

## Install

Requires [uv](https://docs.astral.sh/uv/):

```bash
uv tool install 'onetool-mcp[all]'   # everything
onetool init --config ~/.onetool
```

Add to Claude Code:

```bash
claude mcp add onetool -- onetool serve --config ~/.onetool/onetool.yaml --secrets ~/.onetool/secrets.yaml
```

Or manually add to `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "onetool": {
      "command": "onetool",
      "args": ["serve", "--config", "/Users/yourname/.onetool/onetool.yaml", "--secrets", "/Users/yourname/.onetool/secrets.yaml"]
    }
  }
}
```

That's it. All 100+ tools work out of the box.

Verify: `onetool init validate --config ~/.onetool/onetool.yaml`

[📖 Full installation guide](https://onetool.beycom.online/learn/installation/)

---

## Use from the CLI

Works as an MCP server **and** as a direct CLI bridge into a running MCP process. Useful for agent harnesses, scripts, and automation:

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

## Features

| Feature                  | Description                                                   |
| ------------------------ | ------------------------------------------------------------- |
| **96% Token Savings**    | ~2K tokens no matter how many tools you add                   |
| **100+ Built-in Tools**  | Web search, AWS, databases, file ops, diagrams, conversions   |
| **Explicit Execution**   | See exactly what runs — `__run brave.search(q="AI")`           |
| **Dynamic AWS**          | Proxy all 57+ AWSlabs MCP servers; SSO and credentials handled |
| **Live Whiteboard**      | Draw diagrams with a Mermaid-compatible DSL via Excalidraw    |
| **MCP Server Proxy**     | Wrap existing MCP servers without the tool tax                |
| **Encrypted Secrets**    | age-encrypted `secrets.yaml` backed by your OS keychain       |
| **Forge Tools**          | Build new tools as part of the conversation                   |
| **Image Vision**         | Routes to a cheaper, better vision model via `ot_image` (`img`). Zero host tokens. Supports local files, URLs, clipboard; PNG, JPEG, GIF, WebP, TIFF, HEIC, AVIF, SVG. |
| **Smart Context**        | `ot_context` (`ctx`) — SQLite+FTS5 store. Search and navigate large outputs without filling the context window. |
| **Caveman Compact**      | `ot_caveman` (`cm`) — LLM-powered text compaction. 55–65% on tech prose, 25–31% on search results, 45–55% on conversational prose. `__compact__ = True` applies it to any tool call. Code blocks, URLs, and security warnings are never modified. |
| **Smart Tools**          | Delegate to cheaper LLMs (10× savings)                        |
| **Security Layers**      | AST validation, path boundaries, output sanitisation          |

---

## Tools

27+ packs, 230+ tools ready to use:

| Pack          | Tools                                          | Extra    | Description                    |
| ------------- | ---------------------------------------------- | -------- | ------------------------------ |
| `aws`         | `whoami`, `login`, `start_packs`, `roles`      | `[dev]`  | Dynamic AWS proxy (57+ servers)|
| `brave`       | `search`, `news`                               | `[util]` | Web and news search            |
| `chrome_util` | `highlight_element`, `guide_user`              | `[dev]`  | Browser annotations (DevTools) |
| `context7`    | `search`, `doc`                                | `[dev]`  | Library documentation          |
| `convert`     | `pdf_to_md`, `docx_to_md`, `pptx_to_md`        | `[util]` | Document conversion            |
| `db`          | `query`, `schema`, `tables`, `sample`          | `[dev]`  | Database operations            |
| `diagram`     | `create`, `get_playground_url`                 | `[dev]`  | Mermaid / Kroki diagrams       |
| `excel`       | `read`, `write`, `query`                       | `[util]` | Excel files                    |
| `file`        | `read`, `write`, `grep`, `slice`, `toc`        | `[util]` | File operations                |
| `ground`      | `search`                                       | `[util]` | Google Grounding search        |
| `knowledge`   | `search`, `ask`, `write`, `read`, `grep`       | `[util]` | RAG knowledge base (FTS5+vector) |
| `mem`         | `write`, `read`, `search`, `grep`, `ask`, `inspect`, `query` | `[util]` | Persistent memory              |
| `ot_forge`    | `create_ext`, `validate_ext`, `install_skills` |          | Scaffold new tool packs        |
| `ot_context` (`ctx`) | `write`, `read`, `search`, `grep`, `slice`, `toc`                 |          | Smart context store (SQLite+FTS5)   |
| `ot_caveman` (`cm`)  | `compact`, `expand`, `input`                                      |          | LLM-powered text compaction and expansion |
| `ot_image` (`img`)   | `load`, `load_batch`, `ask`, `summary`, `list`, `delete`, `purge` | `[util]` | Image vision via dedicated model    |
| `ot_llm`      | `transform`, `transform_file`                  |          | LLM-powered transforms         |
| `ot_secrets`  | `init`, `encrypt`, `audit`, `rotate`           |          | Secrets encryption             |
| `ot_timer`    | `start`, `elapsed`, `list`                     |          | Named timers                   |
| `ot`          | `help`, `tools`, `stats`, `skills`             |          | Introspection                  |
| `package`     | `npm`, `pypi`, `cargo`                         | `[dev]`  | Package versions               |
| `play_util`   | `highlight_element`, `guide_user`              | `[dev]`  | Browser annotations (Playwright)|
| `ripgrep`     | `search`, `count`                              | `[dev]`  | Fast code search               |
| `tavily`      | `search`, `search_batch`, `research`           | `[util]` | AI-native search               |
| `webfetch`    | `fetch`, `fetch_batch`                         | `[dev]`  | Web fetching                   |
| `whiteboard`  | `open`, `draw`, `screenshot`, `save`           | `[dev]`  | Live Excalidraw canvas         |

[📖 Complete tools reference](https://onetool.beycom.online/reference/tools/) — full summary table with all 230+ tools

---

## MCP Server Proxy

Wrap any existing MCP server and call it explicitly - simple yaml config without the tool tax:

```yaml
# .onetool/onetool.yaml
servers:
  chrome_devtools:
    type: stdio
    command: npx
    args: ["-y", "@anthropic-ai/chrome-devtools-mcp@latest"]
  github:
    type: stdio
    command: npx
    args: ["-y", "@anthropic-ai/github-mcp-server@latest"]
```

```python
__run mcp.call(server="github", tool="get_file_contents", arguments={"path": "README.md"})
```

[📖 Configuration guide](https://onetool.beycom.online/learn/configuration/#external-mcp-servers)

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
__run wiki.summary(title="Python_(programming_language)")
```

[📖 Creating tools guide](https://onetool.beycom.online/learn/extension-tools/)

---

## Documentation

- [Quickstart](https://onetool.beycom.online/learn/quickstart/) - 30 seconds to first tool call
- [Installation](https://onetool.beycom.online/learn/installation/) - All platforms
- [Configuration](https://onetool.beycom.online/learn/configuration/) - YAML schema
- [Tools Reference](https://onetool.beycom.online/reference/tools/) - All 100+ tools
- [Security](https://onetool.beycom.online/learn/security/) - Security layers
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

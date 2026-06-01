# What's New in v2

This guide covers what you gain in OneTool MCP v2, followed by upgrade steps and breaking changes.

## New Tool Packs

These packs are entirely new in v2.

### whiteboard (excalidraw) — Live whiteboard `[dev]`

Turns Excalidraw into a tool-driven canvas. Agents can generate architecture diagrams, flowcharts, and sketches using a Mermaid-compatible DSL, then screenshot or save the result — all without manual drawing. Useful for visual planning, documentation, and sharing ideas that are easier to show than describe.

```text
__run whiteboard.open()
__run whiteboard.draw(input="A --> B --> C")
__run whiteboard.screenshot()
__run whiteboard.save(path="arch.json")
__run whiteboard.close()
```

Also provides `load`, `clear`, `erase`, `note`, `scroll`, `zoom`, `fit`, `layout`, `align`, `read_scene`, and `hard_reset`. Short alias: `wb`.

### tavily — AI-powered search and URL extraction `[util]`

Tavily is an AI-native search API optimised for LLM pipelines. Results come back clean — titles, URLs, content snippets, and an AI-synthesised answer — all in one call. `output_format` controls the response structure (`"full"`, `"text_only"`, `"sources_only"`), matching the convention used by the `ground` pack. `search_batch()` runs multiple queries in parallel with section labels. `extract_batch()` fetches multiple URL sets concurrently. `research()` submits a deep research task and polls until complete.

```text
__run tavily.search(query="LLM context window research", output_format="text_only")
__run tavily.search(query="AI news", topic="news", time_range="week", min_score=0.7)
__run tavily.search_batch(queries=["React 19 features", "Vue 4 roadmap"])
__run tavily.extract(urls=["https://docs.python.org/3/"])
__run tavily.extract_batch(url_sets=[(["https://docs.a.com"], "A"), (["https://docs.b.com"], "B")])
__run tavily.research(input="How does Rust's ownership model work?", model="mini")
```

Requires a `TAVILY_API_KEY` in `secrets.yaml`. Supports topic filters (`general`, `news`, `finance`), domain allow/block lists, time range filtering, relevance score threshold (`min_score`), and configurable result depth.

### chrome_util / play_util — Browser annotations `[dev]`

Two packs that bring visual annotation to browser automation. Inject overlays onto any page, highlight elements with labels and colours, and display step-by-step guidance panels — one driven by Chrome DevTools Protocol, the other by Playwright. The benefit is the same: agents can visually mark up a page to show users exactly what they're looking at or guide them through a multi-step UI workflow.

```text
__run chrome_util.inject_annotations()
__run chrome_util.highlight_element(selector="h1", label="Title")
__run chrome_util.guide_user(instructions="Click the login button")
__run chrome_util.scan_annotations()
```

### skills — Bundled skill guides

v1 supported user-defined skill files but they were fragile and hard to maintain. v2 replaces them with curated, bundled skill guides. These are structured Markdown documents that give your LLM focused context on demand.

```text
__run skills.skills()                     # list all skills
__run skills.skills(name="ot-ref")       # get full skill content
```

### ot_secrets — Secret encryption

In v1, API keys sat in plain text in `secrets.yaml`. If that file was accidentally committed or shared, every key was exposed. v2 adds transparent age encryption backed by your OS keychain. You generate an identity once, encrypt your secrets file in-place, and from that point on OneTool decrypts values automatically at load time. You can audit which values are still plain, rotate keys, and check keychain status — all without leaving the tool.

```text
__run ot_secrets.init()                          # generate key, store in keychain
__run ot_secrets.encrypt(file="secrets.yaml")    # encrypt plain values in-place
__run ot_secrets.audit(file="secrets.yaml")      # check which values are encrypted
__run ot_secrets.rotate(file="secrets.yaml")     # rotate to a new key
__run ot_secrets.status()                        # keychain status
```

### ot_forge — Extension scaffolding

Generates the boilerplate for new tool packs — file structure, type hints, keyword-only args, docstrings — so you can focus on the logic. Also validates extensions before reload, catching issues early.

```text
__run ot_forge.create_ext(name="my_pack", pack_name="mypack", function="hello")
__run ot_forge.validate_ext(path="src/mypack.py")
```

### ot_timer — Named timers

Simple named timers that persist across tool calls. Start a timer before a long operation, check elapsed time after, and compare results. Useful for profiling builds, API calls, or any workflow where you want to measure duration without leaving the conversation.

```text
__run ot_timer.start(name="build")
__run ot_timer.elapsed(name="build")
__run ot_timer.list()
```

### knowledge — RAG knowledge base `[util]`

Portable SQLite knowledge bases with hybrid FTS5+vector search and AI synthesis. Index documentation from scraped sites or write personal annotations, then search with keyword, semantic, or combined (hybrid) modes. `knowledge.ask()` retrieves relevant chunks and synthesises a concise answer with source citations. Link-graph traversal via `knowledge.related()` follows markdown hyperlinks between topics.

```text
__run knowledge.search(q='context managers', db='docs')
__run knowledge.ask(q='How do I configure authentication?', db='docs')
__run knowledge.write(topic='python/tips/loops', content='Use enumerate()', db='docs', category='rule')
__run knowledge.dbs()
```

Also provides `read`, `update`, `append`, `delete`, `grep`, `related`, `list`, `toc`, `slice`, `stats`, `info`. Short alias: `kb`.

### ot_context — Smart context store `[core]`

Persistent SQLite + FTS5 store for large tool outputs. TTL-expiring, BM25-indexed. Write, search, grep, and navigate results across tool calls without burning your context window.

```text
__run h = ctx.write(content="...", source="research"); ctx.grep(handle=h["handle"], pattern="async error handling")
__run ctx.grep(handle="abc123", pattern="def.*handler")
__run ctx.read(handle="abc123", offset=50)
```

Short alias: `ctx`.

### ot_image — Dedicated image vision `[core]`

Routes image analysis to a dedicated vision model in a separate API session — zero tokens charged to your host session. Substantially more accurate than direct attachment for structured extraction.

Benchmark (4-column product price grid, 20 cells):

| Metric                | `img.ask` | Direct attachment |
| --------------------- | --------- | ----------------- |
| Host session tokens   | **0**     | 190,221           |
| Cost to host session  | **$0**    | $0.078            |
| Rows extracted (of 5) | **5 / 5** | 3 / 5             |
| Cell accuracy (of 20) | **~100%** | **25%**           |
| Speed                 | 41s       | 34s               |

```text
__run img.load(img="diagram.png")
__run img.ask(img="#diag_01", q="What services are in this architecture?")
__run img.summary(img="#diag_01")
```

Supports PNG, JPG, SVG, HEIC, AVIF, TIFF. Short alias: `img`.

---

## New and Changed Functions in Existing Packs

### file `[util]`

v1's file pack covered the basics — read, write, edit, list, search, delete, copy, move. v2 adds a proper grep with `.gitignore` awareness so searches don't drown in `node_modules` and build artifacts. Batch reads let agents load multiple files in a single call instead of one at a time. The new slice and toc functions bring structured navigation to large files — jump to a section by heading or line range, or get a numbered table of contents to orient before reading.

| Function                   | What it does                                                |
| -------------------------- | ----------------------------------------------------------- |
| `file.grep(pattern, path)` | Regex search across files, respects `.gitignore` by default |
| `file.read_batch(items)`   | Read multiple files in one call                             |
| `file.slice(path, select)` | Extract sections by line range or heading                   |
| `file.slice_batch(items)`  | Extract sections from multiple files                        |
| `file.toc(path)`           | Table of contents for markdown files                        |

### mem `[util]`

v1's memory pack already had semantic search via embeddings. v2 adds `grep` for when you know what you're looking for — exact pattern matching across memory content with line numbers and context lines, like running ripgrep over your knowledge base. This is faster and more precise than semantic search for known terms, error messages, or specific code patterns.

| Function            | What it does                                          |
| ------------------- | ----------------------------------------------------- |
| `mem.grep(pattern)` | Regex search across memory content with context lines |

### mem `[util]` — new retrieval functions

Three new functions extend mem beyond write/search/grep:

| Function                        | What it does                                                  |
| ------------------------------- | ------------------------------------------------------------- |
| `mem.ask(topic, q)`             | Q&A over a memory using LLM synthesis                         |
| `mem.inspect(topic)`            | Low-level structured metadata for a single memory             |
| `mem.query(topic, expr)`        | JMESPath query against a JSON/YAML memory                     |

### context7 `[dev]`

The Context7 integration has been simplified. `doc()` has a cleaner signature — just pass the library identifier and your query. The underlying API was updated to v2 endpoints with better library resolution and semantic reranking.

### diagram `[dev]`

Adds `get_playground_url(source)` which generates a shareable Kroki playground link for any diagram source. Instead of rendering locally, you can hand someone a URL where they can view and edit the diagram interactively.

### whiteboard `[dev]`

**`layout` — ELK.js auto-layout**

Runs ELK.js in the browser to automatically position all nodes, then calls `fit()`. Works on the full canvas or a selection.

```text
__run wb.layout()                                    # layered, top-to-bottom
__run wb.layout(direction="RIGHT", gap_layer=120)    # left-to-right pipeline
__run wb.layout(algorithm="stress")                  # spring-based, undirected
__run wb.layout(algorithm="mrtree", direction="DOWN")
__run wb.layout(direction="RIGHT", arrow_type="elbow")
```

| Parameter        | Default            | Options                                                                  |
| ---------------- | ------------------ | ------------------------------------------------------------------------ |
| `algorithm`      | `layered`          | `layered`, `stress`, `mrtree`, `radial`, `force`                         |
| `direction`      | `DOWN`             | `DOWN`, `RIGHT`, `UP`, `LEFT`                                            |
| `gap_layer`      | `80`               | pixels between layers (`layered` only)                                   |
| `gap_node`       | `40`               | pixels between nodes in the same layer                                   |
| `arrow_type`     | `None`             | `"curve"`, `"sharp"`, `"elbow"` — patch all arrows after layout          |
| `node_placement` | `NETWORK_SIMPLEX`  | `BRANDES_KOEPF`, `LINEAR_SEGMENTS`, `SIMPLE` (`layered` only)            |
| `elk_options`    | —                  | `dict[str, str]` of raw ELK key→value pairs; overrides all named params  |

**Other additions:**

- **`align`** — align selected shapes (left, right, center, top, bottom, middle)
- **`read_scene`** — read current canvas state back as structured data
- **Auto-size shapes** — shapes resize from label content automatically
- **Chained edge syntax** — `A --> B --> C --> D` in a single DSL line

### excel `[util]`

| Change                      | What it does                                              |
| --------------------------- | --------------------------------------------------------- |
| Multi-sheet `create`        | Create workbooks with multiple named sheets in one call   |
| `datetime` serialization    | Dates round-trip correctly                                |

---

## New Features

### Interactive setup with `onetool init`

Getting started no longer means editing YAML by hand. Run `onetool init` and a TUI opens — a checkbox list of every available extension (prompts, servers, security rules, diagram config, snippets). Toggle what you want, press enter, and the config files are written for you. Existing files are backed up to `.bak` automatically.

```bash
onetool init --config ~/.onetool
```

### Cleaner config layout

v2 simplifies how config is found and passed to the server:

- **Flat directory** — config lives in `~/.onetool/` directly, not `~/.onetool/config/`
- **Explicit flags** — `--config` and `--secrets` are passed to the server; no implicit discovery
- **Versioned schema** — add `version: 2` to `onetool.yaml`; configs without it are rejected with a clear error rather than silently misbehaving

```bash
onetool serve --config ~/.onetool/onetool.yaml --secrets ~/.onetool/secrets.yaml
```

### Top-level `llm:` config

Configure `base_url`, `model`, and `embedding_model` once at the top level — all LLM-using tools (`ot_llm`, `ot_image`, `mem`, `knowledge`, `ctx`) inherit from it. Individual packs can still override with `tools.<pack>.model` etc.

```yaml
llm:
  base_url: https://openrouter.ai/api/v1
  model: google/gemini-2-flash-preview
  embedding_model: text-embedding-3-small
```

### Slim prompts

The system prompt sent to LLMs is now compact (under 25 lines), reducing context overhead and freeing up token budget for your actual work.

### Smarter result navigation

`ot.result()` gains new parameters for navigating large outputs without full pagination:

- **`tail=N`** — last N lines (great for logs)
- **`search="pattern"`** — regex filter within stored results
- **`context=N`** — lines around each match (grep-style)
- **`progress`** — human-readable progress like "lines 1-50 of 343 (15%)"
- **`next_query`** — exact call to fetch the next page

### Optional tool extras

In v1, all tools shipped in a single install. v2 splits heavy-dependency packs into `[util]` and `[dev]` extras for a leaner base install:

| Extra    | Packs                                                                              |
| -------- | ---------------------------------------------------------------------------------- |
| `[util]` | brave, convert, excel, file, ground, mem                                           |
| `[dev]`  | context7, db, diagram, package, ripgrep, webfetch, whiteboard, and browser utils |
| `[all]`  | Everything                                                                         |

---

## Upgrading

```bash
uv tool upgrade onetool-mcp
```

Or with optional tool packs:

```bash
uv tool install 'onetool-mcp[all]'     # everything
uv tool install 'onetool-mcp[util]'    # file, convert, excel, brave, ground, mem
uv tool install 'onetool-mcp[dev]'     # ripgrep, db, webfetch, diagram, ...
```

---

## Breaking Changes

### Config and MCP setup is now explicit

v1 auto-discovered config and required no arguments. v2 uses explicit `--config` and `--secrets` flags.

**v1 MCP client config:**

```json
{
  "mcpServers": {
    "onetool": {
      "command": "onetool"
    }
  }
}
```

**v2 MCP client config:**

```json
{
  "mcpServers": {
    "onetool": {
      "command": "onetool",
      "args": [
        "--config", "/path/to/.onetool/onetool.yaml",
        "--secrets", "/path/to/.onetool/secrets.yaml"
      ]
    }
  }
}
```

Or via Claude Code CLI:

```bash
claude mcp add onetool -- onetool serve --config ~/.onetool/onetool.yaml --secrets ~/.onetool/secrets.yaml
```

Omit `--secrets` if you don't use API keys. Omit `--config` to start with sensible defaults.

### Config version field

Add `version: 2` to your `onetool.yaml`. Configs with `version: 1` are rejected with a clear error.

```yaml
# onetool.yaml
version: 2
# ... rest of config
```

### Config location is flat

The config directory changed from `~/.onetool/config/` to `~/.onetool/` (flat layout). Move your files up one level, or re-run `onetool init`.

### Trigger prefix change

`__run` is the canonical explicit invocation prefix. `__r` and `__ot` are also supported aliases:

```text
__run brave.search(query="test")
__r brave.search(query="test")
__ot brave.search(query="test")
```

### User-defined skills removed

Custom skill files are no longer supported. Built-in skills like `ot-ref` are bundled and retrieved via `ot.skills()`.

---

## Dependency Changes

**New in core:** `pyrage`, `keyring` (secret encryption support)

**Moved to `[util]`:** `openpyxl`, `pymupdf`, `python-docx`, `python-pptx`, `google-genai`, `send2trash`, `pathspec`

**Moved to `[dev]`:** `sqlalchemy`, `trafilatura`, `filelock`, `tabulate`

The base `onetool-mcp` install is significantly lighter. Install `[all]` to get everything back.

---

## Quick Migration Checklist

1. Update install: `uv tool install 'onetool-mcp[all]'` (or pick specific extras)
2. Add `version: 2` to `onetool.yaml`
3. Move config from `~/.onetool/config/` to `~/.onetool/` (or re-run `onetool init`)
4. Update MCP client config to pass `--config` and `--secrets` flags
5. Replace `__ot` with `__run` in any saved prompts or documentation

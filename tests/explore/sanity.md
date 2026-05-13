# Sanity Tests

## Test Tools

```markdown
Title: Test Tools

Explain each step so it is easy to follow what you did and why. Use 💭 to highlight these explanations.
Learn OneTool with `ot.help(info="full")` as well as the docs at ./docs. If it helps, look at the source code.
Do sanity testing and find issues.

Enable proxy servers before testing (they start disconnected):
```
ot_servers.enable(name="github")
ot_servers.enable(name="playwright")
ot_servers.enable(name="chrome_devtools")
```

Test out the following packs:
Packs: arch, aws, brave, chrome_util, context7, convert, db, diagram, excel, file, ground, ide, knowledge, mem, ot, ot_caveman, ot_context, ot_forge, ot_image, ot_llm, ot_secrets, ot_servers, ot_timer, package, play_util, ripgrep, tavily, webfetch, whiteboard

Test out the following proxy servers separately:
Proxy servers: chrome_devtools, github, playwright

When testing:
- arch: validate a workbook from tests/data/ if present, otherwise run `ot.tools(pattern="arch.", info="full")` and note missing fixture coverage.
- aws: use read-only/config inspection first (`aws.profiles()`, `aws.profile()`, `aws.regions()`, `aws.services()`); only call login/start/stop tools if explicitly safe for the local environment.
- chrome_util: with a known browser page if available, test scan_annotations, inject_annotations, clear_annotations; if no Chrome session is available, verify help/signatures and note as environment gap.
- convert with files at tests/data/
- db with db at tests/data/northwind.db (25MB, download via `just test-setup`)
- excel with files at tests/data/
- ide: test read-only connection/state helpers (`ide.state()`, `ide.sel()`, `ide.workspace()`); if no IDE bridge is connected, note as environment gap.
- mem: use `tmp/test/` topic prefix for all writes. Test write, read, list, search, toc, slice, snap/restore, stale/refresh, write_batch, read_batch, slice_batch, stats, export/load, update, delete, decay, context, flush. Clean up with `mem.delete(topic="tmp/", confirm=True)` when done.
- diagram: list_providers, get_template, generate_source, render_diagram, get_playground_url
- ot_caveman: compact and expand short inline text; do not use protected content as the primary assertion.
- ot_forge: create_ext, validate_ext, install_skills
- ot_secrets: test status and audit; avoid rotate/encrypt/init on real secrets unless using a temporary file.
- ot_servers: status/list a configured server; enable/restart/disable only for explicit proxy-server test cases.
- ot_timer: start, elapsed, list, clear with a unique temporary timer name.
- webfetch with a known URL like https://en.wikipedia.org/wiki/Python_(programming_language)
- chrome_devtools with a known URL like https://en.wikipedia.org/wiki/Python_(programming_language)
- playwright with a known URL like https://en.wikipedia.org/wiki/Python_(programming_language)
- ot_llm: transform with simple data, transform_file with a file from tests/data/
- knowledge: call `knowledge.dbs()` first — if no databases are configured, skip (note as config gap, not failure). If configured, test write, search, ask, list, toc, slice, delete.
- whiteboard: hard_reset first, then draw, erase, note, read_scene, boards

```

```markdown
Title: Snippets

Explain each step so it is easy to follow what you did and why. Use 💭 to highlight these explanations.
Learn OneTool with `ot.help(info="full")` as well as the docs at ./docs. If it helps, look at the source code.
Do sanity testing and find issues.

Test the following snippets:

Search snippets:
- $br q="test query"
- $g q="test query"
- $gh q="onetool"
- $tav q="test query"
- $tav_x url="https://en.wikipedia.org/wiki/Python_(programming_language)"

Documentation snippets:
- $c7 lib="facebook/react" q="hooks"

Package snippets:
- $pkg_py packages="requests"
- $pkg_npm packages="react"
- $pkg_m q="claude"
- $pkg_a

File/code snippets:
- $rg p="TODO"
- $rg_count p="import" ft="py"
- $wf url="https://en.wikipedia.org/wiki/Python_(programming_language)"
- $wf_s url="https://en.wikipedia.org/wiki/Python_(programming_language)"
- $wf_d url="https://en.wikipedia.org/wiki/Python_(programming_language)" schema="section headings"
- $f_t
- $f_r path="README.md"
- $f_g p="TODO"

Convert snippets:
- $cv file="tests/data/file_example_1MB.docx" output_dir="tmp/sanity-cv/"

Memory snippets:
- $mem_w topic="tmp/test/snip" file="README.md" category="note"
- $mem_r topic="tmp/test/snip"
- $mem_l
- $mem_g p="TODO"
- $mem_s q="onetool features"

System snippets:
- $status
- $reload

```

```markdown
Title: Features

Explain each step so it is easy to follow what you did and why. Use 💭 to highlight these explanations.
Learn OneTool with `ot.help(info="full")` as well as the docs at ./docs. If it helps, look at the source code.
Do sanity testing and find issues.

Introspection & Discovery
- ot.help() - general help overview
- ot.help(query="...") - exact lookup (tool, pack, snippet, alias)
- ot.help(query="...", info="min|default|full") - info levels
- ot.tools() - list all tools
- ot.tools(pattern="...") - filter by pattern/prefix
- ot.packs() - list all packs
- ot.packs(pattern="...") - filter by pattern
- ot.snippets() - list configured snippets
- ot.servers() - list MCP proxy servers
- ot.servers(pattern="...") - filter by pattern
- ot.config() - show config (aliases, snippets, servers)
- ot.health() - system health check
- ot.debug() - comprehensive debug info
- ot.version() - version string

Parameter Prefixes
- Short prefixes work: ot.tools(p="brave", i="full") equivalent to ot.tools(pattern="brave", info="full")

Trigger Prefixes (invocation styles)
- >>> - recommended (Python REPL symbol)
- __run - systematic short form
- mcp__onetool__run - canonical MCP call
- __ot, __onetool__run - legacy (backward compat)

Invocation Styles
- Simple call: >>> func(arg=val)
- Code fence: multi-line Python blocks

Snippet Expansion
- $snippet_name param=value expands server-side

Output Format Control
- __format__ = "yml_h"; ... controls serialization

Output Sanitization
- __sanitize__ = True|False controls external content sanitization
- External content wrapped in boundary tags

Code Execution
- Multi-line code blocks with variables
- Loops and list comprehensions
- Chained operations
- Last expression returned as result

Security - AST Validation
- ot.security() - view security rules
- ot.security(check="pattern") - check specific pattern
- Blocked builtins rejected (exec, eval, compile, etc.)
- Warned imports logged (yaml)
- Tool namespaces whitelisted
- Special dunders: __format__, __sanitize__

Statistics
- ot.stats() - runtime statistics
- ot.stats(period="day|week") - filtered by period
- ot.stats(info="list|min|full") - info levels

Large Output Handling
- ot.result() - query stored large output with pagination

Timing
- ot_timer.start(name="label") - start a named timer
- ot_timer.elapsed(name="label") - get elapsed time
- ot_timer.list() - show all active and stored timers
- ot_timer.clear() - clear all running timers

Configuration
- ot.reload() - force config reload

```

## Tear-Down

```markdown
Title: Tear-Down

Provide a summary of the issues found, grouped by component.
Include:
- Pack/tool issues (wrong params, errors, unexpected output)
- Snippet issues (expansion failures, wrong defaults)
- Feature issues (broken introspection, security gaps, format issues)
- Any missing functionality or documentation gaps
```

## Hints

OneTool is setup correctly with all dependencies and secrets needed.

### Efficiency tips

1. **Check signatures first**: Before testing a pack, run `ot.tools(pattern="packname", info="full")` to see all parameter names and avoid guessing
2. **Batch similar tools**: Test tools in groups - e.g., all search tools together, all file tools together
3. **Skip task tracking**: Don't create granular tasks for each pack - it adds overhead. Just work through the list sequentially
4. **Use minimal test inputs**: Use small counts (2-3) and simple queries to speed up API calls
5. **Test one tool per pack first**: If the first tool works, others likely will too - focus deeper testing on tools with different signatures

### Parameter naming hints

- **excel tools**: Use `filepath` not `path`, and `sheet_name` not `sheet`
  - Example: `excel.info(filepath="tests/data/file_example_XLS_1000.xlsx")` not `excel.info(path="data.xlsx")`
  - Example: `excel.read(filepath="tests/data/file_example_XLS_1000.xlsx")` not `excel.read(path="data.xlsx", sheet="Sales")`
  - `excel.read` uses `start_cell=`/`end_cell=` for range (no `limit=` param). Example: `excel.read(filepath="...", start_cell="A1", end_cell="H4")`
  - Use `pattern=` not `search_term=` for excel.search
  - `excel.create` supports multi-sheet creation via `sheet_names=["A", "B", "C"]` (single sheet via `sheet_name=`)
  - `excel.copy_range` uses `source_range=` and `target_cell=` (not `src_range=` or `dest_cell=`)
- **file.grep**: Use `max_matches=` not `limit=` to cap results
  - Example: `file.grep(pattern="def test_", path="tests/", glob="*.py", max_matches=10)`
- **ground tools**: Use `max_sources` not `count` to limit results
  - Example: `ground.search(query="topic", max_sources=5)` not `ground.search(query="topic", count=5)`
- **context7 tools**: Different parameters for search vs doc (v2 API)
  - `context7.search()` requires both `query=` and `library_name=`
  - `context7.doc()` uses `library_id=` and `query=` (not `library_key=` or `topic=`)
  - Example: `context7.search(query="hooks tutorial", library_name="react")`
  - Example: `context7.doc(library_id="react", query="How do hooks work?")`
- **convert tools**: Use `pattern=` and `output_dir=`, not `filepath=`
  - Example: `convert.excel(pattern="tests/data/*.xlsx", output_dir="tmp/")` not `convert.excel(filepath="...")`
- **package tools**: `packages=` requires a list, not a string
  - Example: `package.pypi(packages=["requests", "flask"])` not `package.pypi(packages="requests")`
- **ot_llm tools**: Use `data=` not `input=`
  - Example: `ot_llm.transform(data="text", prompt="...")` not `ot_llm.transform(input="text", ...)`
  - `ot_llm.transform_file` uses `in_file=`/`out_file=` (not `filepath=`). Only works with text files (not binary like .xlsx).
  - Example: `ot_llm.transform_file(prompt="translate to Spanish", in_file="README.md", out_file="tmp/output.txt")`
- **db.schema**: Use `table_names=` as a list
  - Example: `db.schema(db_url="...", table_names=["users"])` not `db.schema(db_url="...", table_names="users")`
- **ripgrep.files**: Use `glob=` or `file_type=`, not `pattern=`. Has no `limit=` param (lists all matching files).
  - Example: `ripgrep.files(path="src/", file_type="py", sort="modified")`
- **ripgrep.search**: Use `limit=` not `max_results=` to limit total results
  - Example: `ripgrep.search(pattern="TODO", path=".", limit=5)`
- **mem tools**: Use `topic=` for identifying memories, `content=` for body text. Use `tmp/test/` prefix for all sanity test topics.
  - Example: `mem.write(topic="tmp/test/sanity", content="test data", category="note")`
  - Example: `mem.read(topic="tmp/test/sanity")` - exact topic match
  - Example: `mem.list(topic="tmp/test/")` - list by topic prefix (use `topic=` not `prefix=`)
  - Example: `mem.search(query="test", limit=5)` - semantic search (requires embeddings enabled)
  - Example: `mem.toc(topic="...")` - get section index
  - Example: `mem.slice(topic="...", select=[1, 2])` - extract by section number (use `select=` not `sections=`)
  - Example: `mem.slice_batch(items=[{"topic": "...", "select": [1]}])` - batch extraction (use `select=` not `sections=`)
  - Example: `mem.write_batch(topic="tmp/test/batch", glob_pattern="docs/*.md", category="note")` - batch import from files (use `glob_pattern=`, not `items=`)
  - Example: `mem.read_batch(topic="tmp/test/", meta=True)` - read multiple memories
  - Example: `mem.update(topic="tmp/test/smoke", content="updated")` - update existing memory
  - Example: `mem.context(topic="tmp/test/", limit=3)` - load most-accessed memories
  - Example: `mem.snap(output="tmp/test-snap", topic="tmp/test/")` - snapshot to directory
  - Example: `mem.restore(input="tmp/test-snap")` - restore from snapshot
  - Example: `mem.export(topic="tmp/test/smoke")` - export to YAML
  - Example: `mem.load(file="memories.yaml")` - import from YAML
  - Example: `mem.refresh(topic="tmp/test/", dry_run=True)` - check for stale file-backed memories
  - Example: `mem.decay(dry_run=True)` - preview importance decay
  - Example: `mem.stale()` - check for outdated file-backed memories
  - Example: `mem.stats()` - get memory statistics
  - Clean up: `mem.delete(topic="tmp/", confirm=True)` after testing
- **diagram tools**: Use `provider=` (not `diagram_type=`) and `source=` for rendering
  - Example: `diagram.list_providers()` - see available providers
  - Example: `diagram.get_template(name="api-flow")` - get a template (valid names: api-flow, state-machine, class-diagram, project-gantt, feature-mindmap)
  - Example: `diagram.generate_source(provider="mermaid", source="graph TD; A-->B", name="test", output_dir="output/")`
  - Example: `diagram.render_diagram(provider="mermaid", source="graph TD; A-->B", name="test")`
- **knowledge tools**: Always call `knowledge.dbs()` first — if no databases are configured, skip the pack (note as config gap, not failure). All write/search/ask tools require a `db=` parameter matching a configured database name.
  - Example: `knowledge.dbs()` — list configured databases
  - Example: `knowledge.write(topic="tmp/test", content="...", db="mydb", category="note")`
  - Example: `knowledge.search(query="...", db="mydb")`
  - Example: `knowledge.ask(question="...", db="mydb")`
- **whiteboard tools**: Always call `whiteboard.hard_reset()` before testing to ensure clean state.
  - Example: `whiteboard.hard_reset(); whiteboard.draw(input="A --> B --> C")`
  - Example: `whiteboard.erase(ids=["a"])` — use element IDs from draw output
  - Example: `whiteboard.note(input="n1[note:\nHello]")` — note type must be lowercase
  - Example: `whiteboard.read_scene()` — list current canvas elements
  - Example: `whiteboard.boards()` — list active session boards
- **ot_forge tools**: Use `name=` for creating extensions
  - Example: `ot_forge.create_ext(name="my_tool")` - create a new extension
  - Example: `ot_forge.validate_ext(path=".onetool/tools/my_tool/my_tool.py")` - validate before reload
  - Example: `ot.packs()` - lists extensions with `is_extension` and `path`
- **Snippets use abbreviated parameter names** (by design):
  - `$rg` and `$rg_count` use `p=` for pattern (not `pattern=`)
  - `$br`, `$g`, `$gh`, `$tav`, `$mem_s` use `q=` for query (not `query=`)
  - `$c7` uses `lib=` for library_id and `q=` for query
  - `$pkg_py` and `$pkg_npm` use `packages=` (comma-separated string, not list)
  - `$wf` uses `url=` for URLs (pipe-separated for batch)
  - `$mem_g` and `$f_g` use `p=` for pattern
  - `$mem_r` uses `topic=` for exact topic path
  - `$mem_w` uses `topic=` and `file=` (writes a file into memory)
  - `$cv` uses `file=` for source glob and `output_dir=` for output
  - `$tav_x` uses `url=` (pipe-separated for batch extraction)
  - `$reload` and `$status` take no parameters
  - Example: `$rg p="TODO" ft="py"` not `$rg pattern="TODO" file_type="py"`
- **db tools**: Use SQLite URL format `sqlite:///path/to/db`
  - Example: `db.tables(db_url="sqlite:///tests/data/northwind.db")`
  - Example: `db.query(sql="SELECT * FROM Customers LIMIT 3", db_url="sqlite:///tests/data/northwind.db")`
  - Not just the file path alone
  - Note: DB path is now `tests/data/northwind.db` (download via `just test-setup`)
- **webfetch.fetch**: Use `max_length=` not `max_chars=` to limit output
  - Example: `webfetch.fetch(url="...", max_length=500)`
- **brave tools**: Use `brave.news()` not `brave.search_news()`. Available: search, news, image, search_batch, video
  - Example: `brave.news(query="AI", count=3)` not `brave.search_news(query="AI")`
- **tavily.search**: Use `max_results=` not `count=` to limit results
  - Example: `tavily.search(query="Python", max_results=2)` not `tavily.search(query="Python", count=2)`
- **ot_image tools**: All tools use `img=` as the image reference parameter (not `path=` or `handle=`)
  - `ot_image.load(img="tests/data/file_example_1.jpg")` — file path, URL, or `"clip"` for clipboard
  - `ot_image.ask(img="#img_handle", q="What is in this image?")` — use `q=` not `questions=`
  - `ot_image.summary(img="#img_handle")` — extracts and caches structured summary
  - `ot_image.delete(handle="img_handle")` — handle without `#` prefix
  - Handles are returned as `"#img_<8hexchars>"` from `load()`; use bare `"img_<8hexchars>"` for `delete()`
- **whiteboard.draw**: Use `input=` not `dsl=`
  - Example: `whiteboard.draw(input="A --> B --> C")` not `whiteboard.draw(dsl="...")`
- **mem.flush**: Replaces `mem.cache_clear()` (removed in refactor). Flushes the background embedding queue.
  - Example: `mem.flush()` → "All pending embeddings completed"
- **ot_context tools**: Use `select=` not `sections=` for slice; `q=` not `question=` for ask
  - `ctx.slice(handle, select=2)` — int section number, str "N:M" line range, or heading substring
  - `ctx.ask(handle, q="list all section names")` — use `ctx.ask` not `ctx.transform`; param is `q=` not `question=`
- **whiteboard.note**: Uses `input=` not `content=` (same as draw and erase)
  - Example: `wb.note(input="n1[note:\ntext here]")` — note type must be lowercase (table/tree/seq/timeline/note)
- **whiteboard.erase**: Uses `ids=` not `targets=`
  - Example: `wb.erase(ids=["nodeA", "nodeB"])`
- **Large output → ctx handles**: `$f_r`, `$f_t`, `$f_g`, `$mem_r`, `$wf`, `$tav_x`, `$gh`, `$rg_count` return ctx handles for large output.
  Use `ctx.read(handle)` to page through, `ctx.grep(handle, pattern="...")` to search.
- **ctx parallel write contention**: Avoid calling 5+ large-output tools simultaneously — SQLite may return
  "database is locked". Retry succeeds. Filed: `wip/issues/ctx-db-locked-parallel-writes.md`
- **`ot.tools`/`ot.help` do NOT support `info="list"`**: Only `ot.stats` has `info="list"`. Use `"min"`,
  `"default"`, or `"full"` for `ot.tools` and `ot.help`.
- **`ot.result()` requires `handle=`**: Not zero-arg. Example: `ot.result(handle="abc123")`
- **devtools pack name**: Use `chrome_devtools` (underscore). The server config key is `chrome_devtools`
  and the Python namespace name matches exactly: `chrome_devtools.list_pages()`

### Expected behaviors (not bugs)

- `file.write` blocks paths outside allowed directories - this is security working correctly
- `ot.security()` shows allowed builtins, imports, and call rules - this is informational
- `mem.search` requires embeddings enabled in config (`tools.mem.embeddings_enabled: true`)
- `diagram.render_diagram` requires a Kroki server (self-hosted or public) to be configured
- `knowledge.*` tools fail if no KB is configured — `knowledge.dbs()` returning empty is a config gap, not a code bug

### Test URLs

- **webfetch.fetch & devtools.navigate_page**: Use `https://en.wikipedia.org/wiki/Python_(programming_language)` or similar - NOT example.com (doesn't resolve) or `https://en.wikipedia.org` (has captcha)

### Test data notes

Test data locations:
- **tests/data/**: All test data — download via `just test-setup` (gitignored):
  - `northwind.db` — SQLite database (25MB) with 13 tables
  - `file_example_XLS_1000.xlsx` — Excel workbook
  - `file_example_1MB.docx` — Word document
  - `file_example_PDF_1MB.pdf` — PDF document
  - `file_example_PPT_1MB.pptx` — PowerPoint presentation
  - `file_example_1.jpg`, `file_example_2.jpg` — Images
- File access: OneTool sandboxes file access — paths outside cwd may be blocked

### MCP Server notes

Disconnected servers can be enabled at runtime without restarting OneTool:
```python
ot_servers.enable(name="github")       # enable + connect
ot.server(status="github")       # check a specific server
ot_servers.restart(name="playwright")  # reconnect an already-enabled server
ot.servers()                     # list all with current status
```
Changes are in-memory only (reset on server restart). Use `ot_servers.disable(name="name")` to disconnect.

- **chrome_devtools** (29 tools): Browser automation via Chrome DevTools Protocol
  - Enable: `ot_servers.enable(name="chrome_devtools")`
  - Key tools: list_pages, navigate_page, take_snapshot, wait_for, list_console_messages
  - `devtools.wait_for()` requires `text=` parameter (not `selector=`). Example: `devtools.wait_for(text="Python")`
  - Note: if the server fails to connect, check config — may need `--isolated` flag or a running Chrome instance at `--remote-debugging-port=9222`
- **github** (44 tools): GitHub API integration
  - Enable: `ot_servers.enable(name="github")`
  - Key tools: search_repositories, get_me, list_commits, get_file_contents
  - Works with both personal and organizational repositories
- **playwright** (21 tools): Browser automation via Playwright
  - Enable: `ot_servers.enable(name="playwright")`
  - Key tools: browser_navigate, browser_snapshot, browser_click, browser_type

### Test ordering to avoid reload side effects

- **Test context7 and ground BEFORE calling `$reload`** — `ot.reload()` clears
  env-based secrets (GEMINI_API_KEY, CONTEXT7_API_KEY), causing all ground and context7
  tools to fail in the same session. These tools only work on fresh server startup.
- **Enable proxy servers early** — `ot_servers.enable(name=...)` calls at the top of the session before testing github, playwright, chrome_devtools.
- **`mem.toc` / `mem.slice`** require `toc=True` at `mem.write` time. The section index
  is only built during write. Calling `mem.write(content="# Heading\n...", toc=True)` is
  required before `mem.toc()` or `mem.slice()` will return results.

### Quick smoke test order

Test these first for fast coverage (one tool from each category):

0. Enable proxy servers: `ot_servers.enable(name="github"); ot_servers.enable(name="playwright"); ot_servers.enable(name="chrome_devtools")`
1. `brave.search(query="test", count=2)` - web search
2. `ripgrep.search(pattern="TODO", path=".", limit=3)` - file search
3. `ot.health()` - introspection
4. `$pkg_py packages="requests"` - snippets
5. `file.tree(path=".", max_depth=1)` - filesystem
6. `mem.write(topic="tmp/test/smoke", content="hello")` then `mem.read(topic="tmp/test/smoke")` then `mem.delete(topic="tmp/", confirm=True)` - memory
7. `db.tables(db_url="sqlite:///tests/data/northwind.db")` - database
8. `ground.search(query="test", max_sources=2)` - grounded search
9. `whiteboard.hard_reset(); whiteboard.draw(input="A --> B")` - whiteboard
10. `github.get_me()` - github

If all pass, the core infrastructure is working.

### Cleanup after testing

- Delete test memories: `mem.delete(topic="tmp/", confirm=True)`
- Delete test knowledge entries (if KB was configured): `knowledge.delete(topic="tmp/", db="mydb")`
- Reset whiteboard state: `whiteboard.hard_reset()`
- Remove any generated files in `tmp/`, `diagrams/`

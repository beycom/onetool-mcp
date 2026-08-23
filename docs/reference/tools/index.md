# Tool Reference

**28 Packs. 253 Tools.**

Complete reference of all built-in tool packs and functions.

For a compact generated list of every callable tool signature, see the
[Tool Index](tool-index.md).

## Optional Extras

Tools are split into optional install extras. Install only what you need:

| Extra | Tools included |
|-------|---------------|
| *(core, always included)* | `console`, `ctx`, `ot`, `ot_forge`, `ot_llm`, `ot_secrets`, `ot_servers`, `ot_timer` |
| `[util]` | `brave`, `convert`, `excel`, `file`, `ground`, `knowledge`, `mem`, `tavily`, `whiteboard` |
| `[dev]` | `arch`, `chrome_util`, `context7`, `db`, `diagram`, `localhist`, `package`, `play_util`, `ripgrep`, `webfetch` |
| `[all]` | All of the above |

```bash
uv tool install 'onetool-mcp[all]'       # everything
uv tool install 'onetool-mcp[util,dev]'  # most tools
```

## Tool Packs

| Pack | Extra | Description | Tool Count | Credits | Tools |
|------|-------|-------------|---|---------|-------|
| [**Arch**](arch.md) | `[dev]` | Architecture schema-v3 files: validate, resolve states, diff milestones, advance the baseline. | 5 | MIT | `advance`, `diff`, `init`, `resolve`, `validate` |
| [**Brave**](brave.md) | `[util]` | Web search via Brave Search API. | 5 | [brave-search-mcp-server](https://github.com/brave/brave-search-mcp-server) (MIT) | `image`, `news`, `search`, `search_batch`, `video` |
| [**Chrome DevTools Util**](chrome-util.md) | `[dev]` | Visual element annotation for a Chrome DevTools-compatible MCP server. | 5 | MIT | `clear_annotations`, `guide_user`, `highlight_element`, `inject_annotations`, `scan_annotations` |
| [**Console**](console.md) | core | Publish inline messages to a connected onetool-console app via the signed Console outbox. | 5 | MIT | `clear`, `display`, `list`, `read`, `show` |
| [**Context7**](context7.md) | `[dev]` | Library documentation lookup. | 2 | [context7](https://github.com/upstash/context7) (MIT) | `doc`, `search` |
| [**Convert**](convert.md) | `[util]` | Convert PDF, Word, PowerPoint, Excel to Markdown. | 5 | MIT | `auto`, `excel`, `pdf`, `powerpoint`, `word` |
| [**DB**](db.md) | `[dev]` | SQL database queries. | 4 | [mcp-alchemy](https://github.com/runekaagaard/mcp-alchemy) (MPL 2.0) | `query`, `sample`, `schema`, `tables` |
| [**Diagram**](diagram.md) | `[dev]` | Generate Mermaid, PlantUML, D2 diagrams. | 11 | [Kroki](https://kroki.io/) (MIT) | `batch_render`, `generate_source`, `get_diagram_instructions`, `get_diagram_policy`, `get_output_config`, `get_playground_url`, `get_render_status`, `get_template`, `list_providers`, `render_diagram`, `render_directory` |
| [**Excel**](excel.md) | `[util]` | Full Excel control. | 24 | [openpyxl](https://github.com/theorchard/openpyxl) (MIT) | `add_sheet`, `cell_range`, `cell_shift`, `copy_range`, `create`, `create_table`, `delete_cols`, `delete_rows`, `formula`, `formulas`, `hyperlinks`, `info`, `insert_cols`, `insert_rows`, `merged_cells`, `named_ranges`, `read`, `search`, `sheets`, `table_data`, `table_info`, `tables`, `used_range`, `write` |
| [**File**](file.md) | `[util]` | Secure file operations with path boundary enforcement. | 16 | MIT | `copy`, `delete`, `edit`, `grep`, `info`, `list`, `move`, `read`, `read_batch`, `resolve`, `search`, `slice`, `slice_batch`, `toc`, `tree`, `write` |
| [**Ground**](ground.md) | `[util]` | Grounded search with sources. | 5 | [Google Gemini](https://ai.google.dev/) (MIT) | `dev`, `docs`, `reddit`, `search`, `search_batch` |
| [**Knowledge**](knowledge.md) | `[util]` | Portable SQLite knowledge bases with hybrid FTS5+vector search and AI synthesis. | 15 | MIT | `append`, `ask`, `dbs`, `delete`, `grep`, `info`, `list`, `read`, `related`, `search`, `slice`, `stats`, `toc`, `update`, `write` |
| [**Localhist**](localhist.md) | `[dev]` | OneTool Local History snapshots backed by Git. | 15 | MIT | `add_exclude`, `add_force_include`, `autosave_list`, `autosave_start`, `autosave_stop`, `diff`, `history`, `info`, `init`, `log`, `prune`, `restore`, `save`, `show`, `status` |
| [**Mem**](mem.md) | `[util]` | Persistent AI agent memory with semantic search. | 31 | MIT | `append`, `ask`, `context`, `count`, `decay`, `delete`, `dump`, `flush`, `grep`, `history`, `inspect`, `load`, `list`, `query`, `read`, `read_batch`, `refresh`, `reindex`, `restore`, `rollback`, `search`, `slice`, `slice_batch`, `snapshot`, `stale`, `stats`, `toc`, `update`, `update_batch`, `write`, `write_batch` |
| [**OT Context**](ot_context.md) | core | TTL-expiring, BM25-indexed storage for large tool outputs. | 13 | MIT | `append`, `ask`, `delete`, `grep`, `inspect`, `list`, `purge`, `query`, `read`, `slice`, `stats`, `toc`, `write` |
| [**OT Core**](ot_core.md) | core | Introspection and management tools. | 18 | MIT | `aliases`, `config`, `debug`, `help`, `pack_info`, `packs`, `reload`, `result`, `security`, `server`, `servers`, `snippet_info`, `snippets`, `stats`, `status`, `tool_info`, `tools`, `version` |
| [**OT Forge**](ot_forge.md) | core | Create and validate extension tools. | 2 | MIT | `create_ext`, `validate_ext` |
| [**OT Image**](ot_image.md) | core | Load images and ask vision questions via OpenAI-compatible API. | 9 | MIT | `ask`, `clip_ask`, `clip_view`, `delete`, `list`, `load`, `load_batch`, `purge`, `summary` |
| [**OT LLM**](ot_llm.md) | core | AI-powered data transformation. | 2 | MIT | `transform`, `transform_file` |
| [**OT Secrets**](ot_secrets.md) | core | Age-encrypted secrets management. | 8 | MIT | `audit`, `encrypt`, `get`, `init`, `rotate`, `set`, `status`, `unset` |
| [**OT Servers**](ot_servers.md) | core | Runtime proxy server state changes (enable, disable, restart, status). | 4 | MIT | `disable`, `enable`, `restart`, `status` |
| [**Package**](package.md) | `[dev]` | Package version lookup and security audits. | 5 | MIT | `audit`, `models`, `npm`, `pypi`, `version` |
| [**Playwright Util**](play-util.md) | `[dev]` | Visual element annotation for a Playwright-compatible MCP server. | 6 | MIT | `clear_annotations`, `enable_auto_inject`, `guide_user`, `highlight_element`, `inject_annotations`, `scan_annotations` |
| [**Ripgrep**](ripgrep.md) | `[dev]` | Fast regex file search. | 4 | [ripgrep](https://github.com/BurntSushi/ripgrep) (MIT) | `count`, `files`, `search`, `types` |
| [**Tavily**](tavily.md) | `[util]` | AI-powered web search and URL content extraction. | 5 | [Tavily](https://tavily.com/) (MIT) | `extract`, `extract_batch`, `research`, `search`, `search_batch` |
| [**OT Timer**](ot_timer.md) | core | Named stopwatch timers for performance measurement. | 5 | MIT | `clear`, `elapsed`, `list`, `start`, `stop` |
| [**WB (Whiteboard)**](whiteboard.md) | `[util]` | Live diagram drawing on excalidraw.com via Playwright. | 22 | MIT | `align`, `boards`, `clear`, `close`, `draw`, `embed_dsl`, `erase`, `fit`, `hard_reset`, `help`, `layout`, `load`, `note`, `open`, `read_scene`, `save`, `screenshot`, `scroll`, `share`, `style`, `sync`, `zoom` |
| [**Webfetch**](webfetch.md) | `[dev]` | Fetch and extract web content. | 2 | [trafilatura](https://github.com/adbar/trafilatura) (Apache 2.0) | `fetch`, `fetch_batch` |

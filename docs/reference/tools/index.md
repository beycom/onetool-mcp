# Tool Reference

**29 Packs. 256 Tools.**

Complete reference of all built-in tool packs and functions.

## Optional Extras

Tools are split into optional install extras. Install only what you need:

| Extra | Tools included |
|-------|---------------|
| *(core, always included)* | `ot_caveman` (alias `cm`), `ctx`, `ot`, `ot_forge`, `ot_llm`, `ot_secrets`, `ot_servers`, `ot_timer` |
| `[util]` | `brave`, `convert`, `excel`, `file`, `ground`, `knowledge`, `mem`, `tavily` |
| `[dev]` | `arch`, `aws`, `chrome_util`, `context7`, `db`, `diagram`, `ide`, `package`, `play_util`, `ripgrep`, `whiteboard`, `webfetch` |
| `[all]` | All of the above |

```bash
uv tool install 'onetool-mcp[all]'       # everything
uv tool install 'onetool-mcp[util,dev]'  # most tools
```

## Tool Packs

| Pack | Extra | Description | Tool Count | Credits | Tools |
|------|-------|-------------|---|---------|-------|
| [**Arch**](arch.md) | `[dev]` | Architecture workflows for Excel ingest, validation, generation, round-trip, and bundling. | 5 | MIT | `bundle_solution`, `export_yaml`, `generate`, `import_yaml`, `validate` |
| [**AWS**](aws.md) | `[dev]` | AWS services via awslabs/mcp servers, activated on demand by role. | 17 | [awslabs/mcp](https://github.com/awslabs/mcp) (Apache 2.0) | `arn`, `attributes`, `check`, `login`, `mfa`, `packs`, `profile`, `profiles`, `refresh_packs`, `regions`, `roles`, `services`, `start_packs`, `stop_packs`, `use`, `values`, `whoami` |
| [**Brave**](brave.md) | `[util]` | Web search via Brave Search API. | 5 | [brave-search-mcp-server](https://github.com/brave/brave-search-mcp-server) (MIT) | `image`, `news`, `search`, `search_batch`, `video` |
| [**OT Caveman**](ot_caveman.md) | core | LLM-powered text compaction and expansion. | 3 | MIT | `compact`, `expand`, `input` |
| [**Chrome DevTools Util**](chrome-util.md) | `[dev]` | Visual element annotation for the Chrome DevTools MCP server. | 5 | MIT | `clear_annotations`, `guide_user`, `highlight_element`, `inject_annotations`, `scan_annotations` |
| [**Context7**](context7.md) | `[dev]` | Library documentation lookup. | 2 | [context7](https://github.com/upstash/context7) (MIT) | `doc`, `search` |
| [**Convert**](convert.md) | `[util]` | Convert PDF, Word, PowerPoint, Excel to Markdown. | 5 | MIT | `auto`, `excel`, `pdf`, `powerpoint`, `word` |
| [**DB**](db.md) | `[dev]` | SQL database queries. | 4 | [mcp-alchemy](https://github.com/runekaagaard/mcp-alchemy) (MPL 2.0) | `query`, `sample`, `schema`, `tables` |
| [**Diagram**](diagram.md) | `[dev]` | Generate Mermaid, PlantUML, D2 diagrams. | 11 | [Kroki](https://kroki.io/) (MIT) | `batch_render`, `generate_source`, `get_diagram_instructions`, `get_diagram_policy`, `get_output_config`, `get_playground_url`, `get_render_status`, `get_template`, `list_providers`, `render_diagram`, `render_directory` |
| [**Excel**](excel.md) | `[util]` | Full Excel control. | 24 | [openpyxl](https://github.com/theorchard/openpyxl) (MIT) | `add_sheet`, `cell_range`, `cell_shift`, `copy_range`, `create`, `create_table`, `delete_cols`, `delete_rows`, `formula`, `formulas`, `hyperlinks`, `info`, `insert_cols`, `insert_rows`, `merged_cells`, `named_ranges`, `read`, `search`, `sheets`, `table_data`, `table_info`, `tables`, `used_range`, `write` |
| [**File**](file.md) | `[util]` | Secure file operations with path boundary enforcement. | 15 | MIT | `copy`, `delete`, `edit`, `grep`, `info`, `list`, `move`, `read`, `read_batch`, `search`, `slice`, `slice_batch`, `toc`, `tree`, `write` |
| [**Ground**](ground.md) | `[util]` | Grounded search with sources. | 5 | [Google Gemini](https://ai.google.dev/) (MIT) | `dev`, `docs`, `reddit`, `search`, `search_batch` |
| [**IDE**](ide.md) | `[dev]` | Read-only VS Code state retrieval through a local companion bridge. | 8 | GPL-3.0 | `connect`, `editor`, `file`, `get_state`, `paths`, `sel`, `state`, `workspace` |
| [**Knowledge**](knowledge.md) | `[util]` | Portable SQLite knowledge bases with hybrid FTS5+vector search and AI synthesis. | 15 | MIT | `append`, `ask`, `dbs`, `delete`, `grep`, `info`, `list`, `read`, `related`, `search`, `slice`, `stats`, `toc`, `update`, `write` |
| [**Mem**](mem.md) | `[util]` | Persistent AI agent memory with semantic search. | 29 | MIT | `append`, `ask`, `context`, `count`, `decay`, `delete`, `export`, `flush`, `grep`, `inspect`, `load`, `list`, `query`, `read`, `read_batch`, `refresh`, `reindex`, `restore`, `search`, `slice`, `slice_batch`, `snap`, `stale`, `stats`, `toc`, `update`, `update_batch`, `write`, `write_batch` |
| [**OT Context**](ot_context.md) | core | TTL-expiring, BM25-indexed storage for large tool outputs. | 13 | MIT | `append`, `ask`, `delete`, `grep`, `inspect`, `list`, `purge`, `query`, `read`, `slice`, `stats`, `toc`, `write` |
| [**OT Core**](ot_core.md) | core | Introspection and management tools. | 19 | MIT | `aliases`, `config`, `debug`, `health`, `help`, `pack_info`, `packs`, `reload`, `result`, `security`, `server`, `servers`, `skills`, `snippet_info`, `snippets`, `stats`, `tool_info`, `tools`, `version` |
| [**OT Forge**](ot_forge.md) | core | Create, validate, and install extension tools and skill stubs. | 3 | MIT | `create_ext`, `install_skills`, `validate_ext` |
| [**OT Image**](ot_image.md) | core | Load images and ask vision questions via OpenAI-compatible API. | 9 | MIT | `ask`, `clip_ask`, `clip_view`, `delete`, `list`, `load`, `load_batch`, `purge`, `summary` |
| [**OT LLM**](ot_llm.md) | core | AI-powered data transformation. | 2 | MIT | `transform`, `transform_file` |
| [**OT Secrets**](ot_secrets.md) | core | Age-encrypted secrets management. | 5 | MIT | `audit`, `encrypt`, `init`, `rotate`, `status` |
| [**OT Servers**](ot_servers.md) | core | Runtime proxy server state changes (enable, disable, restart, status). | 4 | MIT | `disable`, `enable`, `restart`, `status` |
| [**Package**](package.md) | `[dev]` | Package version lookup and security audits. | 5 | MIT | `audit`, `models`, `npm`, `pypi`, `version` |
| [**Playwright Util**](play-util.md) | `[dev]` | Visual element annotation for the Playwright MCP server. | 6 | MIT | `clear_annotations`, `enable_auto_inject`, `guide_user`, `highlight_element`, `inject_annotations`, `scan_annotations` |
| [**Ripgrep**](ripgrep.md) | `[dev]` | Fast regex file search. | 4 | [ripgrep](https://github.com/BurntSushi/ripgrep) (MIT) | `count`, `files`, `search`, `types` |
| [**Tavily**](tavily.md) | `[util]` | AI-powered web search and URL content extraction. | 5 | [Tavily](https://tavily.com/) (MIT) | `extract`, `extract_batch`, `research`, `search`, `search_batch` |
| [**OT Timer**](ot_timer.md) | core | Named stopwatch timers for performance measurement. | 4 | MIT | `clear`, `elapsed`, `list`, `start` |
| [**WB (Whiteboard)**](whiteboard.md) | `[dev]` | Live diagram drawing on excalidraw.com via Playwright. | 22 | MIT | `align`, `boards`, `clear`, `close`, `draw`, `embed_dsl`, `erase`, `fit`, `hard_reset`, `help`, `layout`, `load`, `note`, `open`, `read_scene`, `save`, `screenshot`, `scroll`, `share`, `style`, `sync`, `zoom` |
| [**Webfetch**](webfetch.md) | `[dev]` | Fetch and extract web content. | 2 | [trafilatura](https://github.com/adbar/trafilatura) (Apache 2.0) | `fetch`, `fetch_batch` |

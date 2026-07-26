# OneTool MCP Tool Index

packs=27 tools=252

## arch
```python
arch.bundle_solution(directory: str, output_path: str | None=None, include: str | None=None)  # Bundle generated solution outputs by inlining SVG and zipping directory.
arch.export_yaml(input_path: str, output_path: str)  # Export Excel entity sheets to YAML.
arch.generate(input_path: str, output_dir: str | None=None, profile: str | None=None, profile_yaml: str | None=None, title: str | None=None, include_tags: list[str] | None=None, exclude_tags: list[str] | None=None, force: bool=False)  # Generate architecture outputs from workbook input.
arch.import_yaml(input_path: str, template_path: str, output_path: str)  # Import YAML entities into a template workbook.
arch.validate(input_path: str)  # Validate architecture workbook input.
```

## brave, br
```python
brave.image(query: str, max_results: int=10, country: str='US', search_lang: str='en', safesearch: str='strict', output_format: OutputFormat='full', max_sources: int | None=None)  # Search for images using Brave Search API.
brave.news(query: str, max_results: int=10, offset: int=0, country: str='US', search_lang: str='en', freshness: str | None=None, output_format: OutputFormat='full', max_sources: int | None=None)  # Search news articles using Brave Search API.
brave.search(query: str, max_results: int=10, offset: int=0, country: str='US', search_lang: str='en', safesearch: str='moderate', freshness: str | None=None, output_format: OutputFormat='full', max_sources: int | None=None)  # Search the web using Brave Search API.
brave.search_batch(queries: list[tuple[str, str] | str], max_results: int=2, country: str='US', search_lang: str='en', safesearch: str='moderate', freshness: str | None=None, output_format: OutputFormat='full', max_sources: int | None=None, retries: int=0, retry_delay_ms: int=250)  # Execute multiple web searches concurrently and return combined results.
brave.video(query: str, max_results: int=10, country: str='US', search_lang: str='en', freshness: str | None=None, output_format: OutputFormat='full', max_sources: int | None=None)  # Search for videos using Brave Search API.
```

## chrome_util, chrome
```python
chrome_util.clear_annotations(server: str='chrome_devtools')  # Remove all annotations and visual highlights from the page.
chrome_util.guide_user(task: str, steps: list[dict[str, str]], server: str='chrome_devtools')  # Highlight a sequence of elements to guide the user through a task.
chrome_util.highlight_element(selector: str, label: str, color: str='orange', element_id: str | None=None, server: str='chrome_devtools')  # Highlight elements matching a CSS selector with an annotation overlay.
chrome_util.inject_annotations(server: str='chrome_devtools')  # Inject the annotation script into the current browser page.
chrome_util.scan_annotations(server: str='chrome_devtools')  # Read all current annotations from the page.
```

## context7, c7
```python
context7.doc(library_id: str, query: str)  # Fetch documentation for a library from Context7.
context7.search(query: str, library_name: str, output_format: str='str')  # Search for libraries by name in Context7.
```

## convert, cv
```python
convert.auto(pattern: str, output_dir: str)  # Auto-detect format and convert documents to Markdown.
convert.excel(pattern: str, output_dir: str, include_formulas: bool=False, compute_formulas: bool=False)  # Convert Excel spreadsheets to Markdown.
convert.pdf(pattern: str, output_dir: str)  # Convert PDF documents to Markdown.
convert.powerpoint(pattern: str, output_dir: str, include_notes: bool=False)  # Convert PowerPoint presentations to Markdown.
convert.word(pattern: str, output_dir: str)  # Convert Word documents to Markdown.
```

## db
```python
db.query(sql: str, db_url: str, params: dict[str, Any] | None=None, read_only: bool=False)  # Execute a SQL query and return results.
db.sample(table: str, db_url: str, limit: int=10)  # Fetch a quick sample of rows from a table.
db.schema(table_names: list[str], db_url: str)  # Get schema definitions for specified tables.
db.tables(db_url: str, filter: str | None=None, ignore_case: bool=False, include_row_count: bool=False)  # List table names in the database.
```

## diagram, diag
```python
diagram.batch_render(sources: list[dict[str, str]], output_format: Literal['svg', 'png', 'pdf']='svg', output_dir: str | None=None, max_concurrent: int=5)  # Render multiple diagrams concurrently. Self-hosted Kroki only.
diagram.generate_source(source: str, provider: Literal['mermaid', 'plantuml', 'd2', 'graphviz', 'ditaa', 'erd', 'nomnoml', 'svgbob'] | str, name: str, output_dir: str | None=None, validate: bool=True)  # Save diagram source code to a file for review before rendering.
diagram.get_diagram_instructions(provider: Literal['mermaid', 'plantuml', 'd2'] | str | None=None)  # Get provider-specific diagram instructions.
diagram.get_diagram_policy()  # Get the diagram policy rules from configuration.
diagram.get_output_config()  # Get diagram output configuration settings.
diagram.get_playground_url(source: str, provider: Literal['mermaid', 'plantuml', 'd2'] | str)  # Generate a playground URL for interactive editing.
diagram.get_render_status(task_id: str)  # Check the status of an async render task.
diagram.get_template(name: str)  # Load a diagram template by name.
diagram.list_providers(focus_only: bool=False)  # List all available diagram providers.
diagram.render_diagram(source: str | None=None, source_file: str | None=None, provider: str | None=None, name: str | None=None, output_format: Literal['svg', 'png', 'pdf']='svg', output_dir: str | None=None, save_source: bool | None=None, async_mode: bool=False)  # Render a diagram from source code or file via Kroki.
diagram.render_directory(directory: str, output_format: Literal['svg', 'png', 'pdf']='svg', output_dir: str | None=None, recursive: bool=False, pattern: str='', max_concurrent: int=5)  # Discover and render all diagram source files in a directory.
```

## excel, xls
```python
excel.add_sheet(filepath: str, sheet_name: str)  # Add worksheet to existing workbook.
excel.cell_range(cell: str, right: int=0, down: int=0, left: int=0, up: int=0)  # (no file) Expand a cell into a range using CellRange.expand().
excel.cell_shift(cell: str, rows: int=0, cols: int=0)  # (no file) Shift a cell reference using CellRange.shift().
excel.copy_range(filepath: str, source_range: str, target_cell: str, sheet_name: str | None=None, target_sheet: str | None=None)  # Copy a range to another location.
excel.create(filepath: str, sheet_name: str='Sheet1', sheet_names: list[str] | None=None)  # Create new Excel workbook.
excel.create_table(filepath: str, data_range: str, table_name: str | None=None, sheet_name: str | None=None)  # Create a native Excel table from a data range.
excel.delete_cols(filepath: str, col: int | str, count: int=1, sheet_name: str | None=None)  # Delete columns starting at specified position.
excel.delete_rows(filepath: str, row: int, count: int=1, sheet_name: str | None=None)  # Delete rows starting at specified position.
excel.formula(filepath: str, cell: str, formula: str, sheet_name: str | None=None)  # Apply Excel formula to a cell.
excel.formulas(filepath: str, sheet_name: str | None=None)  # List all cells containing formulas.
excel.hyperlinks(filepath: str, sheet_name: str | None=None)  # List all hyperlinks in worksheet.
excel.info(filepath: str, include_ranges: bool=False)  # Get workbook metadata.
excel.insert_cols(filepath: str, col: int | str, count: int=1, sheet_name: str | None=None)  # Insert columns at specified position.
excel.insert_rows(filepath: str, row: int, count: int=1, sheet_name: str | None=None)  # Insert rows at specified position.
excel.merged_cells(filepath: str, sheet_name: str | None=None)  # List merged cell ranges in worksheet.
excel.named_ranges(filepath: str)  # List all named ranges in workbook.
excel.read(filepath: str, sheet_name: str | None=None, start_cell: str='A1', end_cell: str | None=None)  # Read data from Excel worksheet.
excel.search(filepath: str, pattern: str, sheet_name: str | None=None, regex: bool=False, first_only: bool=False)  # Search for values matching a pattern.
excel.sheets(filepath: str)  # List all sheets with visibility and type.
excel.table_data(filepath: str, table_name: str, row_index: int | None=None, sheet_name: str | None=None)  # Get table data with optional row selection.
excel.table_info(filepath: str, table_name: str, sheet_name: str | None=None)  # Get detailed table information.
excel.tables(filepath: str, sheet_name: str | None=None)  # List all defined tables in worksheet.
excel.used_range(filepath: str, sheet_name: str | None=None)  # Get the used range of a worksheet.
excel.write(filepath: str, data: list[list[Any]], sheet_name: str | None=None, start_cell: str='A1', create_if_missing: bool=False)  # Write data to Excel worksheet.
```

## file, f
```python
file.copy(source: str, dest: str, follow_symlinks: bool=True, overwrite: bool=False)  # Copy a file or directory.
file.delete(path: str, backup: bool=True, recursive: bool=False, dry_run: bool=False)  # Delete a file or directory.
file.edit(path: str, old_text: str, new_text: str, occurrence: int | None=None, encoding: str='utf-8', dry_run: bool=False)  # Edit a file by replacing text.
file.grep(pattern: str, path: str='.', glob: str | None=None, context: int=2, case_sensitive: bool=True, max_matches: int=500, fixed_strings: bool=False, gitignore: bool=True)  # Search file contents with regex (pure Python, no external tools required).
file.info(path: str, follow_symlinks: bool=True)  # Get file or directory metadata.
file.list(path: str='.', pattern: str | None=None, recursive: bool=False, include_hidden: bool=False, sort_by: str='name', reverse: bool=False, follow_symlinks: bool=False)  # List directory contents.
file.move(source: str, dest: str, overwrite: bool=False)  # Move or rename a file or directory.
file.read(path: str, offset: int=1, limit: int | None=None, encoding: str='utf-8', line_numbers: bool=False)  # Read file content with optional offset and limit.
file.read_batch(paths: List[str] | None=None, glob: str | None=None, encoding: str='utf-8', max_files: int=20)  # Read multiple files in a single call.
file.resolve(path: str='.', glob: str | List[str] | None=None, match: str | List[str] | None=None, kind: ResolveKind='file', gitignore: bool=True, include_hidden: bool=True, path_type: str='relative', multi: str='all', max_results: int=10)  # Resolve file or directory references to path strings.
file.search(path: str='.', pattern: str | None=None, glob: str | None=None, file_pattern: str | None=None, case_sensitive: bool=False, include_hidden: bool=False, max_results: int=100)  # Search for files by name pattern or glob.
file.slice(path: str, select: int | str | List[int | str], encoding: str='utf-8')  # Extract content from a file by line range, heading, or section number.
file.slice_batch(items: List[dict[str, Any]])  # Extract sections from multiple files in a single call.
file.toc(path: str, encoding: str='utf-8')  # Display a numbered section index for a file (table of contents).
file.tree(path: str='.', max_depth: int=3, include_hidden: bool=False)  # Display directory tree structure.
file.write(path: str, content: str, append: bool=False, create_dirs: bool=False, encoding: str='utf-8', dry_run: bool=False)  # Write content to a file.
```

## ground, g
```python
ground.dev(query: str, language: str='', framework: str='', timeout: float | None=None, max_sources: int | None=None, output_format: OutputFormat='full', model: str | None=None)  # Search for developer resources and documentation.
ground.docs(query: str, technology: str='', timeout: float | None=None, max_sources: int | None=None, output_format: OutputFormat='full', model: str | None=None)  # Search for official documentation.
ground.reddit(query: str, subreddit: str='', timeout: float | None=None, max_sources: int | None=None, output_format: OutputFormat='full', model: str | None=None)  # Search Reddit discussions.
ground.search(query: str, context: str='', focus: Literal['general', 'code', 'documentation', 'troubleshooting']='general', model: str | None=None, timeout: float | None=None, max_sources: int | None=None, output_format: OutputFormat='full', extract_schema: dict[str, Any] | None=None, return_provenance: bool=False)  # Search the web using Google Gemini with grounding.
ground.search_batch(queries: list[tuple[str, str] | str], context: str='', focus: Literal['general', 'code', 'documentation', 'troubleshooting']='general', model: str | None=None, timeout: float | None=None, max_sources: int | None=None, output_format: OutputFormat='full', extract_schema: dict[str, Any] | None=None, return_provenance: bool=False, retries: int=0, retry_delay_ms: int=250)  # Execute multiple grounded searches concurrently and return combined results.
```

## knowledge, kb
```python
knowledge.append(topic: str, content: str, db: str, id: str | None=None)  # Append content to an existing entry.
knowledge.ask(query: str, db: str, k: int=10, rerank: bool=True, expand: bool=False)  # Retrieve relevant chunks and synthesise an answer with citations.
knowledge.dbs()  # List all configured knowledge databases.
knowledge.delete(topic: str | None=None, source_path: str | None=None, id: str | None=None, db: str)  # Remove an entry by topic, id, or all chunks for a source file.
knowledge.grep(pattern: str, db: str, topic: str | None=None, category: str | None=None, context: int=2, limit: int=50, case_sensitive: bool=True, fixed_strings: bool=False)  # Regex search across knowledge base entries.
knowledge.info(db: str)  # Return database metadata and connection info.
knowledge.list(db: str, topic: str | None=None, category: str | None=None, tags: list[str] | None=None, limit: int=50, offset: int=0)  # List knowledge base entries with optional filters.
knowledge.read(topic: str | None=None, source_path: str | None=None, id: str | None=None, db: str)  # Read a single entry by topic or id, or all chunks for a source file.
knowledge.related(topic: str, db: str, direction: str='out', depth: int=1)  # Return chunks connected by link edges to the given topic.
knowledge.search(query: str, db: str, mode: str='hybrid', k: int | None=None, source: str | None=None, tag: str | None=None, category: str | None=None, after: str | None=None)  # Search the knowledge base using hybrid FTS5 + vector retrieval.
knowledge.slice(topic: str, db: str, heading: str | None=None, start: int | None=None, end: int | None=None)  # Extract a section from an entry by heading or line range.
knowledge.stats(db: str, top: int=5)  # Return entry statistics broken down by category, with links, AI enrichments, and most-accessed pages.
knowledge.toc(topic: str, db: str)  # Return the heading structure (table of contents) of an entry.
knowledge.update(topic: str, content: str, db: str, id: str | None=None, source_path: str | None=None, anchor: str | None=None)  # Replace the content of an existing entry.
knowledge.write(topic: str, content: str, db: str, category: str='note', tags: list[str] | None=None, meta: dict[str, Any] | None=None)  # Write a personal annotation to the knowledge database.
```

## localhist, lh
```python
localhist.add_exclude(rule: str | list[str])  # Append localhist-only exclude rules idempotently.
localhist.add_force_include(rule: str | list[str])  # Append localhist force-include pathspec rules idempotently.
localhist.autosave_list()  # List the shared localhist autosave watcher state.
localhist.autosave_start(path: str | None=None)  # Start or reuse the shared localhist autosave watcher.
localhist.autosave_stop(path: str | None=None)  # Stop the shared localhist autosave watcher.
localhist.diff(ref: str='HEAD', against: str | None=None, path: str | None=None)  # Return a patch for a local-history snapshot.
localhist.history(path: str, limit: int=20, follow: bool=True, date_format: str='%Y-%m-%d %H:%M:%S %Z')  # List snapshots that touched a project-relative path.
localhist.info()  # Inspect local-history initialization, config, paths, and current head.
localhist.init()  # Initialize the project-local history repository.
localhist.log(limit: int=20, date_format: str='%Y-%m-%d %H:%M:%S %Z')  # List local-history snapshots.
localhist.prune(older_than_days: int=30, gc: bool=True, dry_run: bool=True)  # Drop local-history snapshots older than the cutoff and reclaim disk.
localhist.restore(ref: str, paths: list[str], dry_run: bool=True)  # Restore selected paths from a local-history snapshot.
localhist.save(message: str, kind: SnapshotKind='', paths: str | list[str] | None=None)  # Create a local-history snapshot.
localhist.show(ref: str, path: str, offset: int=1, limit: int | None=None, tail: int | None=None)  # Return file content from a local-history snapshot.
localhist.status(path: str | None=None, status: str | None=None, limit: int | None=None)  # Inspect local-history working tree status.
```

## mem
```python
mem.append(topic: str, content: str, id: str | None=None, separator: str='\n\n')  # Append content to an existing memory.
mem.ask(topic: str, q: str | list[str], id: str | None=None, model: str | None=None)  # Ask one or more questions about a stored memory using an LLM.
mem.context(topic: str | None=None, limit: int=5)  # Load most-accessed memories for quick context injection.
mem.count(topic: str | None=None, category: str | None=None)  # Count memories with optional filtering.
mem.decay(dry_run: bool=True)  # Apply importance decay to all memories based on age and access patterns.
mem.delete(topic: str | None=None, id: str | None=None, confirm: bool=False)  # Delete memories by topic prefix or ID.
mem.dump(topic: str | None=None, output: str | None=None)  # Dump memories to YAML format.
mem.flush(timeout: float=60.0)  # Wait for pending background embeddings to complete.
mem.grep(pattern: str, topic: str | None=None, category: str | None=None, tags: list[str] | None=None, context: int=2, case_sensitive: bool=True, limit: int=50, max_per_memory: int=10, fixed_strings: bool=False)  # Regex search across memory content with line-level results.
mem.history(topic: str | None=None, id: str | None=None, limit: int=10)  # List prior versions of a memory, newest first.
mem.inspect(topic: str, id: str | None=None)  # Return structured metadata for a single memory.
mem.list(topic: str | None=None, category: str | None=None, limit: int=50, format: str='list', depth: int=0)  # List memories with optional topic prefix and category filtering.
mem.load(file: str)  # Import memories from a YAML file. Skips duplicates by content hash.
mem.query(topic: str, expr: str, id: str | None=None)  # Evaluate a JMESPath expression against a memory stored as JSON or YAML.
mem.read(topic: str, id: str | None=None, meta: bool=False, mode: str | None=None)  # Read a memory by topic or ID.
mem.read_batch(topic: str | None=None, ids: list[str] | None=None, category: str | None=None, tags: list[str] | None=None, meta: bool=False, mode: str | None=None, limit: int=50)  # Read multiple memories by topic prefix, IDs, category, or tags.
mem.refresh(topic: str | None=None, dry_run: bool=True)  # Re-read source files for stale file-backed memories.
mem.reindex(topic: str | None=None, limit: int=100, dry_run: bool=True)  # Backfill or update vector embeddings for memories missing them.
mem.restore(input: str, topic: str | None=None, overwrite: bool=False)  # Restore memories from a snapshot directory (created by `mem.snapshot`).
mem.rollback(topic: str | None=None, id: str | None=None, version: int=1, history_id: str | None=None)  # Restore a memory to a prior version from mem.history().
mem.search(query: str, mode: str='semantic', topic: str | None=None, category: str | None=None, limit: int | None=None, tags: list[str] | None=None, extract: int | None=None)  # Search memories by semantic similarity, keyword matching, or hybrid.
mem.slice(topic: str, select: int | str | list[int | str], id: str | None=None)  # Extract content by section number, heading path, line range, or mixed list.
mem.slice_batch(items: list[dict[str, Any]])  # Extract sections from multiple memories in a single call.
mem.snapshot(output: str, topic: str | None=None, ext: str='', on_conflict: str='skip')  # Write memories to a directory as individual files with an index.yaml.
mem.stale(topic: str | None=None)  # Check which file-backed memories have outdated content relative to their source files.
mem.stats()  # Show memory statistics - counts, sizes, category breakdown, topic tree.
mem.toc(topic: str, id: str | None=None)  # Display a numbered section index for a memory with table of contents.
mem.update(topic: str, content: str, id: str | None=None)  # Update a memory's content. Must match exactly one memory.
mem.update_batch(search_text: str, replace_text: str, topic: str | None=None, dry_run: bool=True)  # Search and replace text across matching memories.
mem.write(topic: str, content: str | None=None, category: str='note', tags: list[str] | None=None, relevance: int=5, file: str | None=None, toc: bool=True)  # Store a memory with topic, content, and optional metadata.
mem.write_batch(topic: str, glob_pattern: str, category: str='note', tags: list[str] | None=None, relevance: int=5, toc: bool=True)  # Store multiple memories from files matching a glob pattern.
```

## ot
```python
ot.aliases(pattern: str='', info: InfoLevel='default')  # List aliases with optional filtering.
ot.config()  # Show key configuration values.
ot.debug(verbose: bool=False, env_vars: bool=False, dependencies: bool=False, prompts: bool=False)  # Get comprehensive debug information about this OneTool installation.
ot.help(query: str='', topic: str='', info: HelpInfoLevel='default', ask: str='', answer_only: bool=False)  # Get help on OneTool commands, tools, packs, snippets, or aliases.
ot.pack_info(name: str='', info: InfoLevel='default')  # Get detailed info for a single pack.
ot.packs(pattern: str='', info: InfoLevel='default')  # List all packs with optional filtering.
ot.prompt(server: str, name: str, arguments: dict[str, Any] | None=None)  # Render one prompt through a connected MCP server.
ot.prompts(server: str)  # List prompt metadata exposed by one connected MCP server.
ot.reload()  # Force reload of all configuration.
ot.resource(server: str, uri: str)  # Read one resource from a connected MCP server.
ot.resources(server: str)  # List resource metadata exposed by one connected MCP server.
ot.result(handle: str, offset: int=1, limit: int=100, search: str='', fuzzy: bool=False, tail: int=0, context: int=0)  # Query stored large output results with pagination and filtering.
ot.security(check: str='')  # Check security rules for code validation.
ot.server(status: str | None=None)  # List or inspect runtime proxy server state.
ot.servers(pattern: str='', info: ServerInfoLevel='default')  # List configured MCP proxy servers with optional filtering.
ot.snippet_info(name: str='', pattern: str='', info: InfoLevel='default')  # Get detailed info for one or more snippets.
ot.snippets(pattern: str='', info: InfoLevel='default')  # List snippets with optional filtering.
ot.stats(period: str='all', tool: str='', info: InfoLevel='default', output: str='')  # Get runtime statistics for OneTool usage.
ot.status()  # Report cheap runtime status for OneTool components.
ot.tool_info(name: str='', pattern: str='', info: InfoLevel='default')  # Get detailed info for one or more tools.
ot.tools(pattern: str='', info: InfoLevel='default')  # List all available tools with optional filtering.
ot.version()  # Return OneTool version string.
```

## ot_context, ctx
```python
ot_context.append(handle: str, content: str, store: HandleStore | None=None)  # Append content to an existing handle.
ot_context.ask(handle: str, q: str | list[str], model: str | None=None, store: HandleStore | None=None)  # Send one or more questions about stored content to an LLM.
ot_context.delete(handle: str, store: HandleStore | None=None)  # Delete a single handle and both associated files.
ot_context.grep(handle: str, pattern: str, context: int=0, ignore_case: bool=True, limit: int=500, store: HandleStore | None=None, config: Config | None=None)  # Regex line search with optional context lines and long-line truncation.
ot_context.inspect(handle: str, store: HandleStore | None=None)  # Return detailed metadata for a single handle.
ot_context.list(source: str='', status: str='', store: HandleStore | None=None)  # Return all active (non-expired) handles with summary information.
ot_context.purge(delete_all: bool=False, minutes: int | None=None, source: str='', status: str='', store: HandleStore | None=None)  # Delete handles matching the given filters.
ot_context.query(handle: str, expr: str, store: HandleStore | None=None)  # Evaluate a jmespath expression against a json or yaml handle.
ot_context.read(handle: str, offset: int=1, limit: int=100, tail: int=0, mode: str='', store: HandleStore | None=None, config: Config | None=None)  # Return paginated raw content from a stored handle.
ot_context.slice(handle: str, select: str, store: HandleStore | None=None)  # Extract content by section number, heading name, or line range.
ot_context.stats(store: HandleStore | None=None)  # Return session-level storage metrics.
ot_context.toc(handle: str, store: HandleStore | None=None)  # Return a format-aware table of contents for a handle.
ot_context.write(content: str | dict[str, Any], source: str='', verbose: bool=False, store: HandleStore | None=None, config: Config | None=None)  # Store content synchronously and return a handle dict immediately.
```

## ot_forge, forge
```python
ot_forge.create_ext(name: str, pack_name: str | None=None, function: str='run', description: str='My extension tool', function_description: str='Execute the tool function', api_key: str='MY_API_KEY')  # Create a new extension tool.
ot_forge.validate_ext(path: str)  # Validate an extension before reload.
```

## ot_image, img
```python
ot_image.ask(img: str | list[str], q: str | list[str], max_edge: int=1568)  # Send one or more questions about one or more images to the vision model.
ot_image.clip_ask(q: str | list[str], max_edge: int=1568)  # Ask a question about the current clipboard image.
ot_image.clip_view()  # Extract a structured summary of the current clipboard image.
ot_image.delete(handle: str)  # Delete a loaded image and remove it from the session cache.
ot_image.list()  # List all images in ``.onetool/images/``.
ot_image.load(img: str, handle: str | None=None, max_edge: int=1568)  # Load a single image into session storage and return a stable handle.
ot_image.load_batch(img: str | list[str], max_edge: int=1568)  # Load multiple images and return a list of result dicts.
ot_image.purge(all: bool=False, minutes: int=15)  # Delete images from ``.onetool/images/``, optionally filtered by age.
ot_image.summary(img: str)  # Extract and cache a structured summary of an image.
```

## ot_llm, llm
```python
ot_llm.transform(data: Any, prompt: str, model: str | None=None, json_mode: bool=False)  # Transform data using an LLM.
ot_llm.transform_file(prompt: str, in_file: str, out_file: str, model: str | None=None, json_mode: bool=False)  # Transform a file's content using an LLM and write to output file.
```

## ot_secrets, sec
```python
ot_secrets.audit(file: str | None=None)  # Scan a secrets YAML file for unencrypted values.
ot_secrets.encrypt(file: str | None=None, backup: bool=False)  # Encrypt plain values in a secrets YAML file in-place.
ot_secrets.get(key: str, file: str | None=None, out_file: str | None=None)  # Look up a secret's existence/metadata, never returning its plaintext value.
ot_secrets.init(label: str='', force: bool=False)  # Generate an age X25519 identity and store it in the OS keychain.
ot_secrets.rotate(file: str | None=None, backup: bool=False)  # Generate a new identity and re-encrypt all encrypted values in-place.
ot_secrets.set(key: str, value: str, file: str | None=None)  # Set a single secret, encrypting it in place if an identity exists.
ot_secrets.status(file: str | None=None)  # Check secrets identity status and optionally inspect a secrets file.
ot_secrets.unset(key: str, file: str | None=None)  # Remove a single key from a secrets YAML file.
```

## ot_servers, srv
```python
ot_servers.disable(name: str)  # Disable an enabled proxy server and disconnect it.
ot_servers.enable(name: str)  # Enable a disabled proxy server and connect it.
ot_servers.restart(name: str)  # Reconnect a proxy server with its current on-disk config.
ot_servers.status(name: str)  # Show detailed status for one proxy server.
```

## ot_timer, tmr
```python
ot_timer.clear(results: bool=False)  # Clear all running timers and optionally stored results.
ot_timer.elapsed(name: str='_default', store_as: str | None=None)  # Get elapsed time for a named timer.
ot_timer.list()  # Return all stored timer results and currently running timers.
ot_timer.start(name: str='_default')  # Start or restart a named timer.
ot_timer.stop(name: str='_default', store_as: str | None=None)  # Stop and remove a named timer, returning its final elapsed time.
```

## package, pkg
```python
package.audit(path: str='.', registry: str | None=None)  # Audit project dependencies against latest registry versions.
package.models(query: str='', provider: str='', limit: int=20)  # Search OpenRouter AI models.
package.npm(packages: list[str])  # Check latest npm package versions.
package.pypi(packages: list[str])  # Check latest PyPI package versions.
package.version(registry: str, packages: list[str] | dict[str, str])  # Check latest versions for packages from a registry.
```

## play_util, play
```python
play_util.clear_annotations(server: str='playwright')  # Remove all annotations and visual highlights from the page.
play_util.enable_auto_inject(server: str='playwright')  # Register inject.js as a Playwright init script for automatic injection.
play_util.guide_user(task: str, steps: list[dict[str, str]], server: str='playwright')  # Highlight a sequence of elements to guide the user through a task.
play_util.highlight_element(selector: str, label: str, color: str='orange', element_id: str | None=None, server: str='playwright')  # Highlight elements matching a CSS selector with an annotation overlay.
play_util.inject_annotations(server: str='playwright')  # Inject the annotation script into the current browser page.
play_util.scan_annotations(server: str='playwright')  # Read all current annotations from the page.
```

## ripgrep, rg
```python
ripgrep.count(pattern: str, path: str='.', count_all: bool=False, file_type: str | None=None, glob: str | None=None, include_hidden: bool=False, no_ignore: bool=False)  # Count pattern occurrences in files.
ripgrep.files(path: str='.', file_type: str | None=None, glob: str | None=None, include_hidden: bool=False, no_ignore: bool=False, sort: str | None=None)  # List files that would be searched.
ripgrep.search(pattern: str, path: str='.', case_sensitive: bool=True, fixed_strings: bool=False, file_type: str | None=None, glob: str | None=None, context: int=0, before_context: int=0, after_context: int=0, max_per_file: int | None=None, limit: int | None=None, word_match: bool=False, include_hidden: bool=False, invert_match: bool=False, multiline: bool=False, only_matching: bool=False, no_ignore: bool=False, heading: bool=False, follow_symlinks: bool=False, smart_case: bool=False, filenames_only: bool=False)  # Search files for patterns using ripgrep.
ripgrep.types()  # List supported file types.
```

## tavily, tav
```python
tavily.extract(urls: list[str], format: str='markdown', extract_depth: str='basic')  # Extract content from one or more URLs using Tavily.
tavily.extract_batch(url_sets: list[tuple[list[str], str] | list[str]], format: str='markdown', extract_depth: str='basic', retries: int=0, retry_delay_ms: int=250)  # Extract content from multiple URL sets concurrently.
tavily.research(input: str, model: str='auto', timeout_seconds: int=300)  # Perform comprehensive multi-source research using Tavily Research API.
tavily.search(query: str, max_results: int=5, search_depth: str='basic', topic: str='general', output_format: OutputFormat='full', min_score: float | None=None, max_sources: int | None=None, time_range: str | None=None, days: int=3, include_domains: list[str] | None=None, exclude_domains: list[str] | None=None, extract_schema: dict[str, Any] | None=None, return_provenance: bool=False)  # Search the web using Tavily AI-powered search API.
tavily.search_batch(queries: list[tuple[str, str] | str], max_results: int=2, search_depth: str='basic', topic: str='general', output_format: OutputFormat='full', min_score: float | None=None, max_sources: int | None=None, time_range: str | None=None, days: int=3, include_domains: list[str] | None=None, exclude_domains: list[str] | None=None, extract_schema: dict[str, Any] | None=None, return_provenance: bool=False, retries: int=0, retry_delay_ms: int=250)  # Execute multiple Tavily searches concurrently and return combined results.
```

## webfetch, wf
```python
webfetch.fetch(url: str, output_format: Literal['text', 'markdown', 'json', 'html']='markdown', include_links: bool=False, include_images: bool=False, include_tables: bool=True, include_comments: bool=False, include_formatting: bool=True, include_metadata: bool=False, favor_precision: bool=False, favor_recall: bool=False, fast: bool=False, target_language: str | None=None, max_length: int | None=None, timeout: float | None=None, use_cache: bool=True)  # Fetch and extract main content from a web page.
webfetch.fetch_batch(urls: list[str] | list[tuple[str, str]], output_format: Literal['text', 'markdown', 'json', 'html']='markdown', include_links: bool=False, include_images: bool=False, include_tables: bool=True, include_comments: bool=False, include_formatting: bool=True, favor_precision: bool=False, favor_recall: bool=False, fast: bool=False, target_language: str | None=None, max_length: int | None=None, timeout: float | None=None, use_cache: bool=True, max_workers: int=5)  # Fetch multiple URLs concurrently and return concatenated results.
```

## whiteboard, wb, excalidraw
```python
whiteboard.align(ids: list[str], axis: str)  # Align or distribute a set of shapes using Excalidraw's built-in actions.
whiteboard.boards()  # List all active whiteboard session boards.
whiteboard.clear(board: str | None=None)  # Delete the session file for the given board and optionally clear the canvas.
whiteboard.close()  # Close the excalidraw browser and reset all Python state.
whiteboard.draw(input: str, board: str | None=None)  # Add or update diagram elements from DSL. Always additive — never clears.
whiteboard.embed_dsl(board: str | None=None)  # Embed the current DSL as a note element on the canvas.
whiteboard.erase(ids: list[str], board: str | None=None)  # Remove individual elements from the canvas and Python state.
whiteboard.fit()  # Fit all elements in view.
whiteboard.hard_reset()  # Reset Python DSL state unconditionally; attempt canvas clear if browser is available.
whiteboard.help()  # Return the full DSL and style reference. Call this before using whiteboard.draw or whiteboard.style.
whiteboard.layout(direction: str='DOWN', gap_layer: int=80, gap_node: int=40, algorithm: str='layered', node_placement: str='NETWORK_SIMPLEX', crossing_min: str='LAYER_SWEEP', cycle_breaking: str='GREEDY', arrow_type: str | None=None, elk_options: dict[str, str] | None=None, board: str | None=None)  # Apply ELK.js graph layout to the current whiteboard.
whiteboard.load(file: str, board: str | None=None)  # Restore diagram from a native ``.excalidraw`` file.
whiteboard.note(input: str, background: str='#f5f5dc', board: str | None=None)  # Insert ASCII-rendered text annotations onto the canvas.
whiteboard.open()  # Open excalidraw.com and start with a clean canvas.
whiteboard.read_scene(info: str='default', board: str | None=None)  # Return a structured text summary of all canvas elements.
whiteboard.save(file: str, board: str | None=None)  # Save current diagram to a native ``.excalidraw`` JSON file.
whiteboard.screenshot(file: str | None=None, board: str | None=None)  # Take a screenshot of the current canvas as PNG.
whiteboard.scroll(dx: int=0, dy: int=0)  # Pan the canvas by (dx, dy) pixels.
whiteboard.share(board: str | None=None)  # Generate a shareable Excalidraw link for the current canvas.
whiteboard.style(ids: list[str], style: str, board: str | None=None)  # Apply visual style properties to existing canvas elements in bulk.
whiteboard.sync(board: str | None=None)  # Sync Python DSL state from the ``__otDSL`` canvas element.
whiteboard.zoom(level: float)  # Set zoom level. Pass 0 to fit all elements in view.
```

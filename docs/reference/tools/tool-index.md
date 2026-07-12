# OneTool MCP Tool Index

packs=28 tools=253

## arch
```python
arch.bundle_solution(directory: str, output_path: str | None=None, include: str | None=None)
arch.export_yaml(input_path: str, output_path: str)
arch.generate(input_path: str, output_dir: str | None=None, profile: str | None=None, profile_yaml: str | None=None, title: str | None=None, include_tags: list[str] | None=None, exclude_tags: list[str] | None=None, force: bool=False)
arch.import_yaml(input_path: str, template_path: str, output_path: str)
arch.validate(input_path: str)
```

## brave, br
```python
brave.image(query: str, max_results: int=10, country: str='US', search_lang: str='en', safesearch: str='strict', output_format: OutputFormat='full', max_sources: int | None=None)
brave.news(query: str, max_results: int=10, offset: int=0, country: str='US', search_lang: str='en', freshness: str | None=None, output_format: OutputFormat='full', max_sources: int | None=None)
brave.search(query: str, max_results: int=10, offset: int=0, country: str='US', search_lang: str='en', safesearch: str='moderate', freshness: str | None=None, output_format: OutputFormat='full', max_sources: int | None=None)
brave.search_batch(queries: list[tuple[str, str] | str], max_results: int=2, country: str='US', search_lang: str='en', safesearch: str='moderate', freshness: str | None=None, output_format: OutputFormat='full', max_sources: int | None=None, retries: int=0, retry_delay_ms: int=250)
brave.video(query: str, max_results: int=10, country: str='US', search_lang: str='en', freshness: str | None=None, output_format: OutputFormat='full', max_sources: int | None=None)
```

## chrome_util, chrome
```python
chrome_util.clear_annotations(server: str='chrome_devtools')
chrome_util.guide_user(task: str, steps: list[dict[str, str]], server: str='chrome_devtools')
chrome_util.highlight_element(selector: str, label: str, color: str='orange', element_id: str | None=None, server: str='chrome_devtools')
chrome_util.inject_annotations(server: str='chrome_devtools')
chrome_util.scan_annotations(server: str='chrome_devtools')
```

## console
```python
console.clear()
console.display(content: Any=None, /, path: str | None=None, old_path: str | None=None, new_path: str | None=None, kind: ConsoleKind | None=None, title: str | None=None, metadata: dict[str, str] | None=None)
console.list(limit: int=100, offset: int=0, kind: ConsoleKind | None=None, source: str | None=None)
console.read(id: str)
console.show(kind: ConsoleKind, content: str | dict[str, Any] | List[Any], metadata: dict[str, str] | None=None)
```

## context7, c7
```python
context7.doc(library_id: str, query: str)
context7.search(query: str, library_name: str, output_format: str='str')
```

## convert, cv
```python
convert.auto(pattern: str, output_dir: str)
convert.excel(pattern: str, output_dir: str, include_formulas: bool=False, compute_formulas: bool=False)
convert.pdf(pattern: str, output_dir: str)
convert.powerpoint(pattern: str, output_dir: str, include_notes: bool=False)
convert.word(pattern: str, output_dir: str)
```

## db
```python
db.query(sql: str, db_url: str, params: dict[str, Any] | None=None, read_only: bool=False)
db.sample(table: str, db_url: str, limit: int=10)
db.schema(table_names: list[str], db_url: str)
db.tables(db_url: str, filter: str | None=None, ignore_case: bool=False, include_row_count: bool=False)
```

## diagram, diag
```python
diagram.batch_render(sources: list[dict[str, str]], output_format: Literal['svg', 'png', 'pdf']='svg', output_dir: str | None=None, max_concurrent: int=5)
diagram.generate_source(source: str, provider: Literal['mermaid', 'plantuml', 'd2', 'graphviz', 'ditaa', 'erd', 'nomnoml', 'svgbob'] | str, name: str, output_dir: str | None=None, validate: bool=True)
diagram.get_diagram_instructions(provider: Literal['mermaid', 'plantuml', 'd2'] | str | None=None)
diagram.get_diagram_policy()
diagram.get_output_config()
diagram.get_playground_url(source: str, provider: Literal['mermaid', 'plantuml', 'd2'] | str)
diagram.get_render_status(task_id: str)
diagram.get_template(name: str)
diagram.list_providers(focus_only: bool=False)
diagram.render_diagram(source: str | None=None, source_file: str | None=None, provider: str | None=None, name: str | None=None, output_format: Literal['svg', 'png', 'pdf']='svg', output_dir: str | None=None, save_source: bool | None=None, async_mode: bool=False)
diagram.render_directory(directory: str, output_format: Literal['svg', 'png', 'pdf']='svg', output_dir: str | None=None, recursive: bool=False, pattern: str='', max_concurrent: int=5)
```

## excel, xls
```python
excel.add_sheet(filepath: str, sheet_name: str)
excel.cell_range(cell: str, right: int=0, down: int=0, left: int=0, up: int=0)
excel.cell_shift(cell: str, rows: int=0, cols: int=0)
excel.copy_range(filepath: str, source_range: str, target_cell: str, sheet_name: str | None=None, target_sheet: str | None=None)
excel.create(filepath: str, sheet_name: str='Sheet1', sheet_names: list[str] | None=None)
excel.create_table(filepath: str, data_range: str, table_name: str | None=None, sheet_name: str | None=None)
excel.delete_cols(filepath: str, col: int | str, count: int=1, sheet_name: str | None=None)
excel.delete_rows(filepath: str, row: int, count: int=1, sheet_name: str | None=None)
excel.formula(filepath: str, cell: str, formula: str, sheet_name: str | None=None)
excel.formulas(filepath: str, sheet_name: str | None=None)
excel.hyperlinks(filepath: str, sheet_name: str | None=None)
excel.info(filepath: str, include_ranges: bool=False)
excel.insert_cols(filepath: str, col: int | str, count: int=1, sheet_name: str | None=None)
excel.insert_rows(filepath: str, row: int, count: int=1, sheet_name: str | None=None)
excel.merged_cells(filepath: str, sheet_name: str | None=None)
excel.named_ranges(filepath: str)
excel.read(filepath: str, sheet_name: str | None=None, start_cell: str='A1', end_cell: str | None=None)
excel.search(filepath: str, pattern: str, sheet_name: str | None=None, regex: bool=False, first_only: bool=False)
excel.sheets(filepath: str)
excel.table_data(filepath: str, table_name: str, row_index: int | None=None, sheet_name: str | None=None)
excel.table_info(filepath: str, table_name: str, sheet_name: str | None=None)
excel.tables(filepath: str, sheet_name: str | None=None)
excel.used_range(filepath: str, sheet_name: str | None=None)
excel.write(filepath: str, data: list[list[Any]], sheet_name: str | None=None, start_cell: str='A1', create_if_missing: bool=False)
```

## file, f
```python
file.copy(source: str, dest: str, follow_symlinks: bool=True, overwrite: bool=False)
file.delete(path: str, backup: bool=True, recursive: bool=False, dry_run: bool=False)
file.edit(path: str, old_text: str, new_text: str, occurrence: int | None=None, encoding: str='utf-8', dry_run: bool=False)
file.grep(pattern: str, path: str='.', glob: str | None=None, context: int=2, case_sensitive: bool=True, max_matches: int=500, fixed_strings: bool=False, gitignore: bool=True)
file.info(path: str, follow_symlinks: bool=True)
file.list(path: str='.', pattern: str | None=None, recursive: bool=False, include_hidden: bool=False, sort_by: str='name', reverse: bool=False, follow_symlinks: bool=False)
file.move(source: str, dest: str, overwrite: bool=False)
file.read(path: str, offset: int=1, limit: int | None=None, encoding: str='utf-8', line_numbers: bool=False)
file.read_batch(paths: List[str] | None=None, glob: str | None=None, encoding: str='utf-8', max_files: int=20)
file.resolve(path: str='.', glob: str | List[str] | None=None, match: str | List[str] | None=None, kind: ResolveKind='file', gitignore: bool=True, include_hidden: bool=True, path_type: str='relative', multi: str='all', max_results: int=10)
file.search(path: str='.', pattern: str | None=None, glob: str | None=None, file_pattern: str | None=None, case_sensitive: bool=False, include_hidden: bool=False, max_results: int=100)
file.slice(path: str, select: int | str | List[int | str], encoding: str='utf-8')
file.slice_batch(items: List[dict[str, Any]])
file.toc(path: str, encoding: str='utf-8')
file.tree(path: str='.', max_depth: int=3, include_hidden: bool=False)
file.write(path: str, content: str, append: bool=False, create_dirs: bool=False, encoding: str='utf-8', dry_run: bool=False)
```

## ground, g
```python
ground.dev(query: str, language: str='', framework: str='', timeout: float | None=None, max_sources: int | None=None, output_format: OutputFormat='full', model: str | None=None)
ground.docs(query: str, technology: str='', timeout: float | None=None, max_sources: int | None=None, output_format: OutputFormat='full', model: str | None=None)
ground.reddit(query: str, subreddit: str='', timeout: float | None=None, max_sources: int | None=None, output_format: OutputFormat='full', model: str | None=None)
ground.search(query: str, context: str='', focus: Literal['general', 'code', 'documentation', 'troubleshooting']='general', model: str | None=None, timeout: float | None=None, max_sources: int | None=None, output_format: OutputFormat='full', extract_schema: dict[str, Any] | None=None, return_provenance: bool=False)
ground.search_batch(queries: list[tuple[str, str] | str], context: str='', focus: Literal['general', 'code', 'documentation', 'troubleshooting']='general', model: str | None=None, timeout: float | None=None, max_sources: int | None=None, output_format: OutputFormat='full', extract_schema: dict[str, Any] | None=None, return_provenance: bool=False, retries: int=0, retry_delay_ms: int=250)
```

## knowledge, kb
```python
knowledge.append(topic: str, content: str, db: str, id: str | None=None)
knowledge.ask(query: str, db: str, k: int=10, rerank: bool=True, expand: bool=False)
knowledge.dbs()
knowledge.delete(topic: str | None=None, source_path: str | None=None, id: str | None=None, db: str)
knowledge.grep(pattern: str, db: str, topic: str | None=None, category: str | None=None, context: int=2, limit: int=50, case_sensitive: bool=True, fixed_strings: bool=False)
knowledge.info(db: str)
knowledge.list(db: str, topic: str | None=None, category: str | None=None, tags: list[str] | None=None, limit: int=50, offset: int=0)
knowledge.read(topic: str | None=None, source_path: str | None=None, id: str | None=None, db: str)
knowledge.related(topic: str, db: str, direction: str='out', depth: int=1)
knowledge.search(query: str, db: str, mode: str='hybrid', k: int | None=None, source: str | None=None, tag: str | None=None, category: str | None=None, after: str | None=None)
knowledge.slice(topic: str, db: str, heading: str | None=None, start: int | None=None, end: int | None=None)
knowledge.stats(db: str, top: int=5)
knowledge.toc(topic: str, db: str)
knowledge.update(topic: str, content: str, db: str, id: str | None=None, source_path: str | None=None, anchor: str | None=None)
knowledge.write(topic: str, content: str, db: str, category: str='note', tags: list[str] | None=None, meta: dict[str, Any] | None=None)
```

## localhist, lh
```python
localhist.add_exclude(rule: str | list[str])
localhist.add_force_include(rule: str | list[str])
localhist.autosave_list()
localhist.autosave_start(path: str | None=None)
localhist.autosave_stop(path: str | None=None)
localhist.diff(ref: str='HEAD', against: str | None=None, path: str | None=None)
localhist.history(path: str, limit: int=20, follow: bool=True, date_format: str='%Y-%m-%d %H:%M:%S %Z')
localhist.info()
localhist.init()
localhist.log(limit: int=20, date_format: str='%Y-%m-%d %H:%M:%S %Z')
localhist.prune(older_than_days: int=30, gc: bool=True, dry_run: bool=True)
localhist.restore(ref: str, paths: list[str], dry_run: bool=True)
localhist.save(message: str, kind: SnapshotKind='', paths: str | list[str] | None=None)
localhist.show(ref: str, path: str, offset: int=1, limit: int | None=None, tail: int | None=None)
localhist.status(path: str | None=None, status: str | None=None, limit: int | None=None)
```

## mem
```python
mem.append(topic: str, content: str, id: str | None=None, separator: str='\n\n')
mem.ask(topic: str, q: str | list[str], id: str | None=None, model: str | None=None)
mem.context(topic: str | None=None, limit: int=5)
mem.count(topic: str | None=None, category: str | None=None)
mem.decay(dry_run: bool=True)
mem.delete(topic: str | None=None, id: str | None=None, confirm: bool=False)
mem.dump(topic: str | None=None, output: str | None=None)
mem.flush(timeout: float=60.0)
mem.grep(pattern: str, topic: str | None=None, category: str | None=None, tags: list[str] | None=None, context: int=2, case_sensitive: bool=True, limit: int=50, max_per_memory: int=10, fixed_strings: bool=False)
mem.history(topic: str | None=None, id: str | None=None, limit: int=10)
mem.inspect(topic: str, id: str | None=None)
mem.list(topic: str | None=None, category: str | None=None, limit: int=50, format: str='list', depth: int=0)
mem.load(file: str)
mem.query(topic: str, expr: str, id: str | None=None)
mem.read(topic: str, id: str | None=None, meta: bool=False, mode: str | None=None)
mem.read_batch(topic: str | None=None, ids: list[str] | None=None, category: str | None=None, tags: list[str] | None=None, meta: bool=False, mode: str | None=None, limit: int=50)
mem.refresh(topic: str | None=None, dry_run: bool=True)
mem.reindex(topic: str | None=None, limit: int=100, dry_run: bool=True)
mem.restore(input: str, topic: str | None=None, overwrite: bool=False)
mem.rollback(topic: str | None=None, id: str | None=None, version: int=1, history_id: str | None=None)
mem.search(query: str, mode: str='semantic', topic: str | None=None, category: str | None=None, limit: int | None=None, tags: list[str] | None=None, extract: int | None=None)
mem.slice(topic: str, select: int | str | list[int | str], id: str | None=None)
mem.slice_batch(items: list[dict[str, Any]])
mem.snapshot(output: str, topic: str | None=None, ext: str='', on_conflict: str='skip')
mem.stale(topic: str | None=None)
mem.stats()
mem.toc(topic: str, id: str | None=None)
mem.update(topic: str, content: str, id: str | None=None)
mem.update_batch(search_text: str, replace_text: str, topic: str | None=None, dry_run: bool=True)
mem.write(topic: str, content: str | None=None, category: str='note', tags: list[str] | None=None, relevance: int=5, file: str | None=None, toc: bool=True)
mem.write_batch(topic: str, glob_pattern: str, category: str='note', tags: list[str] | None=None, relevance: int=5, toc: bool=True)
```

## ot
```python
ot.aliases(pattern: str='', info: InfoLevel='default')
ot.config()
ot.debug(verbose: bool=False, env_vars: bool=False, dependencies: bool=False, prompts: bool=False)
ot.help(query: str='', info: HelpInfoLevel='default', ask: str='')
ot.pack_info(name: str='', info: InfoLevel='default')
ot.packs(pattern: str='', info: InfoLevel='default')
ot.reload()
ot.result(handle: str, offset: int=1, limit: int=100, search: str='', fuzzy: bool=False, tail: int=0, context: int=0)
ot.security(check: str='')
ot.server(status: str | None=None)
ot.servers(pattern: str='', info: ServerInfoLevel='default')
ot.snippet_info(name: str='', pattern: str='', info: InfoLevel='default')
ot.snippets(pattern: str='', info: InfoLevel='default')
ot.stats(period: str='all', tool: str='', info: InfoLevel='default', output: str='')
ot.status()
ot.tool_info(name: str='', pattern: str='', info: InfoLevel='default')
ot.tools(pattern: str='', info: InfoLevel='default')
ot.version()
```

## ot_context, ctx
```python
ot_context.append(handle: str, content: str, store: HandleStore | None=None)
ot_context.ask(handle: str, q: str | list[str], model: str | None=None, store: HandleStore | None=None)
ot_context.delete(handle: str, store: HandleStore | None=None)
ot_context.grep(handle: str, pattern: str, context: int=0, ignore_case: bool=True, limit: int=500, store: HandleStore | None=None, config: Config | None=None)
ot_context.inspect(handle: str, store: HandleStore | None=None)
ot_context.list(source: str='', status: str='', store: HandleStore | None=None)
ot_context.purge(delete_all: bool=False, minutes: int | None=None, source: str='', status: str='', store: HandleStore | None=None)
ot_context.query(handle: str, expr: str, store: HandleStore | None=None)
ot_context.read(handle: str, offset: int=1, limit: int=100, tail: int=0, mode: str='', store: HandleStore | None=None, config: Config | None=None)
ot_context.slice(handle: str, select: str, store: HandleStore | None=None)
ot_context.stats(store: HandleStore | None=None)
ot_context.toc(handle: str, store: HandleStore | None=None)
ot_context.write(content: str | dict[str, Any], source: str='', verbose: bool=False, store: HandleStore | None=None, config: Config | None=None)
```

## ot_forge, forge
```python
ot_forge.create_ext(name: str, pack_name: str | None=None, function: str='run', description: str='My extension tool', function_description: str='Execute the tool function', api_key: str='MY_API_KEY')
ot_forge.validate_ext(path: str)
```

## ot_image, img
```python
ot_image.ask(img: str | list[str], q: str | list[str], max_edge: int=1568)
ot_image.clip_ask(q: str | list[str], max_edge: int=1568)
ot_image.clip_view()
ot_image.delete(handle: str)
ot_image.list()
ot_image.load(img: str, handle: str | None=None, max_edge: int=1568)
ot_image.load_batch(img: str | list[str], max_edge: int=1568)
ot_image.purge(all: bool=False, minutes: int=15)
ot_image.summary(img: str)
```

## ot_llm, llm
```python
ot_llm.transform(data: Any, prompt: str, model: str | None=None, json_mode: bool=False)
ot_llm.transform_file(prompt: str, in_file: str, out_file: str, model: str | None=None, json_mode: bool=False)
```

## ot_secrets, sec
```python
ot_secrets.audit(file: str | None=None)
ot_secrets.encrypt(file: str | None=None, backup: bool=False)
ot_secrets.get(key: str, file: str | None=None, out_file: str | None=None)
ot_secrets.init(label: str='', force: bool=False)
ot_secrets.rotate(file: str | None=None, backup: bool=False)
ot_secrets.set(key: str, value: str, file: str | None=None)
ot_secrets.status(file: str | None=None)
ot_secrets.unset(key: str, file: str | None=None)
```

## ot_servers, srv
```python
ot_servers.disable(name: str)
ot_servers.enable(name: str)
ot_servers.restart(name: str)
ot_servers.status(name: str)
```

## ot_timer, tmr
```python
ot_timer.clear(results: bool=False)
ot_timer.elapsed(name: str='_default', store_as: str | None=None)
ot_timer.list()
ot_timer.start(name: str='_default')
ot_timer.stop(name: str='_default', store_as: str | None=None)
```

## package, pkg
```python
package.audit(path: str='.', registry: str | None=None)
package.models(query: str='', provider: str='', limit: int=20)
package.npm(packages: list[str])
package.pypi(packages: list[str])
package.version(registry: str, packages: list[str] | dict[str, str])
```

## play_util, play
```python
play_util.clear_annotations(server: str='playwright')
play_util.enable_auto_inject(server: str='playwright')
play_util.guide_user(task: str, steps: list[dict[str, str]], server: str='playwright')
play_util.highlight_element(selector: str, label: str, color: str='orange', element_id: str | None=None, server: str='playwright')
play_util.inject_annotations(server: str='playwright')
play_util.scan_annotations(server: str='playwright')
```

## ripgrep, rg
```python
ripgrep.count(pattern: str, path: str='.', count_all: bool=False, file_type: str | None=None, glob: str | None=None, include_hidden: bool=False, no_ignore: bool=False)
ripgrep.files(path: str='.', file_type: str | None=None, glob: str | None=None, include_hidden: bool=False, no_ignore: bool=False, sort: str | None=None)
ripgrep.search(pattern: str, path: str='.', case_sensitive: bool=True, fixed_strings: bool=False, file_type: str | None=None, glob: str | None=None, context: int=0, before_context: int=0, after_context: int=0, max_per_file: int | None=None, limit: int | None=None, word_match: bool=False, include_hidden: bool=False, invert_match: bool=False, multiline: bool=False, only_matching: bool=False, no_ignore: bool=False, heading: bool=False, follow_symlinks: bool=False, smart_case: bool=False, filenames_only: bool=False)
ripgrep.types()
```

## tavily, tav
```python
tavily.extract(urls: list[str], format: str='markdown', extract_depth: str='basic')
tavily.extract_batch(url_sets: list[tuple[list[str], str] | list[str]], format: str='markdown', extract_depth: str='basic', retries: int=0, retry_delay_ms: int=250)
tavily.research(input: str, model: str='auto', timeout_seconds: int=300)
tavily.search(query: str, max_results: int=5, search_depth: str='basic', topic: str='general', output_format: OutputFormat='full', min_score: float | None=None, max_sources: int | None=None, time_range: str | None=None, days: int=3, include_domains: list[str] | None=None, exclude_domains: list[str] | None=None, extract_schema: dict[str, Any] | None=None, return_provenance: bool=False)
tavily.search_batch(queries: list[tuple[str, str] | str], max_results: int=2, search_depth: str='basic', topic: str='general', output_format: OutputFormat='full', min_score: float | None=None, max_sources: int | None=None, time_range: str | None=None, days: int=3, include_domains: list[str] | None=None, exclude_domains: list[str] | None=None, extract_schema: dict[str, Any] | None=None, return_provenance: bool=False, retries: int=0, retry_delay_ms: int=250)
```

## webfetch, wf
```python
webfetch.fetch(url: str, output_format: Literal['text', 'markdown', 'json', 'html']='markdown', include_links: bool=False, include_images: bool=False, include_tables: bool=True, include_comments: bool=False, include_formatting: bool=True, include_metadata: bool=False, favor_precision: bool=False, favor_recall: bool=False, fast: bool=False, target_language: str | None=None, max_length: int | None=None, timeout: float | None=None, use_cache: bool=True)
webfetch.fetch_batch(urls: list[str] | list[tuple[str, str]], output_format: Literal['text', 'markdown', 'json', 'html']='markdown', include_links: bool=False, include_images: bool=False, include_tables: bool=True, include_comments: bool=False, include_formatting: bool=True, favor_precision: bool=False, favor_recall: bool=False, fast: bool=False, target_language: str | None=None, max_length: int | None=None, timeout: float | None=None, use_cache: bool=True, max_workers: int=5)
```

## whiteboard, wb, excalidraw
```python
whiteboard.align(ids: list[str], axis: str)
whiteboard.boards()
whiteboard.clear(board: str | None=None)
whiteboard.close()
whiteboard.draw(input: str, board: str | None=None)
whiteboard.embed_dsl(board: str | None=None)
whiteboard.erase(ids: list[str], board: str | None=None)
whiteboard.fit()
whiteboard.hard_reset()
whiteboard.help()
whiteboard.layout(direction: str='DOWN', gap_layer: int=80, gap_node: int=40, algorithm: str='layered', node_placement: str='NETWORK_SIMPLEX', crossing_min: str='LAYER_SWEEP', cycle_breaking: str='GREEDY', arrow_type: str | None=None, elk_options: dict[str, str] | None=None, board: str | None=None)
whiteboard.load(file: str, board: str | None=None)
whiteboard.note(input: str, background: str='#f5f5dc', board: str | None=None)
whiteboard.open()
whiteboard.read_scene(info: str='default', board: str | None=None)
whiteboard.save(file: str, board: str | None=None)
whiteboard.screenshot(file: str | None=None, board: str | None=None)
whiteboard.scroll(dx: int=0, dy: int=0)
whiteboard.share(board: str | None=None)
whiteboard.style(ids: list[str], style: str, board: str | None=None)
whiteboard.sync(board: str | None=None)
whiteboard.zoom(level: float)
```

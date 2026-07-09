# Feature inventory approach

This file documents the process used to build `features.xlsx` so another LLM can repeat or audit it.

## Goal

Create a spreadsheet of every current, surviving feature and significant change since the first stable release. Removed features must not be listed. If a pack was introduced in one version and then materially improved later, include both the original pack row and later improvement rows.

## Output

Workbook: `features/features-v3.xlsx`

Columns:

- `feature`
- `pack`
- `build-date`
- `release-version`
- `description`
- `examples`
- `value`
- `loc`

`value` is a subjective 1-10 usefulness/value score. `loc` is an approximate current-code line count from `cloc`, scoped to the source paths that implement the feature area. Because many rows share an implementation area, `loc` is not additive across the sheet.

`pack` uses the canonical pack name from the module's `pack =` declaration (e.g. `ot_context`, not its alias `ctx`). Short aliases are themselves a feature row, not a naming convention for the sheet.

## Source priority

Use these sources in order:

1. Current source tree, to confirm a feature still exists.
2. `CHANGELOG.md`, release tags, and git log, to identify when the feature or change landed.
3. User-facing docs under `docs/`, especially `docs/reference/tools/*.md`, `docs/reference/tools/tool-index.md`, `docs/learn/*.md`, and `README.md`, to identify features and differentiators described to users.
4. Developer docs under `dev/`, especially architecture, config, security, logging, and tool-development guides, to catch cross-cutting QoL features.
5. Current OpenSpec specs under `openspec/specs/` and archived release specs under `openspec/changes/archive/`, to catch implemented contract-level features that docs may summarize only briefly.

Do not list a feature if it was removed from current source, even if it appears in old changelog entries or archived specs.

## Commands used

Start with project guidance:

```bash
sed -n '1,220p' dev/index.md
sed -n '1,220p' dev/agents/hints.md
sed -n '1,240p' dev/agents/project-map.md
```

Inspect release history:

```bash
git tag --sort=creatordate --format='%(refname:short)%09%(creatordate:short)%09%(objectname:short)'
git log --reverse --date=short --pretty=format:'%h%x09%ad%x09%s'
sed -n '1,280p' CHANGELOG.md
```

List current packs and public tools from source:

```bash
python - <<'PY'
import ast
from pathlib import Path
for p in sorted(list(Path('src/ottools').glob('*.py')) + list(Path('src/otdev/tools').glob('*.py')) + list(Path('src/otutil/tools').glob('*.py'))):
    t = ast.parse(p.read_text())
    pack = None
    aliases = []
    exports = []
    for n in t.body:
        if isinstance(n, ast.Assign):
            for target in n.targets:
                if isinstance(target, ast.Name) and target.id == 'pack' and isinstance(n.value, ast.Constant):
                    pack = n.value.value
                if isinstance(target, ast.Name) and target.id == 'pack_aliases' and isinstance(n.value, (ast.Tuple, ast.List)):
                    aliases = [getattr(x, 'value', None) for x in n.value.elts]
                if isinstance(target, ast.Name) and target.id == '__all__' and isinstance(n.value, (ast.Tuple, ast.List)):
                    exports = [getattr(x, 'value', None) for x in n.value.elts]
    if pack:
        print(f'{p}\tpack={pack}\taliases={aliases}\texports={exports}')
PY
```

Scan docs and specs for differentiators:

```bash
find docs dev openspec -type f \( -name '*.md' -o -name '*.yaml' -o -name '*.yml' \) | sort
rg -n "sanitize|injection|tool arg|argument|parameter|prefix|matching|alias|snippet|include:|stats|usage|metric|log|LogSpan|ctx|context|mem|memory|ripgrep|file\\.grep|file\\.resolve|file\\.slice|large output|result|handle|toc|slice|grep|query|search|batch|cache|reload|status|debug|security|direct|console|whiteboard|knowledge|ground|tavily|brave|webfetch|convert|excel|diagram|arch|localhist|secrets|server" docs dev openspec CHANGELOG.md README.md -S
sed -n '1,260p' docs/reference/tools/tool-index.md
```

Use focused reads for high-signal docs:

```bash
sed -n '1,470p' docs/reference/tools/ot_core.md
sed -n '1,260p' docs/reference/console-outbox-protocol.md
sed -n '1,260p' docs/learn/configuration.md
sed -n '1,260p' docs/learn/explicit-calls.md
sed -n '1,260p' docs/learn/security.md
sed -n '1,260p' docs/learn/direct-usage.md
sed -n '1,220p' docs/reference/tools/file.md
sed -n '1,240p' docs/reference/tools/mem.md
sed -n '1,220p' docs/reference/tools/ot_context.md
sed -n '1,220p' docs/reference/tools/ripgrep.md
sed -n '1,160p' docs/reference/cli/onetool.md
sed -n '1,80p' docs/telemetry.md
sed -n '1,260p' docs/learn/installation.md
```

The last three catch features earlier passes missed: the HTTP root MCP transport (`onetool serve --transport http`), anonymous telemetry with opt-out, and ot-ref agent skill distribution. Also read `openspec/specs/serve-prompts/spec.md` and `openspec/specs/serve-mcp-discoverability/spec.md` for the configurable prompts system and the `ot://tools` / `ot://tool/{name}` MCP resources.

Estimate LOC using `cloc` over current source paths only:

```bash
cloc --version
cloc --json --quiet src/ot src/onetool src/ottools src/otdev src/otutil
find src -type f -name '*.py' | sort | xargs cloc --by-file --csv --quiet
```

For row-level `loc`, group files by implementation area. Examples:

- `core-run`: `src/ot/server.py`, `src/ot/executor`, `src/ot/services.py`, `src/ot/tools.py`
- `security`: `src/ot/executor/validator.py`, `src/ot/utils/sanitize.py`, `src/ot/utils/pathsec.py`, `src/ot/config/secrets.py`, `src/ot/logging/redact.py`
- `file`: `src/otutil/tools/file.py`, `src/otutil/tools/_file_resolve_match.py`, `src/otutil/tools/_content_util`
- `mem`: `src/otutil/tools/mem.py`, `src/otutil/tools/_mem`
- `ctx`: `src/otutil/tools/ctx.py`, `src/ot/ctx`

Exclude generated dependencies and bundled frontend dependencies such as `node_modules`.

## Inclusion rules

Include:

- Current public packs and their major user-facing capabilities.
- Major changes to current packs after introduction.
- Cross-cutting runtime features: invocation contract, argument matching, aliases, snippets, output formatting, sanitization, config includes, metrics, logs, direct API, proxy behavior, server management, status/debug/help.
- Quality-of-life features that materially differentiate the tool from a thin wrapper around an upstream implementation.
- Documentation-backed tool differentiators such as batch retry envelopes, `.gitignore` awareness, format-aware table-of-contents, source freshness, file references, and bounded previews.

Exclude:

- Removed packs/features, even if historical: `code_search`, `aws`, `handoff`, `worktree`, `ide`, benchmark package, caveman compaction, old skill installer surface, old trigger forms, old config layout, old names kept only in historical docs.
- Purely internal refactors unless they are visible as stability, security, performance, or usability features.
- Roadmap-only features that are not in current source.

## Removed-feature checks

Before finalizing, search workbook rows for removed feature names. Expected result is zero for these terms, except incidental substrings inside unrelated words are acceptable and should be manually inspected:

```python
removed = [
    "code_search", "aws", "handoff", "worktree", "ide",
    "caveman", "bench", "__compact__", "ot.skills", "install_skills",
]
```

Also compare against current pack list from the AST scan above.

## Workbook build rules

- Use standard `.xlsx` only.
- Avoid conditional formatting if Excel displays repair warnings.
- The current workbook contains an Excel table object (`Table1`) covering the Features data. openpyxl does **not** adjust table ranges when rows are inserted or deleted, and Excel shows a "found a problem with some content" repair prompt if the table range, its embedded `autoFilter`, or its `sortState` reference rows that no longer exist. After any row insert/delete, update the table and drop the stale sort state:

  ```python
  t = ws.tables["Table1"]
  t.ref = f"A1:H{ws.max_row}"
  if t.autoFilter is not None:
      t.autoFilter.ref = t.ref
  t.sortState = None
  ```

- Do not add a worksheet-level autofilter (`ws.auto_filter.ref`); Excel forbids a sheet filter overlapping a table's own filter, and `Table1` already provides filter dropdowns.
- Freeze the header row (`ws.freeze_panes = "A2"`).
- Keep row heights large enough for wrapped descriptions/examples; when inserting rows with openpyxl, copy each cell's `_style`/`number_format` and the row height from an adjacent data row.
- Add a `Notes` sheet documenting scope, LOC method, source basis, and generation time.
- Verify with:

```bash
python - <<'PY'
from openpyxl import load_workbook
p = "features/features-v3.xlsx"
wb = load_workbook(p, data_only=True)  # not read_only: tables are unavailable in read-only mode
ws = wb["Features"]
print(ws.max_row, ws.max_column)
print([c.value for c in next(ws.iter_rows(min_row=1, max_row=1))])
t = ws.tables["Table1"]
assert t.ref == f"A1:H{ws.max_row}", f"stale table ref {t.ref} vs {ws.max_row} rows"
assert t.sortState is None, "drop sortState after row edits; its refs go stale"
assert ws.auto_filter.ref is None, "sheet-level autofilter must not overlap Table1"
print("table ref OK:", t.ref)
PY
unzip -t features/features-v3.xlsx
```

## Keeping the doc up to date

Update history lives in `features/CHANGELOG.md`, not in the workbook. Each
changelog entry records the git hash the workbook is current through
(**coverage**). To update:

1. Read the newest entry in `features/CHANGELOG.md` and take its coverage hash.
2. List what landed since: `git log --reverse --date=short --pretty=format:'%h%x09%ad%x09%s' <coverage>..HEAD`.
3. For each feature-bearing commit, add rows per the rules above (original
   pack row + later improvement rows; canonical pack names; skip docs-only
   and chore commits). Insert new rows at the top of the `Features` table to
   keep release-version descending order, and extend `Table1`'s `ref` and
   `autoFilter.ref` to cover them.
4. If a commit materially changed an existing feature area, refresh that
   area's `loc` with cloc over its source paths (all rows sharing the area
   get the same number).
5. Update the `Analysis` sheet's shown values (post-N totals and Grand Total)
   and set the pivot cache's `refreshOnLoad = True` so Excel rebuilds it.
6. Append a new entry to `features/CHANGELOG.md`: date/time, `coverage:
   <current HEAD short hash>`, rows added/changed and why, any loc refreshes,
   and commits reviewed but skipped (with reason).
7. Run the verification script above.

Do not record update metadata in the workbook's `Notes` sheet — it only
carries a pointer to the changelog.

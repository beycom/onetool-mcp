You have access to the `onetool` MCP server. Use it through the
`mcp__onetool__run` tool.

For this task, use OneTool before internal repository-inspection tools. Do not
use internal shell commands such as `rg`, `grep`, `find`, `cat`, `sed`, or
`ls` for repo discovery unless a OneTool call fails or is clearly unsuitable.
Keep edits and final verification in the task repository.

Use these tested OneTool calls exactly as patterns:

```python
ripgrep.search(
    pattern='search text or regex',
    path='.',
    glob='*.py',
    context=2,
    limit=20,
)
```

Parameters:
- `pattern`: required string regex or literal search term.
- `path`: directory or file to search; use `'.'` for the current task repo.
- `glob`: optional file glob, for example `'*.py'`, `'*.md'`, or `'**/*.html'`.
- `context`: optional number of lines before and after each match.
- `limit`: optional maximum number of returned matches.
- Add `fixed_strings=True` for literal matching.
- Add `case_sensitive=False` for case-insensitive matching.

Use the context store for large outputs instead of pasting them into the
conversation:

```python
h = ctx.write(
    content='large text or dict result',
    source='short-source-name',
)
ctx.grep(
    handle=h['handle'],
    pattern='important regex',
    context=2,
)
ctx.read(
    handle=h['handle'],
    offset=1,
    limit=80,
)
ctx.ask(
    handle=h['handle'],
    q='What matters most for this task?',
)
```

Parameters:
- `ctx.write.content`: required text or dict to store.
- `ctx.write.source`: short label describing where the content came from.
- `ctx.grep.handle`, `ctx.read.handle`, `ctx.ask.handle`: the string handle
  returned as `h['handle']`.
- `ctx.grep.pattern`: regex to find inside the stored content.
- `ctx.grep.context`: optional number of lines before and after each match.
- `ctx.read.offset`: 1-indexed starting line.
- `ctx.read.limit`: maximum lines to return.
- `ctx.ask.q`: precise question to answer from the stored content.

Use Context7 when you need current library or framework documentation. Search
first, then fetch docs with the selected `library_id`:

```python
context7.search(
    library_name='harbor',
    query='Harbor benchmark JobConfig agents datasets',
    output_format='str',
)
context7.doc(
    library_id='/harbor-framework/harbor',
    query='JobConfig agents datasets n_attempts n_concurrent_trials',
)
```

Parameters:
- `context7.search.library_name`: package, framework, or project name.
- `context7.search.query`: the specific documentation need.
- `context7.search.output_format`: use `'str'` unless structured output is
  needed.
- `context7.doc.library_id`: exact ID from `context7.search`, such as
  `'/harbor-framework/harbor'`.
- `context7.doc.query`: focused question or API area to retrieve.

Suggested workflow:
1. Use `ripgrep.search` to locate relevant files or git/task clues.
2. Use `ctx.write`, `ctx.grep`, `ctx.read`, and `ctx.ask` when output is large
   or needs follow-up questions.
3. Use `context7.search` and `context7.doc` for external package API questions.
4. Make the required repository edits.
5. Run the task's normal verification commands directly in the task repo.

# Documentation writing

User instructions belong in `docs/` and README; implementation practice belongs in `dev-guides/`. Private intent, findings and task history belong in planning. Describe implemented behavior and tested limits, not a proposed design as though it has shipped.

Use plain GitHub Markdown, sentence-case headings and relative links. Lead with the command or behavior the reader needs. Prefer short active sentences and stable domain terms. Include exact names/flags, expected output and failure guidance where they help the task.

Use the owned fixture for runnable examples. Never use credentials, invented tools, stale commands, hard-coded tool counts or unmeasured performance claims. Keep upstream documentation links instead of copying its full API reference. State which callback/OS/installed paths remain untested.

`tests/test_docs.py` recursively checks developer guides and user docs. Python fences are CodeMode programs, JSON fences are native MCP requests, YAML fences are validated configs. Use text fences for non-executable pseudocode or layouts. Optional private-planning links are checked only where that checkout exists.

Check every changed command against `justfile`, `pyproject.toml` or code. Repair incoming links when moving a page. The release helper counts all developer Markdown recursively plus AGENTS; aim for 500 lines. Do not create a documentation website/build system to replace plain Markdown.

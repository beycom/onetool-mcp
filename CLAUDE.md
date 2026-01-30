<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

Read AGENTS_RULES.md for this project.
Read AGENTS_PRIME.md for a project overview.

## Tools - File Search

Use OneTool ripgrep (50x faster than find+grep, with line numbers):

```python
# Search for pattern in files
ripgrep.search(pattern="onetool", path="src/", glob="*.py")

# List files only
ripgrep.search(pattern="TODO", path=".", glob="*.{py,yaml}")

# Count matches
ripgrep.count(pattern="import", path="src/", file_type="py")
```

## Tools - Web Search

Use OneTool web search:

```text
__ot $q_b q=query one|query two|query three
```

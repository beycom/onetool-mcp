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

Read dev/agents/hints.md for quick reference (commands, rules, project structure).
Read dev/agents/project-map.md for detailed project structure.
Read dev/index.md for complete dev docs navigation.

## MCP Servers

Two OneTool versions are configured:

- **otd**: Local dev version. Use `mcp__onetool-dev__run` only when explicitly requested
- **ot**: Stable version . Use `__ot` for all normal operations (default)
Use stable version unless "dev" is explicitly mentioned.

## Commands

Use `just` (not `make`) for project commands:

```bash
just check    # Run all checks (lint, type, test)
just test     # Run tests
just lint     # Run linters
```

## OneTool - Your AI-Powered Toolkit

OneTool provides 100+ tools via MCP for file operations, web search, code search, and more.

**Get the complete reference:**
# Complete OneTool cheatsheet with all tools and examples
__ot `ot.agent_hints()`

**Quick reference:**
- **File operations**: `file.read()`, `file.write()`, `file.search()` - prefer over `cat`, `echo >`, `find`
- **Code search**: `ripgrep.search()` - 50× faster than `grep -r`
- **Web search**: `brave.search()`, `web.fetch()` - prefer over `curl` or manual browsing
- **Package info**: `package.pypi()`, `package.npm()`, `package.models()` - get package/model info
- **Memory**: `mem.write()`, `mem.read()` - save findings across sessions
- **Discovery**: `ot.tools()`, `ot.help(query="...")` - find available tools

**When to use OneTool vs Bash:**
- ✅ Use OneTool for: file ops, web ops, code search, package info, data processing
- ✅ Use Bash for: git, build commands (`just`), process management, package installation

**Always use keyword arguments:**
```python
brave.search(query="test", count=5)  # ✅ Correct
brave.search("test", 5)              # ❌ Wrong
```

# Feature Summary

### onetool.feature-summary

```markdown
## Why OneTool?

**Stop Context Rot** - MCP tool enumeration burns 55K-150K tokens before you start. OneTool reduces this to ~2K tokens (98.7% reduction).

**Explicit Calls** - No tool-selection guessing games. You write `__ot brave.search(query="AI")` and that's exactly what runs. Five trigger prefixes, three invocation styles.

**Configurable Everything**
- **Tools**: Per-tool timeouts, limits, and behavior
- **Secrets**: Isolated `secrets.yaml` (gitignored), environment variable expansion
- **Prompts**: Customizable system prompts and instructions
- **Servers**: Proxy external MCP servers through OneTool

**Code-Centric**
- **Easy to extend**: Drop a Python file, get a tool pack. No registration.
- **Batteries included**: 15 packs, 90+ tools ready to use
- **Worker isolation**: External dependencies run in isolated subprocesses (PEP 723)
- **AST security**: All code validated before execution

**Built-in CLIs**
- `ot-serve` - The MCP server
- `ot-bench` - Benchmark harness (tokens, cost, accuracy)
```

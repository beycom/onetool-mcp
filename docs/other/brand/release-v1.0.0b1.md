# GitHub Release Template

### github.release.v1.0.0b1

```markdown
## OneTool v1.0.0b1

🧿 One MCP, unlimited tools

### Highlights

🛡️ **Stop Context Rot**
- 98.7% token reduction (150K → 2K)
- 10x lower cost per query
- Single MCP call vs 5+ tool-selection loops

⚡ **Explicit Calls**
- Five trigger prefixes (`__ot`, `__onetool__run`, etc.)
- Three invocation styles (simple, inline backticks, code fence)
- No guessing — you write the code, it runs exactly that

⚙️ **Configurable Everything**
- Per-tool timeouts, limits, behavior
- Isolated secrets management (`secrets.yaml`)
- Customizable prompts and snippets
- Proxy external MCP servers

🔋 **Batteries Included**
- 14 packs, 89 tools ready to use
- Drop a file to add a pack
- Worker isolation for external dependencies

🔒 **Security First**
- AST validation before execution
- Configurable allow/ask/warn/block policies
- Path boundary enforcement
- Secrets isolation (never logged)

### Installation

\`\`\`bash
uv tool install onetool-mcp
# or: pip install onetool-mcp
\`\`\`

### Links
- 📖 [Documentation](https://onetool.beycom.online)
- 🐛 [Issues](https://github.com/beycom/onetool/issues)
- ☕ [Support](https://ko-fi.com/beycom)
```

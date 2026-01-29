# Changelog

All notable changes to OneTool will be documented in this file.

## [1.0.0b1] - 2026-01-24

### Highlights

- **Stop Context Rot** - 98.7% token reduction (150K to 2K)
- **Explicit Calls** - Five trigger prefixes, three invocation styles
- **Configurable Everything** - Per-tool timeouts, limits, behavior
- **Batteries Included** - 15 packs, 97 tools ready to use
- **Security First** - AST validation, configurable policies, path boundaries

### Added

- 15 built-in tool packs
- Worker process isolation for external dependencies
- Configurable allow/ask/warn/block security policies
- Secrets isolation (never logged)
- Benchmark harness (`ot-bench`)

### Changed

- Renamed "namespace" to "pack" throughout codebase
- Updated documentation to match FastMCP standards
- Development status upgraded to Beta

### Installation

```bash
uv tool install onetool-mcp
# or: pip install onetool-mcp
```

### Links

- [Documentation](https://onetool.beycom.online)
- [Issues](https://github.com/beycom/onetool/issues)
- [Support](https://ko-fi.com/beycom)

# Security Model

Four layers of defence protect against arbitrary code execution and prompt injection.

## Layer 1: Fence Stripping

`fence_processor.py` normalises input before any execution:

- Strips execution prefixes: `__run`, `__r`, and `__ot`
- Removes markdown code fences and backticks for code-mode commands
- Ensures expanded snippet/code-mode Python reaches the validator

## Layer 2: AST Validation

`validator.py` parses code into an AST and checks every node against allowlists:

- **Names**: Only allowlisted builtins (`str`, `int`, `list`, `dict`, `print`, `len`, `range`, ...)
- **Imports**: Only allowlisted stdlib modules (`json`, `re`, `math`, `datetime`, ...)
- **Calls**: Wildcard pattern matching blocks dangerous calls (`pickle.*`, `subprocess.*`)
- Tool namespaces are auto-allowed (all registered pack names)

Configured in `security.yaml`:

```yaml
security:
  builtins:
    allow: [str, int, list, dict, print, len, range, ...]
  imports:
    allow: [json, re, math, datetime, ...]
  calls:
    block: [pickle.*, subprocess.*]
```

## Layer 3: Namespace Restriction

The `exec()` call receives a carefully constructed namespace containing only:

- Tool pack proxies (`brave`, `file`, `db`, ...)
- Allowlisted builtins
- Magic variables (`__format__`, `__sanitize__`)

Excluded: `__import__`, `exec`, `eval`, direct filesystem access, network access, subprocess.

## Layer 4: Output Sanitisation

`sanitize.py` protects against prompt injection in tool results:

- **Trigger sanitisation**: Replaces OneTool trigger-like output (`__run`, `__r`, `__ot`, `mcp__onetool*`) with `[REDACTED:trigger]`
- **Tag sanitisation**: Removes boundary tag patterns
- **GUID wrapping**: External content wrapped in unpredictable UUID-tagged boundaries

## Key Files

| File | Role |
|------|------|
| `src/ot/executor/fence_processor.py` | Input normalisation |
| `src/ot/executor/validator.py` | AST-based code analysis |
| `src/ot/executor/pack_proxy.py` | Namespace construction |
| `src/ot/utils/sanitize.py` | Output sanitisation |
| `.onetool/config/security.yaml` | Allowlist configuration |

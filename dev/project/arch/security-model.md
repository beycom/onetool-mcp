# Security Model

Four layers of defence protect against arbitrary code execution and prompt injection.

## Layer 1: Fence Stripping

`fence_processor.py` normalises input before any execution:

- Strips execution prefixes: `__onetool` and `__ot`
- Removes markdown code fences and backticks for code-mode commands
- Ensures expanded snippet/code-mode Python reaches the validator

## Layer 2: AST Validation

`validator.py` parses code into an AST and checks every node against allowlists:

- **Names**: Only allowlisted builtins (`str`, `int`, `list`, `dict`, `print`, `len`, `range`, ...)
- **Imports**: Only allowlisted stdlib modules (`json`, `re`, `math`, `datetime`, ...)
- **Calls**: Wildcard pattern matching blocks dangerous calls (`pickle.*`, `subprocess.*`)
- Tool namespaces are auto-allowed (all registered pack names)

Configured in `security.yaml` (keys illustrative of the schema; see the shipped
`src/ot/config/global_templates/security.yaml` for the actual defaults, which use
`builtins`, `imports`, `dunders`, and `sanitize`):

```yaml
security:
  builtins:
    allow: [str, int, list, dict, print, len, range, ...]
  imports:
    allow: [json, re, math, datetime, ...]
  dunders:
    allow: [__format__, __sanitize__, __force_context__]
```

## Layer 3: Namespace and the exec() boundary

**`exec()` is not a sandbox.** The executor passes the full, unfiltered builtins
mapping into the exec namespace (`src/ot/executor/runner.py`,
`"__builtins__": __builtins__`) — `__import__`, `eval`, filesystem, network, and
subprocess are all reachable from executed code. Do not treat `exec()` itself as a
containment layer.

AST validation (`src/ot/executor/validator.py`) blocks casual mistakes and
known-dangerous imports/calls, but it does **not** contain a determined escape. Two
concrete bypasses illustrate the limit:

- `().__class__.__base__.__subclasses__()` walks the class hierarchy to reach
  arbitrary classes without ever naming a blocked import.
- Aliasing: `x = __builtins__; x['eval'](...)` — the validator's `visit_Subscript`
  check only matches `node.value.id == "__builtins__"` literally, so an aliased name
  slips past it.

**The security boundary is process / user / environment isolation** for a *trusted
local user running a trusted agent session* — not `exec()`. Users must not feed
untrusted content to an agent with OneTool access and expect the validator to hold as
a security control.

**Deferred hardening (V4, contingent on the threat model changing):** narrowing the
exposed builtins or adopting an alternative sandbox (e.g. Monty) is deliberately not
implemented — sandboxing was dropped pre-V1 as complexity, and is revisited only if
OneTool's trust model shifts to running untrusted sessions.

## Layer 4: Output Sanitisation

`sanitize.py` protects against prompt injection in tool results:

- **Trigger sanitisation**: Replaces OneTool trigger-like output (`__onetool`, `__ot`, `mcp__onetool*`) with `[REDACTED:trigger]`
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

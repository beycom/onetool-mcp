# Security Model

**No hidden calls. No magic. You read the code before you run it.**

## Philosophy

OneTool takes a different approach to AI tool security:

1. **Transparency over obscurity** - You see the exact code before it runs
2. **Developer control** - Configurable policies, not black boxes
3. **Defense in depth** - Multiple layers, each independently useful
4. **Fail-safe defaults** - Secure out of the box, customisable when needed

## Security Layers

### 1. Explicit Execution

The fundamental security mechanism: **you see what runs**.

```python
# The LLM generates this code - you see it before execution
__ot brave.web_search(query="AI security best practices")
```

Unlike hidden tool calls, OneTool's explicit execution means:

- No surprise API calls
- No hidden file modifications
- No covert network requests
- Full audit trail in conversation

Code review catches what automation misses.

### 2. AST Code Validation

Before any code executes, OneTool validates it using Python's Abstract Syntax Tree:

```text
Code → ast.parse() → Pattern Detection → Execute or Reject
```

**What it catches:**

| Pattern | Risk | Action |
|---------|------|--------|
| `exec()`, `eval()` | Arbitrary code execution | Block |
| `subprocess.*` | Command injection | Block |
| `os.system`, `os.popen` | Shell execution | Block |
| `pickle.load()` | Deserialisation attacks | Warn |
| `open()` | File access | Warn |

**Performance:** ~0.1-1ms overhead. Negligible compared to actual tool execution.

### 3. Configurable Security Policies

Four-tier pattern system for fine-grained control:

```yaml
security:
  allow: [...]     # Execute silently
  ask: [...]       # Prompt user, show full command
  warn: [...]      # Log warning, execute
  block: [...]     # Reject with error
```

**Priority:** allow > ask > warn > block

**Example configurations:**

```yaml
# Paranoid mode - confirm everything
security:
  ask:
    - "*"

# Air-gapped - block all network tools
security:
  block:
    - brave.*
    - web_fetch.*
    - context7.*
    - ground.*

# Trust file ops, ask for network
security:
  allow:
    - file.*
  ask:
    - brave.*
    - web_fetch.*
```

Patterns use fnmatch wildcards (`*`, `?`, `[seq]`) and work for both code patterns and tool names.

### 4. Path Boundary Enforcement

File operations are constrained to allowed directories:

```yaml
tools:
  file:
    allowed_dirs: ["."]           # Only current directory
    exclude_patterns: [".git", ".env", "node_modules"]
    max_file_size: 10000000       # 10MB limit
```

**What it prevents:**

- Reading `/etc/passwd` or system files
- Writing outside project boundaries
- Accessing sensitive directories (`.git`, `.env`)
- Symlink escape attacks (resolved before validation)

### 5. Secrets Management

API keys and credentials are isolated from code:

```yaml
# secrets.yaml (gitignored)
BRAVE_API_KEY: "your-key"
DATABASE_URL: "${PROD_DB_URL}"
```

**Security properties:**

- Separate file, not in main config
- Environment variable expansion
- Never logged or exposed in errors
- Accessed via `get_secret()` API only

### 6. Worker Process Isolation

Tools run in isolated worker processes:

- Separate memory space from main server
- Controlled execution environment (no arbitrary imports)
- Timeout enforcement per tool
- Clean process state between calls

## Default Security Patterns

### Blocked (prevent execution)

```text
exec, eval, compile, __import__     # Arbitrary code execution
subprocess.*                         # Command injection
os.system, os.popen                  # Shell execution
os.spawn*, os.exec*                  # Process spawning
```

### Warned (log and execute)

```text
subprocess, os                       # Import warnings
open                                 # File access
pickle.*, yaml.load, marshal.*       # Deserialisation
```

## Customising Security

### Extend defaults (additive)

```yaml
security:
  blocked:
    - my_dangerous.*    # Added to defaults
  warned:
    - custom_risky.*    # Added to defaults
```

### Downgrade blocked to warned

```yaml
security:
  warned:
    - os.popen          # Moves from blocked to warned
```

### Exempt from defaults

```yaml
security:
  allow:
    - open              # Remove warning for file tools
```

## Attack Mitigation Summary

| Attack Vector | Mitigation |
|---------------|------------|
| Arbitrary code execution | AST blocks `exec`, `eval` |
| Command injection | AST blocks `subprocess.*`, `os.system` |
| Path traversal | Boundary validation, symlink resolution |
| Sensitive data exposure | Secrets isolation, path exclusions |
| Deserialisation attacks | AST warns on `pickle`, `yaml.load` |
| Prompt injection | Explicit execution (developer review) |

## What OneTool Doesn't Do

OneTool is a developer tool, not a sandbox. It does not:

- Run untrusted code from unknown sources
- Provide container-level isolation
- Implement network firewalls
- Replace code review

## Recommendations

1. **Review generated code** - The explicit execution model only works if you look
2. **Use `ask` for destructive ops** - `ask: [file.write, file.delete]`
3. **Restrict paths to project scope** - `allowed_dirs: ["."]`
4. **Keep secrets separate** - Never commit `secrets.yaml`
5. **Use air-gapped mode for sensitive work** - Block network tools when needed

## See Also

- [Configuration Reference](configuration.md) - Full YAML schema

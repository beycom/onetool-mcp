# Configuration

OneTool uses YAML configuration files. The config file path is always specified explicitly via the `--config` flag.

## Quick Start

```bash
# Initialize config (interactive TUI)
onetool init --config .onetool

# Validate configuration
onetool init validate --config .onetool/onetool.yaml
```

## Key Files

| File | Purpose |
|------|---------|
| `onetool.yaml` | Main configuration (tools, servers, snippets) |
| `secrets.yaml` | API keys (gitignored, passed via `--secrets`) |

## Security Configuration

OneTool uses an allowlist-based security model. Everything is blocked by
default; you must explicitly allow what's safe.

Bundled defaults like `snippets.yaml`, `diagram.yaml`, and `security.yaml` are not loaded
automatically — they must be listed under `include:`. `onetool init` handles this for you;
it only matters if you write your own `onetool.yaml` from scratch.

Include `security.yaml` in your config (paths resolve from the directory containing `onetool.yaml`):

```yaml
include:
  - security.yaml  # Resolves from config parent dir, falls back to package default
```

Or define inline:

```yaml
security:
  builtins:
    allow:
      - [str, int, float, list, dict, set, tuple]  # Types
      - [len, range, enumerate, zip, sorted]       # Iteration
      - [print, repr, format]                      # Output
  imports:
    allow: [json, re, math, datetime, collections]
    warn: [yaml]
  calls:
    block: [pickle.*, yaml.load]
  dunders:
    allow: [__format__, __sanitize__, __compact__, __force_context__, __display__]
```

Tool namespaces (`ot.*`, `brave.*`, `file.*`, etc.) are auto-allowed.

### Checking Security Rules

Use introspection to check what's allowed:

```python
ot.security()                    # Summary of all rules
ot.security(check="json")        # Check specific pattern
ot.security(check="pickle.load") # Check qualified call
```

## Reference

- **[onetool Configuration](../reference/cli/onetool-config.md)** - Full YAML schema, pack settings, secrets, MCP servers, aliases, snippets, security

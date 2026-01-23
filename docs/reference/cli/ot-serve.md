# ot-serve

**The MCP server. One tool. Unlimited capabilities.**

Exposes a single `run` tool that executes Python code. Your LLM writes code; OneTool runs it.

## Usage

```bash
ot-serve [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-c, --config PATH` | Path to ot-serve.yaml configuration file |
| `-v, --version` | Show version and exit |

## Examples

```bash
# Start MCP server (stdio)
ot-serve

# Use specific config
ot-serve --config config/ot-serve.yaml
```

## Configuration

Configuration file: `config/ot-serve.yaml` or `.onetool/ot-serve.yaml`

See [Configuration Reference](../../getting-started/configuration.md) for full schema.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OT_SERVE_CONFIG` | Config file path override |
| `OT_LOG_LEVEL` | Log level (DEBUG/INFO/WARNING/ERROR) |
| `OT_LOG_DIR` | Log directory path |

## How It Works

1. Loads tools from `src/ot_tools/` via AST-based discovery
2. Exposes a single `run` tool that executes Python code
3. Communicates via stdio using the MCP protocol

## Tool Discovery

Tools are discovered statically from `tools_dir` patterns in config:

```yaml
tools_dir:
  - src/ot_tools/*.py
```

Benefits:
- No code execution during discovery
- Instant startup
- Hot reload support
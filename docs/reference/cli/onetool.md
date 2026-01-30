# onetool

**The MCP server. One tool. Unlimited capabilities.**

Exposes a single `run` tool that executes Python code. Your agent writes code; OneTool runs it.

## Usage

```bash
onetool [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-c, --config PATH` | Path to onetool.yaml configuration file |
| `-v, --version` | Show version and exit |

## Commands

### init

Initialize and manage global configuration in `~/.onetool/`.

```bash
onetool init [subcommand]
```

Running `onetool init` without a subcommand creates the global config directory.

| Subcommand | Description |
|------------|-------------|
| `validate` | Validate config and show status |
| `reset` | Reset global config to default templates |

#### init (default)

Creates the global config directory and copies template files if they don't already exist.

```bash
onetool init
```

#### init validate

Validates configuration files and displays status including packs, secrets (names only), snippets, aliases, and MCP servers.

```bash
onetool init validate
```

#### init reset

Resets config files in `~/.onetool/` to fresh templates. Prompts for each existing file before overwriting, with option to create backups. Backups are named `file.bak`, `file.bak.1`, `file.bak.2`, etc.

```bash
onetool init reset
```

## Examples

```bash
# Start MCP server (stdio)
onetool

# Use specific config
onetool --config config/onetool.yaml
```

## Configuration

Configuration file: `config/onetool.yaml` or `.onetool/onetool.yaml`

See [Configuration Reference](../../learn/configuration.md) for full schema.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ONETOOL_CONFIG` | Config file path override |
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
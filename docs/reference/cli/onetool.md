# onetool

Exposes a single `run` tool that executes Python code. Your agent writes code; OneTool runs it.

## Usage

```bash
onetool [OPTIONS] COMMAND [ARGS]...
```

## Options

| Option | Description |
|--------|-------------|
| `-c, --config PATH` | Path to onetool.yaml configuration file for root compatibility invocation |
| `-s, --secrets PATH` | Path to secrets file. If omitted, no secrets are loaded |
| `-v, --version` | Show version and exit |

## Commands

### serve

Run the OneTool root MCP server. Defaults to stdio transport.

```bash
onetool serve --config .onetool/onetool.yaml
onetool serve --transport http --config .onetool/onetool.yaml
onetool serve -t http -c .onetool/onetool.yaml --host 127.0.0.1 --port 8767 --path /mcp
```

| Option | Default | Description |
|--------|---------|-------------|
| `-c, --config PATH` | required | Path to onetool.yaml configuration file |
| `-s, --secrets PATH` | none | Path to secrets file |
| `-t, --transport TRANSPORT` | `stdio` | Root MCP transport: `stdio` or `http` |
| `--host HOST` | `127.0.0.1` | Streamable HTTP root bind host |
| `--port PORT` | `8767` | Streamable HTTP root bind port |
| `--path PATH` | `/mcp` | Streamable HTTP MCP endpoint path |

### init

Initialize and manage the OneTool configuration directory.

```bash
onetool init [subcommand]
```

Running `onetool init` without a subcommand runs an interactive TUI to select which extensions to install. Existing files are backed up to `.bak` automatically.

| Subcommand | Description |
|------------|-------------|
| `validate` | Validate config and show status |

#### init (default)

Interactive setup — select which extensions to install into the config directory. Pass `--config` to specify a directory or config file path.

```bash
onetool init                              # uses current directory
onetool init --config .onetool            # explicit directory
onetool init --config .onetool/ot.yaml    # explicit file path
```

#### init validate

Validates configuration files and displays status including packs, secrets (names only), snippets, aliases, and MCP servers.

```bash
onetool init validate --config .onetool/onetool.yaml
```

## Examples

```bash
# Start MCP server with explicit config
onetool serve --config .onetool/onetool.yaml

# Start with config and secrets
onetool serve --config .onetool/onetool.yaml --secrets .onetool/secrets.yaml

# Start Streamable HTTP root MCP for URL-based MCP clients
onetool serve --transport http --config .onetool/onetool.yaml --host 127.0.0.1 --port 8767 --path /mcp
```

## Runtime Modes

| Mode | Purpose | Transport | Auth | Port or bind | Config shape | Entry point | Recommended use |
|------|---------|-----------|------|--------------|--------------|-------------|-----------------|
| `stdio` | Root MCP server | MCP over stdio | MCP client process boundary | none | command + args | `onetool serve --config .onetool/onetool.yaml` | Default local MCP setup |
| `http` | Root MCP server | MCP Streamable HTTP | none in this mode | `127.0.0.1:8767/mcp` by default | URL | `onetool serve --transport http --config .onetool/onetool.yaml` | Harnesses, containers, and URL-only MCP clients |
| `direct` | Private signed client into the root MCP process | Signed HTTP, not MCP | HMAC key in `.onetool/mcp-direct/auth.key` | `127.0.0.1:8765` preferred by default | CLI target port | `onetool direct run --port 8765 "ot.version()"` | Scripts and harnesses calling a running root process |

Use `stdio` for normal local MCP client configuration. Use `http` when the MCP
client needs a URL instead of a command it can spawn. Direct API is private
process access for `direct`; it is not an MCP HTTP transport.

## Configuration

Config is specified via `--config`. All relative paths inside the config file resolve from the config file's parent directory.

See [onetool Configuration](onetool-config.md) for full schema reference.

### Quick Setup

```bash
onetool init --config .onetool     # Interactive TUI setup
onetool init validate --config .onetool/onetool.yaml  # Check for errors
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OT_LOG_LEVEL` | Log level (DEBUG/INFO/WARNING/ERROR) |
| `OT_LOG_DIR` | Log directory path |

## How It Works

1. Loads tools from `src/ottools/` via AST-based discovery
2. Exposes a single `run` tool that executes Python code
3. Communicates via stdio using the MCP protocol

## Tool Discovery

Tools are discovered statically from `tools_dir` patterns in config:

```yaml
tools_dir:
  - src/ottools/*.py
```

Benefits:
- No code execution during discovery
- Instant startup
- Hot reload support

# Installation

**Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).**

For the quickest path, see [Quickstart](quickstart.md). This page covers all platforms and optional features.

## System Requirements

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **Python** | >= 3.12 | Runtime environment |
| **uv** | Latest | Package management |

### Installing System Requirements

**macOS:**

```bash
brew install python@3.12
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Linux (Debian/Ubuntu):**

```bash
apt install python3.12
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**

```powershell
winget install Python.Python.3.12
irm https://astral.sh/uv/install.ps1 | iex
```

## Install

### Bootstrap (recommended)

The bootstrap script installs `uv` if missing, installs OneTool, runs `onetool init`,
and prints ready-to-paste MCP client config:

```bash
curl -LsSf https://onetool.beycom.online/install.sh | sh          # macOS / Linux
irm https://onetool.beycom.online/install.ps1 | iex               # Windows (PowerShell)
```

To inspect the script and verify its checksum before running:

```bash
curl -LsSf https://onetool.beycom.online/install.sh -o install.sh
curl -LsSf https://onetool.beycom.online/install.sh.sha256 -o install.sh.sha256
shasum -a 256 -c install.sh.sha256
sh install.sh
```

Override extras or config dir with `ONETOOL_EXTRAS` / `ONETOOL_CONFIG_DIR`.

### Manual (uv)

```bash
uv tool install onetool-mcp
```

This installs the `onetool` command globally with the core tool set.

### Optional Tool Packs

Tools are split into optional extras for leaner installs:

| Extra | Tools | Install |
|-------|-------|---------|
| `[util]` | `brave`, `convert`, `excel`, `file`, `ground`, `knowledge`, `mem`, `tavily`, `whiteboard` | `uv tool install 'onetool-mcp[util]'` |
| `[dev]` | `chrome_util`, `context7`, `db`, `diagram`, `package`, `play_util`, `ripgrep`, `webfetch` | `uv tool install 'onetool-mcp[dev]'` |
| `[all]` | Everything | `uv tool install 'onetool-mcp[all]'` |

```bash
# Install with all tools
uv tool install 'onetool-mcp[all]'

# Install with specific extras
uv tool install 'onetool-mcp[util,dev]'
```

**Optional:** For safe file deletion (moves to trash instead of permanent delete), add `send2trash`:

```bash
uv tool install 'onetool-mcp[all]' --with send2trash
```

## Upgrade

```bash
uv tool upgrade onetool-mcp
```

Or to upgrade all tools:

```bash
uv tool upgrade --all
```

## Uninstall

```bash
uv tool uninstall onetool-mcp
```

This removes the tool and its isolated environment. Any config directories you created are preserved.

## From Source (Development)

```bash
git clone https://github.com/beycom/onetool-mcp.git
cd onetool-mcp
uv sync --group dev
```

### Local Development Install

```bash
uv tool install -e .
```

Code changes are picked up immediately. Reinstall only for new entry points, dependencies, or top-level packages.

## API Keys

API keys are stored in `secrets.yaml` (gitignored) and passed to the server via `--secrets`:

| Key | Service | Used By |
|-----|---------|---------|
| `OPENAI_API_KEY` | OpenAI API | Explicit direct generation or embedding routes |
| `OPENROUTER_API_KEY` | OpenRouter | Explicit direct generation routes |
| `CLIPROXY_INFERENCE_KEY` | User-managed CLIProxyAPI | Proxy code-harness launches and generation routes |
| `BRAVE_API_KEY` | [Brave Search](https://brave.com/search/api/) | `brave.*` tools |
| `CONTEXT7_API_KEY` | [Context7](https://context7.com) | `context7.*` tools |

### Example secrets.yaml

```yaml
# secrets.yaml
BRAVE_API_KEY: "BSA..."
OPENAI_API_KEY: "sk-..."
CONTEXT7_API_KEY: "c7-..."
```

Pass it to the server via `--secrets /path/to/secrets.yaml`. If omitted, no secrets are loaded.

### Configuration Variables

| Variable       | Default   | Purpose                                   |
|----------------|-----------|-------------------------------------------|
| `OT_LOG_LEVEL` | `INFO`    | Logging verbosity                         |
| `OT_LOG_DIR`   | `../logs` | Log file directory (relative to config)   |

### LLM Configuration

Register model capabilities and select one explicit generation backend:

```yaml
models:
  glm52:
    shortcut: glm52
    id: z-ai/glm-5.2
    source: openrouter
    modalities: [text]
    interfaces: [chat_completions]
    structured_outputs:
      chat_completions: [json_object, json_schema]
    efforts: [low, medium, high]

llm:
  backend: openai_compatible
  interface: chat_completions
  model: glm52
  base_url: https://openrouter.ai/api/v1
  secret_name: OPENROUTER_API_KEY
  timeout: 30
  max_output_tokens: 4096

embeddings:
  backend: openai_compatible
  model: text-embedding-3-small
  base_url: https://api.openai.com/v1
  secret_name: OPENAI_API_KEY
  dimensions: 1536
  timeout: 60
  batch_size: 200
  max_tokens: 8191
```

Generation and embeddings are independent; configure only the routes you use. A
CLIProxyAPI generation route instead reuses `code.proxy` and its named secret.
See [LLM routing](llm-routing.md).

## MCP Configuration

OneTool works with any MCP client. Generate ready-to-paste config with **resolved
absolute paths** (config, secrets, and the `onetool` executable) — no hand-editing:

```bash
onetool init mcp-config --client <client>   # omit --client to print all four
```

The command prints, for each client, the JSON block and the exact file to merge it
into. Supported `--client` values and their targets:

### Claude Code

```bash
onetool init mcp-config --client claude-code
```

Merge the printed `mcpServers` block into `~/.claude/mcp.json` (or project `.mcp.json`),
or run the printed `claude mcp add …` one-liner.

### Claude Desktop

```bash
onetool init mcp-config --client claude-desktop
```

Merge into `claude_desktop_config.json` (the command names the correct per-OS path:
`~/Library/Application Support/Claude/` on macOS, `%APPDATA%\Claude\` on Windows,
`~/.config/claude-desktop/` on Linux).

### Cursor

```bash
onetool init mcp-config --client cursor
```

Merge into `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global).

### VS Code

```bash
onetool init mcp-config --client vscode
```

VS Code uses a top-level `servers` key with `"type": "stdio"` per entry. Merge into
`.vscode/mcp.json` (project) or the user-profile `mcp.json` (global).

## Install the OneTool Skills

OneTool ships the `ot-ref` skill in the standard Agent Skills layout at `skills/ot-ref/SKILL.md`.
Install it into your agent with [vercel-labs/skills](https://github.com/vercel-labs/skills):

```bash
npx skills add https://github.com/beycom/onetool-mcp --skill ot-ref --agent claude
```

`--agent` also accepts `codex`, `opencode`, and others. Run `npx skills add https://github.com/beycom/onetool-mcp --list`
to discover every installable skill. If you don't use vercel-labs/skills, APM or a manual copy of
`skills/ot-ref/SKILL.md` into your agent's skills directory are supported alternatives.

## External Tools

### Ripgrep Search

```bash
# macOS
brew install ripgrep

# Linux
apt install ripgrep

# Windows
winget install BurntSushi.ripgrep.MSVC
```

## Verify Installation

```bash
# Check version
onetool --version

# Initialize and validate config
onetool init --config ~/.onetool
onetool init validate --config ~/.onetool/onetool.yaml

```

## Next Steps

- [Configuration](configuration.md) - YAML schema and options
- [CLI Reference](../reference/cli/onetool.md) - Command-line tools

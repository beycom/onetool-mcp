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
| `[all]` | Core plus `[util,dev]`; not `[scrape]` | `uv tool install 'onetool-mcp[all]'` |
| `[scrape]` | Optional Knowledge web ingestion | `uv tool install 'onetool-mcp[scrape]'` |

```bash
# Install core, util, and dev packs
uv tool install 'onetool-mcp[all]'

# Add Knowledge web ingestion too
uv tool install 'onetool-mcp[all,scrape]'
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
| `OPENAI_API_KEY` | OpenAI-compatible providers (including OpenRouter) | `ot_llm.transform` |
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

Configure `base_url` and `model` once at the top level — all LLM-using tools (`ot_llm`, `ot_image`, `mem`, `knowledge`, `ctx`) inherit from it:

```yaml
llm:
  base_url: "https://openrouter.ai/api/v1"    # Required
  model: "google/gemini-2-flash-preview"       # Required for transform/vision
  embedding_model: "text-embedding-3-small"    # Required for mem/knowledge embeddings
```

The transform tool is not available until `base_url` and `model` are configured (via `llm:` or `tools.ot_llm.*`), plus `OPENAI_API_KEY` in secrets.

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

OneTool ships a curated set of standard Agent Skills. Use the
[Skills CLI](https://www.skills.sh/docs/cli) to list the current catalog:

```bash
npx skills@latest add https://github.com/beycom/onetool-mcp --list
```

Install only the guidance matching your Python extras and work. Each recipe
below expands to ordinary repeated `--skill` flags so it works with the current
CLI; OneTool does not claim that the installer understands named profiles.

<!-- BEGIN GENERATED:SKILL_INSTALLATION_PROFILES -->
| Recipe | Skills |
|---|---|
| **Foundation** | `ot-ask`, `ot-ref`, `ot-setup` |
| **Core** | `ot-ask`, `ot-context`, `ot-forge`, `ot-image`, `ot-llm`, `ot-mcp-proxy`, `ot-ref`, `ot-runtime`, `ot-secrets`, `ot-setup` |
| **Core + [util]** | `ot-ask`, `ot-context`, `ot-convert`, `ot-excel`, `ot-file`, `ot-forge`, `ot-image`, `ot-knowledge`, `ot-llm`, `ot-mcp-proxy`, `ot-mem`, `ot-ref`, `ot-research`, `ot-runtime`, `ot-secrets`, `ot-setup`, `ot-whiteboard` |
| **Core + [dev]** | `ot-arch`, `ot-ask`, `ot-browser-guidance`, `ot-context`, `ot-db`, `ot-diagram`, `ot-file`, `ot-forge`, `ot-image`, `ot-llm`, `ot-localhist`, `ot-mcp-proxy`, `ot-ref`, `ot-research`, `ot-runtime`, `ot-secrets`, `ot-setup` |
| **[all]** | `ot-arch`, `ot-ask`, `ot-browser-guidance`, `ot-context`, `ot-convert`, `ot-db`, `ot-diagram`, `ot-excel`, `ot-file`, `ot-forge`, `ot-image`, `ot-knowledge`, `ot-llm`, `ot-localhist`, `ot-mcp-proxy`, `ot-mem`, `ot-ref`, `ot-research`, `ot-runtime`, `ot-secrets`, `ot-setup`, `ot-whiteboard` |

These are documentation recipes, not native installer profile names. Replace `<agent>` with a supported agent such as `codex` or `claude-code`.

**Foundation**

```bash
npx skills@latest add https://github.com/beycom/onetool-mcp --agent <agent> --skill ot-ask --skill ot-ref --skill ot-setup
```

**Core**

```bash
npx skills@latest add https://github.com/beycom/onetool-mcp --agent <agent> --skill ot-ask --skill ot-context --skill ot-forge --skill ot-image --skill ot-llm --skill ot-mcp-proxy --skill ot-ref --skill ot-runtime --skill ot-secrets --skill ot-setup
```

**Core + [util]**

```bash
npx skills@latest add https://github.com/beycom/onetool-mcp --agent <agent> --skill ot-ask --skill ot-context --skill ot-convert --skill ot-excel --skill ot-file --skill ot-forge --skill ot-image --skill ot-knowledge --skill ot-llm --skill ot-mcp-proxy --skill ot-mem --skill ot-ref --skill ot-research --skill ot-runtime --skill ot-secrets --skill ot-setup --skill ot-whiteboard
```

**Core + [dev]**

```bash
npx skills@latest add https://github.com/beycom/onetool-mcp --agent <agent> --skill ot-arch --skill ot-ask --skill ot-browser-guidance --skill ot-context --skill ot-db --skill ot-diagram --skill ot-file --skill ot-forge --skill ot-image --skill ot-llm --skill ot-localhist --skill ot-mcp-proxy --skill ot-ref --skill ot-research --skill ot-runtime --skill ot-secrets --skill ot-setup
```

**[all]**

```bash
npx skills@latest add https://github.com/beycom/onetool-mcp --agent <agent> --skill ot-arch --skill ot-ask --skill ot-browser-guidance --skill ot-context --skill ot-convert --skill ot-db --skill ot-diagram --skill ot-excel --skill ot-file --skill ot-forge --skill ot-image --skill ot-knowledge --skill ot-llm --skill ot-localhist --skill ot-mcp-proxy --skill ot-mem --skill ot-ref --skill ot-research --skill ot-runtime --skill ot-secrets --skill ot-setup --skill ot-whiteboard
```
<!-- END GENERATED:SKILL_INSTALLATION_PROFILES -->

Skill `[all]` means every distributed OneTool guidance skill. It is not the
Python `onetool-mcp[all]` extra, which installs core plus `[util,dev]` and still
excludes `[scrape]`.

Use `npx skills@latest list`, `update`, and `remove` to inspect and maintain
installed skills. If you do not use the Skills CLI, copy selected `skills/<name>`
directories into the location documented by your agent.

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

# Installation

**Python 3.11+ required. Install with uv or pip.**

For the quickest path, see [Quickstart](quickstart.md). This page covers all platforms and optional features.

## System Requirements

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **Python** | >= 3.11 | Runtime environment |
| **uv** | Latest | Package management (recommended) |

### Installing System Requirements

**macOS:**

```bash
brew install python@3.11
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Linux (Debian/Ubuntu):**

```bash
apt install python3.11
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**

```powershell
winget install Python.Python.3.11
irm https://astral.sh/uv/install.ps1 | iex
```

## Installation Methods

### Using uv tool (Recommended)

```bash
uv tool install onetool-mcp
```

This installs `onetool` and `bench` commands globally.

### Using pip

```bash
pip install onetool-mcp
```

### From Source (Development)

```bash
git clone https://github.com/beycom/onetool.git
cd onetool
uv sync --group dev
```

### Local Development Install

```bash
uv tool install -e .
```

Code changes are picked up immediately. Reinstall only for new entry points, dependencies, or top-level packages.

## API Keys

API keys are stored in `secrets.yaml` (gitignored):

| Key | Service | Used By |
|-----|---------|---------|
| `OPENAI_API_KEY` | OpenRouter | `transform`, `code_search` |
| `BRAVE_API_KEY` | [Brave Search](https://brave.com/search/api/) | `brave.*` tools |
| `CONTEXT7_API_KEY` | [Context7](https://context7.com) | `context7.*` tools |

### Example secrets.yaml

```yaml
# .onetool/secrets.yaml
BRAVE_API_KEY: "BSA..."
OPENAI_API_KEY: "sk-..."
CONTEXT7_API_KEY: "c7-..."
```

**Resolution order:** `OT_SECRETS_FILE` > `.onetool/secrets.yaml` > `~/.onetool/secrets.yaml`

### Configuration Variables

| Variable       | Default   | Purpose                                   |
|----------------|-----------|-------------------------------------------|
| `OT_LOG_LEVEL` | `INFO`    | Logging verbosity                         |
| `OT_LOG_DIR`   | `../logs` | Log file directory (relative to config)   |

### Transform Tool Configuration

The transform tool requires explicit configuration in `onetool.yaml`:

```yaml
tools:
  transform:
    base_url: "https://openrouter.ai/api/v1"  # Required
    model: "openai/gpt-5-mini"                 # Required
```

The tool is not available until both `base_url` and `model` are configured, plus `OPENAI_API_KEY` in secrets.

## MCP Configuration

### Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "onetool": {
      "command": "onetool"
    }
  }
}
```

### With Environment Variables

```json
{
  "mcpServers": {
    "onetool": {
      "command": "onetool",
      "env": {
        "OT_BRAVE_API_KEY": "your-brave-api-key"
      }
    }
  }
}
```

### Project Setup

Create a `.onetool/` directory in your project:

| Platform | Global Config | Project Config |
|----------|--------------|----------------|
| macOS/Linux | `~/.onetool/` | `.onetool/` |
| Windows | `%USERPROFILE%\.onetool\` | `.onetool\` |

## Optional Dependencies

Some tools require additional Python packages. When installed via `uv tool`, you must include these at install time using `--with` flags:

### Document Conversion (`convert` pack)

```bash
uv tool install onetool-mcp \
  --with pymupdf \
  --with python-docx \
  --with python-pptx \
  --with openpyxl \
  --with Pillow
```

### Code Search (`code` pack)

```bash
uv tool install onetool-mcp \
  --with duckdb \
  --with openai
```

### All Optional Dependencies

Install everything at once:

```bash
uv tool install onetool-mcp \
  --with pymupdf \
  --with python-docx \
  --with python-pptx \
  --with openpyxl \
  --with Pillow \
  --with duckdb \
  --with openai
```

### Verify Dependencies

Check which dependencies are installed:

```bash
onetool init validate
```

The Dependencies section shows each tool's requirements and their status (OK or missing).

> **Note:** Using `pip install` after `uv tool install` won't work - the packages install to a different environment. Always use `--with` during installation.

## Feature-Specific Requirements

### Semantic Code Search (`code` pack)

**Requires pre-indexed codebase:**

```bash
chunkhound index /path/to/project
```

See [Optional Dependencies](#optional-dependencies) for installing `duckdb` and `openai`.

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

# Start MCP server
onetool

# Run benchmarks (from source)
OT_CWD=demo bench run demo/bench/features.yaml
```

## Next Steps

- [Configuration](configuration.md) - YAML schema and options
- [CLI Reference](../reference/cli/onetool.md) - Command-line tools
- [Examples](examples.md) - Demo project usage

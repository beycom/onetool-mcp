# Configuration Reference

Complete reference for OneTool configuration.

## Configuration Files

OneTool uses a layered configuration system:

| Location | Purpose | Scope |
|----------|---------|-------|
| `config/ot-serve.yaml` | Development config | Repository |
| `.onetool/ot-serve.yaml` | Project config | Project |
| `~/.onetool/ot-serve.yaml` | Global config | User |

**Windows paths:** Replace `~/.onetool/` with `%USERPROFILE%\.onetool\`

## Environment Variables

OneTool uses environment variables for runtime settings (with `OT_` prefix):

| Variable | Description | Required |
|----------|-------------|----------|
| `OT_LOG_LEVEL` | Log level (DEBUG/INFO/WARNING/ERROR) | No |
| `OT_LOG_DIR` | Log directory path | No |
| `OT_COMPACT_MAX_LENGTH` | Max value length in compact output | No |
| `OT_SERVE_CONFIG` | Config file path override | No |
| `OT_SECRETS_FILE` | Secrets file path override | No |

**Note:** API keys are no longer set via environment variables. They are loaded from YAML files:
- Tool API keys (`BRAVE_API_KEY`, `GEMINI_API_KEY`, etc.) → `secrets.yaml`
- Benchmark API keys (`OPENAI_API_KEY`, etc.) → `bench-secrets.yaml`

## Secrets Configuration

API keys and sensitive credentials are stored separately in `secrets.yaml` (gitignored):

| Location | Purpose | Scope |
|----------|---------|-------|
| `.onetool/secrets.yaml` | Project secrets | Project |
| `~/.onetool/secrets.yaml` | Global secrets | User |

**Resolution order:** `OT_SECRETS_FILE` env var → project secrets → global secrets

### Secrets File Format

```yaml
# API keys for tools
BRAVE_API_KEY: "your-brave-api-key"
OPENAI_API_KEY: "sk-..."
CONTEXT7_API_KEY: "your-context7-key"
GEMINI_API_KEY: "your-gemini-key"

# Environment variable references
DATABASE_URL: "${PROD_DATABASE_URL}"
```

### Environment Variable References

Secrets can reference environment variables with `${VAR_NAME}` syntax:

```yaml
# Reference an environment variable
API_KEY: "${MY_ENV_VAR}"
```

### Accessing Secrets in Tools

Worker tools access secrets via the SDK:

```python
from ot_sdk import get_secret

api_key = get_secret("BRAVE_API_KEY")
if not api_key:
    return "Error: BRAVE_API_KEY not configured in secrets.yaml"
```

In-process tools can also use `get_secret`:

```python
from ot.config.secrets import get_secret

api_key = get_secret("BRAVE_API_KEY")
```

## YAML Configuration Schema

### Basic Structure

```yaml
version: 1                    # Config schema version (required)

include:                      # External config files to merge
  - prompts.yaml              # prompts: section
  - snippets.yaml             # snippets: section
  - servers.yaml              # servers: section

tools_dir:                    # Tool discovery patterns
  - src/ot_tools/*.py

log_level: INFO               # DEBUG, INFO, WARNING, ERROR
validate_code: true           # Validate generated code before execution

projects: {}                  # Named project paths
servers: {}                   # External MCP servers
tools: {}                     # Tool-specific configuration
alias: {}                     # Function aliases
snippets: {}                  # Reusable code templates
prompts: {}                   # Inline prompts (overrides included)
```

### Config Includes

The `include:` key allows composing configuration from multiple files:

```yaml
version: 1

include:
  - ../../resources/config/prompts.yaml   # Shared prompts
  - ../../resources/config/snippets.yaml  # Shared snippets
  - ../../resources/config/servers.yaml   # Shared MCP servers
  - local-snippets.yaml                   # Project additions

# Inline content overrides included content
servers:
  local_dev:
    type: stdio
    command: python
```

**Merge behaviour:**
- Files are merged left-to-right (later files override earlier)
- Inline content in the main file overrides everything
- Nested dicts are deep-merged
- Non-dict values (lists, scalars) are replaced entirely

**Included file format:**

Each included file contains complete config sections with their own keys:

```yaml
# prompts.yaml
prompts:
  instructions: |
    OneTool executes Python code...

# snippets.yaml
snippets:
  brv_research:
    body: brave.search(query="{{ topic }}")

# servers.yaml
servers:
  github:
    type: http
    url: https://api.githubcopilot.com/mcp/
```

### Projects Configuration

Named projects for path resolution:

```yaml
projects:
  myapp:
    path: /path/to/myapp
    attrs:
      db_url: postgresql://localhost/myapp
      api_key: ${MY_API_KEY}

  onetool:
    path: .
    attrs:
      db_url: sqlite:///demo/db/northwind.db
```

### Tools Configuration

Customise tool behaviour with the `tools:` section:

```yaml
tools:
  brave:
    timeout: 60.0              # 1.0 - 300.0 seconds

  ground:
    model: gemini-2.5-flash    # Gemini model name

  context7:
    timeout: 30.0              # 1.0 - 120.0 seconds
    docs_limit: 10             # 1 - 20 results

  web_fetch:
    timeout: 30.0              # 1.0 - 120.0 seconds
    max_length: 50000          # 1000 - 500000 characters

  ripgrep:
    timeout: 60.0              # 1.0 - 300.0 seconds

  code_search:
    limit: 10                  # 1 - 100 results

  db:
    max_chars: 4000            # 100 - 100000 characters

  # page_view: (beta - see docs/beta/)

  package:
    timeout: 30.0              # 1.0 - 120.0 seconds
```

All tools section fields are optional. Omitted fields use defaults shown above.

### Tools Configuration Reference

| Tool | Field | Type | Default | Range | Description |
|------|-------|------|---------|-------|-------------|
| brave | timeout | float | 60.0 | 1-300 | API request timeout (seconds) |
| ground | model | string | gemini-2.5-flash | - | Gemini model for grounding |
| context7 | timeout | float | 30.0 | 1-120 | API request timeout (seconds) |
| context7 | docs_limit | int | 10 | 1-20 | Max documentation results |
| web_fetch | timeout | float | 30.0 | 1-120 | Page fetch timeout (seconds) |
| web_fetch | max_length | int | 50000 | 1K-500K | Max content characters |
| ripgrep | timeout | float | 60.0 | 1-300 | Search timeout (seconds) |
| code_search | limit | int | 10 | 1-100 | Max search results |
| db | max_chars | int | 4000 | 100-100K | Query output truncation |
| package | timeout | float | 30.0 | 1-120 | Registry request timeout |
| stats | enabled | bool | true | - | Enable statistics collection |
| stats | persist_path | string | stats.jsonl | - | JSONL file for stats (relative to config) |
| stats | flush_interval_seconds | int | 30 | 1-300 | Interval between disk flushes |
| stats | context_per_call | int | 30000 | ≥0 | Context tokens saved per call estimate |
| stats | time_overhead_per_call_ms | int | 4000 | ≥0 | Time overhead saved per call (ms) |
| stats | model | string | anthropic/claude-opus-4.5 | - | Model name for cost estimation |
| stats | cost_per_million_input_tokens | float | 15.0 | ≥0 | Input token cost (USD per million) |
| stats | cost_per_million_output_tokens | float | 75.0 | ≥0 | Output token cost (USD per million) |
| stats | chars_per_token | float | 4.0 | ≥1.0 | Characters per token estimate |

### Statistics Configuration

Track runtime statistics to measure OneTool's efficiency:

```yaml
tools:
  stats:
    enabled: true                    # Enable/disable statistics collection
    persist_path: stats.jsonl        # JSONL file path (relative to config dir)
    flush_interval_seconds: 30       # How often to write to disk
    context_per_call: 30000          # Estimated context tokens saved per call
    time_overhead_per_call_ms: 4000  # Estimated time overhead saved per call
    model: anthropic/claude-opus-4.5 # Model name for cost display
    cost_per_million_input_tokens: 15.0   # Input cost (USD)
    cost_per_million_output_tokens: 75.0  # Output cost (USD)
    chars_per_token: 4.0             # Characters per token estimate
```

**What's tracked:**
- Tool name, characters in/out, duration
- Success/error status with error type
- Timestamp for period filtering

**Viewing statistics:**

Use `ot.stats()` to view aggregated statistics:

```python
# View all-time statistics
ot.stats()

# View last 24 hours
ot.stats(period="day")

# Filter by tool
ot.stats(period="week", tool="brave.search")

# Generate HTML report
ot.stats(output="stats_report.html")
```

**Savings estimates:**

The `context_per_call` and `time_overhead_per_call_ms` settings control how savings are calculated. These represent the overhead that would be incurred by traditional MCP tool calls (tool description in context, round-trip latency) that OneTool eliminates through consolidation.

**Cost estimation:**

Statistics include an estimated cost based on the configured model pricing. Cost is calculated from characters in/out converted to tokens:

```text
tokens = chars / chars_per_token
cost = (input_tokens / 1M × input_cost) + (output_tokens / 1M × output_cost)
```

The HTML report shows the estimated cost with the model name for reference.

### External MCP Servers

Proxy external MCP servers through OneTool:

```yaml
servers:
  package_version:
    type: stdio
    command: npx
    args: ["-y", "mcp-package-version@0.1.17"]
    timeout: 30
```

### Aliases

Short names for common tool functions:

```yaml
alias:
  ws: brave.web_search
  ns: brave.news
  wf: web.fetch
```

### Snippets

Reusable code templates with Jinja2 substitution:

```yaml
snippets:
  multi_search:
    description: Search multiple queries
    params:
      queries: { required: true, description: "List of queries" }
    body: |
      results = []
      for q in {{ queries }}:
          results.append(brave.web_search(query=q))
      "\n---\n".join(results)
```

### External Snippet Files

Load snippets from external YAML files using `include:`:

```yaml
include:
  - resources/config/snippets.yaml       # Shared library
  - project/snippets/local.yaml          # Project additions

snippets:
  # Inline snippets override included ones with same name
  custom:
    body: "demo.foo()"
```

External snippet files must have a `snippets:` key:

```yaml
# my-snippets.yaml
snippets:
  brv_research:
    description: Research a topic with web search
    params:
      topic: { required: true, description: "Topic to research" }
    body: |
      brave.search(query="{{ topic }}")
```

**Resolution order:** Files are loaded in order, then inline snippets override any conflicts.

## Environment Variable Expansion

Config values support `${VAR}` and `${VAR:-default}` syntax:

```yaml
projects:
  myapp:
    path: ${HOME}/projects/myapp
    attrs:
      db_url: ${DATABASE_URL:-sqlite:///local.db}
```

## Validation

Invalid configuration values are rejected at load time with helpful error messages:

```
ValueError: Invalid configuration in config/ot-serve.yaml:
  tools.brave.timeout: Input should be greater than or equal to 1
```

## Example Configurations

### Minimal Configuration

```yaml
version: 1
tools_dir:
  - src/ot_tools/*.py
```

### Production Configuration

```yaml
version: 1

tools_dir:
  - src/ot_tools/*.py

log_level: WARNING
validate_code: true

tools:
  brave:
    timeout: 120.0
  context7:
    timeout: 60.0
    docs_limit: 20
  db:
    max_chars: 8000
  ripgrep:
    timeout: 120.0

projects:
  app:
    path: /srv/myapp
    attrs:
      db_url: ${DATABASE_URL}
```

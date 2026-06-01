# onetool Configuration

Complete reference for `onetool.yaml` configuration.

## Quick Reference

- Use `onetool init --config ~/.onetool` for first-time setup.
- Core config lives in `onetool.yaml`; secrets live in `secrets.yaml`.
- Relative include paths resolve from the directory containing `onetool.yaml`.
- Start with `version`, `include`, `tools_dir`, `servers`, `tools`, `security`.
- Validate with `onetool init validate --config ~/.onetool/onetool.yaml`.

## CLI Flags

Configuration is specified via CLI flags — there is no automatic global or project config discovery.

| Flag | Short | Required | Description |
|------|-------|----------|-------------|
| `--config PATH` | `-c` | Yes (server) | Path to `onetool.yaml` config file or directory |
| `--secrets PATH` | `-s` | No | Path to `secrets.yaml`. If omitted, no secrets are loaded |

**Config path resolution:** If `PATH` ends in `.yaml`/`.yml` it is used as the config file directly; otherwise `onetool.yaml` is appended to the directory path.

**Include path resolution:** All relative paths in `include:`, `tools_dir:`, etc. resolve from the **parent directory of the config file** (i.e., the directory containing `onetool.yaml`).

**Windows paths:** Use backslashes or forward slashes, e.g., `C:\Users\name\.onetool\onetool.yaml`.

## First Run Setup

Run `onetool init` to create a config interactively:

```bash
onetool init                          # Create onetool.yaml in current directory
onetool init --config .onetool              # Create .onetool/onetool.yaml
onetool init --config .onetool/onetool.yaml # Explicit file path

onetool init validate --config .onetool/onetool.yaml  # Validate + show status
```

`onetool init` opens a TUI (interactive checkbox) to select which extensions to install. Existing files are backed up to `.bak` automatically. Running non-interactively (e.g., in CI) writes a minimal `onetool.yaml` with `version: 2`.

## YAML Schema

```yaml
version: 2                    # Config schema version (required)

include:                      # External config files to merge
  - prompts.yaml
  - snippets.yaml
  - servers.yaml

tools_dir:                    # Tool discovery patterns
  - src/ottools/*.py

env:                          # Default subprocess environment variables
  LANG: en_US.UTF-8

log_level: INFO               # DEBUG, INFO, WARNING, ERROR

security:                     # Code validation settings
  validate_code: true
  enabled: true

servers: {}                   # External MCP servers
tools: {}                     # Pack-specific configuration
alias: {}                     # Function aliases
snippets: {}                  # Reusable code templates
prompts: {}                   # Inline prompts (overrides included)
```

## Config Includes

Compose configuration from multiple files:

```yaml
version: 2

include:
  - config/prompts.yaml     # Relative to config parent dir
  - config/snippets.yaml
  - local-snippets.yaml     # Project-only additions

servers:
  local_dev:
    type: stdio
    command: python
```

**Include resolution:**

1. Absolute paths: used as-is
2. Tilde paths (`~/...`): expanded to home directory
3. Relative paths: checked in config parent dir first, then falls back to package-bundled defaults

**Merge behaviour:**

- Files are merged left-to-right (later files override earlier)
- Inline content in the main file overrides everything

!!! note "Bundled defaults are not auto-loaded"
    `snippets.yaml`, `diagram.yaml`, `security.yaml`, and the other bundled config files are
    **not loaded automatically** — they only activate when listed under `include:`.
    `onetool init` writes an `onetool.yaml` that already includes all of them, so this only
    matters if you write your own config from scratch.

    Packaged skills are discovered from bundled resources at runtime; they are not loaded from
    copied files under the OneTool config directory.

## Pack Configuration

Pack settings go under `tools.<pack_name>` in `onetool.yaml`.

### aws

| Field | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `profile` | string \| null | `null` | - | Active AWS profile name |
| `region` | string \| null | `null` | - | Active AWS region |
| `timeout` | int | `30` | `>=1` | Boto3 API call timeout seconds |
| `roles` | object<string, string[]> | `{}` | - | User-defined role name -> server short names |
| `servers` | object<string, string> | `{}` | - | Additional/override AWS MCP servers |

### brave

| Field | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `timeout` | float | `60.0` | `1.0-300.0` | Request timeout in seconds |

### chrome_util

No pack-specific `tools.chrome_util` settings.

### context7

| Field | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `timeout` | float | `30.0` | `1.0-120.0` | Request timeout in seconds |

### convert

No pack-specific `tools.convert` settings.

### db

| Field | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `max_chars` | int | `4000` | `100-100000` | Maximum characters in query result output |

### diagram

| Field | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `backend.type` | `"kroki"` | `"kroki"` | fixed | Backend type |
| `backend.remote_url` | string | `https://kroki.io` | - | Remote Kroki service URL |
| `backend.self_hosted_url` | string | `http://localhost:8000` | - | Self-hosted Kroki URL |
| `backend.prefer` | enum | `remote` | `remote \| self_hosted \| auto` | Backend preference |
| `backend.timeout` | float | `30.0` | `1.0-120.0` | Backend request timeout |
| `policy.rules` | string | built-in policy text | - | Diagram generation policy text |
| `policy.preferred_format` | enum | `svg` | `svg \| png \| pdf` | Preferred output format |
| `policy.preferred_providers` | string[] | `["mermaid","d2","plantuml"]` | - | Preferred providers in order |
| `output.dir` | string | `diagrams` | - | Output directory |
| `output.naming` | string | `{provider}_{name}_{timestamp}` | - | Filename template |
| `output.default_format` | enum | `svg` | `svg \| png \| pdf` | Default output format |
| `output.save_source` | bool | `true` | - | Save source next to rendered output |
| `instructions` | object<string, object> | `{}` | - | Provider guidance overrides |
| `templates` | object<string, object> | `{}` | - | Named template references |

### excel

No pack-specific `tools.excel` settings.

### file

| Field | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `allowed_dirs` | string[] | `[]` | - | Allowed dirs (empty = cwd only) |
| `exclude_patterns` | string[] | `[".git","node_modules","__pycache__",".venv","venv"]` | - | Excluded path patterns |
| `max_file_size` | int | `10000000` | `1000-100000000` | Max file size in bytes |
| `max_list_entries` | int | `1000` | `10-10000` | Max entries for list/tree |
| `backup_on_write` | bool | `true` | - | Create `.bak` before overwrite |
| `use_trash` | bool | `true` | - | Move deleted files to trash |
| `relative_paths` | bool | `true` | - | Return relative paths in output |

### ground

| Field | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `model` | string | `gemini-2.5-flash` | - | Gemini model for grounded search |

### mem

| Field | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `db_path` | string | `data/mem/default.db` | - | SQLite path for memory store |
| `model` | string | `text-embedding-3-small` | - | Embedding model |
| `base_url` | string | `https://openrouter.ai/api/v1` | - | OpenAI-compatible embedding API base |
| `dimensions` | int | `1536` | - | Embedding dimensions |
| `search_limit` | int | `10` | `1-100` | Default max search results |
| `search_extract` | int | `200` | `>=0` | Extract length per result (`0` = full) |
| `redaction_enabled` | bool | `true` | - | Enable redaction on write |
| `redaction_patterns` | string[] | `[]` | - | Extra regex redaction patterns |
| `tags_whitelist` | string[] | `[]` | - | Allowed tag prefixes |
| `decay_half_life_days` | int | `30` | `>=1` | Importance decay half-life |
| `allowed_file_dirs` | string[] | `[]` | - | Allowed dirs for mem file I/O |
| `exclude_file_patterns` | string[] | built-in defaults | - | Excluded paths for mem file I/O |
| `max_embedding_tokens` | int | `8191` | `>=1` | Max tokens per embedding input |
| `read_cache_max_size` | int | `128` | `>=0` | Read cache size (`0` = off) |
| `read_cache_ttl_seconds` | int | `300` | `>=0` | Read cache TTL (`0` = no expiry) |
| `embeddings_enabled` | bool | `false` | - | Enable semantic embeddings |
| `embeddings_async` | bool | `true` | - | Generate embeddings async |

### ot

No pack-specific `tools.ot` settings.

### ot_forge

No pack-specific `tools.ot_forge` settings.

### ot_llm

| Field | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `base_url` | string | `""` | - | OpenAI-compatible API base URL |
| `model` | string | `""` | - | Default model for transforms |
| `timeout` | int | `30` | - | API timeout in seconds |
| `max_tokens` | int \| null | `null` | - | Max response tokens (`null` = no limit) |

### ot_secrets

No pack-specific `tools.ot_secrets` settings.

### ot_timer

No pack-specific `tools.ot_timer` settings.

### package

| Field | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `timeout` | float | `30.0` | `1.0-120.0` | Request timeout in seconds |

### play_util

No pack-specific `tools.play_util` settings.

### ripgrep

| Field | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `timeout` | float | `60.0` | `1.0-300.0` | Command timeout in seconds |
| `relative_paths` | bool | `true` | - | Return relative paths in output |

### whiteboard

No pack-specific `tools.whiteboard` settings.

### webfetch

| Field | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `timeout` | float | `30.0` | `1.0-120.0` | Request timeout in seconds |
| `max_length` | int | `50000` | `1000-500000` | Maximum content length in chars |

Example:

```yaml
tools:
  aws:
    profile: dev
    timeout: 45
  diagram:
    backend:
      prefer: auto
    output:
      dir: docs/diagrams
  ripgrep:
    timeout: 120
    relative_paths: true
  ot_llm:
    model: openai/gpt-4o-mini
```

## Secrets Configuration

API keys stored separately in `secrets.yaml` (gitignored). Pass the path via `--secrets`:

```bash
onetool serve --config .onetool/onetool.yaml --secrets .onetool/secrets.yaml
```

```yaml
# secrets.yaml — values are literal, no ${VAR} expansion
BRAVE_API_KEY: "your-brave-api-key"
OPENAI_API_KEY: "sk-..."
CONTEXT7_API_KEY: "your-context7-key"
GEMINI_API_KEY: "your-gemini-key"
DATABASE_URL: "postgresql://user:pass@localhost/db"
```

If `--secrets` is omitted, no secrets file is loaded. Tools that require API keys will report a configuration error when called.

### Accessing Secrets in Tools

```python
from ot.config.secrets import get_secret

api_key = get_secret("BRAVE_API_KEY")
if not api_key:
    return "Error: BRAVE_API_KEY not configured in secrets.yaml"
```

### Encrypting Secrets at Rest

Values in `secrets.yaml` can be encrypted using [age](https://age-encryption.org) encryption. This is **opt-in** — plain files continue to work without any changes. Once set up, decryption is transparent: OneTool decrypts values in memory when secrets are loaded, and your tools see the plaintext as normal.

**Setup (once per machine):**

```python
# 1. Generate an age X25519 identity and store it in the OS keychain
__run ot_secrets.init(label="my-machine")

# 2. Encrypt all plain values in your secrets file
__run ot_secrets.encrypt(file="~/.onetool/secrets.yaml")
```

After encryption, `secrets.yaml` looks like:

```yaml
# Encrypt values with: __run ot_secrets.encrypt(file=<this file>)
BRAVE_API_KEY: "age1enc:YWdlLWVuY3J5cHRpb24ub3JnL3Yx..."
OPENAI_API_KEY: "age1enc:YWdlLWVuY3J5cHRpb24ub3JnL3Yy..."
```

The file is safe to inspect — values cannot be recovered without the private key in your OS keychain. Encrypted values are safe to commit to version control if needed.

**How it works:**

- The private key is stored in the OS keychain (macOS Keychain, Windows Credential Locker, GNOME libsecret) — never on disk
- `age1enc:` values are decrypted in memory automatically when `secrets.yaml` is loaded
- Plain and encrypted values can coexist in the same file
- Keychain access is lazy: if no `age1enc:` values are present, the keychain is never touched

**Managing encrypted secrets:**

```python
# Check identity status and count encrypted/plain values
__run ot_secrets.status(file="~/.onetool/secrets.yaml")

# Scan for any unencrypted values (safe to run before committing)
__run ot_secrets.audit(file="~/.onetool/secrets.yaml")

# Rotate to a new key (re-encrypts all values)
__run ot_secrets.rotate(file="~/.onetool/secrets.yaml")
```

**Headless / CI environments:** This is a local-dev security feature. CI/CD should continue using environment variables (existing behavior). Plain `secrets.yaml` files are completely unaffected — encryption only triggers when `age1enc:` values are present.

## External MCP Servers

Proxy external MCP servers through OneTool. Supports both stdio (local process) and HTTP (remote server) transports.

### Stdio Servers

Local MCP servers running as subprocesses:

```yaml
servers:
  local_tools:
    type: stdio
    command: npx
    args: ["-y", "some-mcp-server@latest"]
    timeout: 30

  browser_tools:
    type: stdio
    command: npx
    args: ["-y", "browser-mcp-server@latest"]

  docs_tools:
    type: stdio
    command: uvx
    args: ["docs-mcp-server"]
    tool_prefix: "docs_"     # Strip this prefix so docs_search.query() → search.query()
    inherit_env: true
```

**`tool_prefix`:** When set, callers may omit the prefix. For example, with `tool_prefix: "docs_"` you can call `search.query()` instead of `docs_search.query()`. Prefix stripping is resolved automatically at call time.

### HTTP Servers

Remote MCP servers accessed via HTTP/HTTPS:

```yaml
servers:
  # HTTP server without authentication
  local_dev:
    type: http
    url: https://localhost:3000/mcp
    timeout: 30

  # HTTP server with Bearer token authentication
  private_api:
    type: http
    url: ${PRIVATE_MCP_URL}
    auth:
      type: bearer
      token: ${PRIVATE_MCP_TOKEN}  # Expands from secrets.yaml
    headers:
      Accept: "application/json, text/event-stream"
    timeout: 120

  # HTTP server with OAuth 2.1 + PKCE
  docs_api:
    type: http
    url: https://docs-api.local/mcp
    auth:
      type: oauth
      scopes: [tools:read, tools:write]
    timeout: 60
```

**Authentication Types:**

- **None (default)**: No authentication required
- **bearer**: Static token authentication (use `${VAR}` for secrets)
- **oauth**: OAuth 2.1 with PKCE flow (browser-based authorization)

## Aliases

Short names for common tool functions:

```yaml
alias:
  ws: brave.search
  ns: brave.news
  wf: webfetch.fetch
```

## Snippets

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
          results.append(brave.search(query=q))
      "\n---\n".join(results)
```

External snippet files:

```yaml
include:
  - config/snippets.yaml       # Falls back to package default
  - local-snippets.yaml        # Project-specific additions

snippets:
  custom:
    body: "brave.search(query='test')"  # Inline overrides included
```

## Direct API Configuration

Settings for the MCP-owned direct API used by `onetool direct run --port`.
Configure under `direct` in `onetool.yaml`.

```yaml
direct:
  host:
    enabled: false  # true binds the authenticated loopback API from the MCP process
    port: 8765      # Preferred API port; MCP startup probes upward if occupied
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `direct.host.enabled` | bool | `false` | Bind the MCP-owned authenticated loopback direct API when the MCP process starts. |
| `direct.host.port` | int (1-65535) | `8765` | Preferred direct API port. MCP startup tries this port first, then increments until one binds. |

Unrecognised config attributes are ignored with warnings that identify the dotted
path. Recognised attributes with invalid values still fail validation.

## Statistics Configuration

Track runtime statistics:

```yaml
stats:
  enabled: true
  persist_dir: stats
  persist_path: stats.jsonl
  flush_interval_seconds: 30
  context_per_call: 30000
  time_overhead_per_call_ms: 4000
  model: anthropic/claude-opus-4-6
  cost_per_million_input_tokens: 15.0
  cost_per_million_output_tokens: 75.0
  chars_per_token: 4.0
```

View with `ot.stats()`:

```python
ot.stats()                           # All-time
ot.stats(period="day")               # Last 24 hours
ot.stats(period="week", tool="brave.search")
ot.stats(output="stats_report.html") # HTML report
```

## Transform Configuration

Configure the `ot_llm.transform()` tool for LLM-powered text transformations. Add under `tools:`:

```yaml
tools:
  ot_llm:
    model: "openai/gpt-5-mini"                  # Model for transformations
    base_url: "https://openrouter.ai/api/v1"    # OpenAI-compatible API endpoint
    max_tokens: 4096                            # Max output tokens (optional)
    timeout: 30                                 # API timeout in seconds
```

Requires `OPENAI_API_KEY` in secrets.yaml (or compatible provider key).

## Output Configuration

Control large output handling:

```yaml
output:
  max_inline_size: 5000       # Threshold in bytes (0 to disable)
  result_store_dir: tmp       # Directory for stored results
  result_ttl: 3600            # Time-to-live in seconds
  preview_lines: 10           # Lines in summary preview
```

When output exceeds `max_inline_size`, OneTool stores the result and returns a handle. Query with `ot.result(handle="...")`.

## Security Configuration

OneTool uses an **allowlist-based** security model: everything is blocked by default, you explicitly allow what's safe. Tool namespaces (`ot.*`, `brave.*`, etc.) are auto-allowed.

Security rules are defined in `security.yaml` (included by default):

```yaml
security:
  validate_code: true          # Enable AST validation
  enabled: true                # Enable security checks

  builtins:
    allow:
      - [str, int, float, list, dict, set, tuple]  # Types
      - [len, range, enumerate, zip, sorted]       # Iteration
      - [print, repr, format]                      # Output

  imports:
    allow: [json, re, math, datetime, collections, itertools]
    warn: [yaml]               # Allowed but logs warning

  calls:
    block: [pickle.*, yaml.load]  # Blocked qualified calls
    warn: [random.seed]           # Warned qualified calls

  dunders:
    allow: [__format__, __sanitize__]  # Allowed magic variables

  sanitize:
    enabled: true              # Output sanitization (prompt injection protection)
```

**Compact array format:** Group related items for readability:

```yaml
allow:
  - [str, int, float]  # Grouped items
  - print              # Single item
```

### Security Introspection

Check what's allowed at runtime:

```python
ot.security()                    # Summary of all rules
ot.security(check="json")        # Check specific pattern
ot.security(check="pickle.load") # Check qualified call
```

### Output Sanitization

The `security.sanitize` subsection protects against indirect prompt injection by sanitizing tool outputs:

1. **Trigger sanitization:** Replace `__run`, `__r`, `__ot`, and `mcp__onetool` patterns
2. **Tag sanitization:** Remove `<external-content-*>` patterns
3. **GUID-tagged boundaries:** Wrap content in unpredictable tags

Disable per-call with `__sanitize__ = False` prefix.

See [Security Model](../../learn/security.md) for full documentation.

## Environment Variables

Environment variables take priority over the corresponding `onetool.yaml` fields.

| Variable | Description | YAML equivalent |
|----------|-------------|-----------------|
| `OT_LOG_LEVEL` | Log level: `DEBUG`, `INFO`, `WARNING`, or `ERROR` | `log_level` |
| `OT_LOG_VERBOSE` | Enable verbose logging: `true`/`false`/`1`/`0` | `log_verbose` |
| `OT_LOG_DIR` | Log directory path (absolute or relative) | `log_dir` |
| `OT_COMPACT_MAX_LENGTH` | Max value length in compact output (integer) | `compact_max_length` |

## Environment Variable Expansion

Config values support `${VAR}` and `${VAR:-default}` syntax. Variables are expanded at runtime from `secrets.yaml`:

```yaml
servers:
  myserver:
    type: http
    url: ${MY_SERVER_URL:-https://localhost:3000/mcp}
    auth:
      type: bearer
      token: ${MY_API_KEY}
```

## Validation

Invalid values are rejected at load time:

```
ValueError: Invalid configuration in config/onetool.yaml:
  tools.brave.timeout: Input should be greater than or equal to 1
```

## Example Configurations

### Minimal

```yaml
version: 2
tools_dir:
  - src/ottools/*.py
```

### Production

```yaml
version: 2

tools_dir:
  - src/ottools/*.py

log_level: WARNING

security:
  validate_code: true

tools:
  ot_llm:
    model: "openai/gpt-5-mini"
    base_url: "https://openrouter.ai/api/v1"
  brave:
    timeout: 120.0
  context7:
    timeout: 60.0
  db:
    max_chars: 8000
  ripgrep:
    timeout: 120.0
```

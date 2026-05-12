# Logging

OneTool's structured logging infrastructure built on Loguru.

---

## Quick Start

```python
from ot.logging import configure_logging, LogSpan

# Initialize logging for your CLI
configure_logging(log_name="my-cli")

# Use LogSpan for structured operation logging
with LogSpan(span="operation.name", key="value") as s:
    result = do_something()
    s.add("resultCount", len(result))
# Logs automatically on exit with duration and status
```

---

## Core Components

### LogSpan

The primary logging interface. Wraps an operation with automatic timing and status:

```python
from ot.logging import LogSpan

with LogSpan(span="brave.search.web", query=query) as span:
    results = perform_search(query)
    span.add("resultCount", len(results))
    # Auto-logs SUCCESS with duration on exit
```

On exception, auto-logs FAILED with error details.

**Async usage with FastMCP Context:**

```python
async with LogSpan.async_span(ctx, span="tool.execute", tool="search") as s:
    result = await execute_tool()
    await s.log_info("Tool completed", resultCount=len(result))
```

### LogEntry

Low-level structured log entry with fluent API for one-shot log entries without a span context:

```python
from ot.logging import LogEntry

entry = LogEntry(event="command.received")
entry.add("function", func_name).add("found", True)
entry.success(status_code=200)
# or
entry.failure(error=str(exception))
```

### configure_logging(log_name)

Initializes Loguru for file-only output with dev-friendly formatting.

```python
from ot.logging import configure_logging

# In your CLI entry point
configure_logging(log_name="serve")  # Creates logs/serve.log
```

**Environment variables:**
- `OT_LOG_LEVEL`: Log level (default: INFO)
- `OT_LOG_DIR`: Directory for log files (default: ../logs, relative to config dir)
- `OT_LOG_VERBOSE`: Disable truncation, show full values (default: false)

---

## Span Naming

Format: `{component}.{operation}[.{detail}]`

**Examples:**
- `brave.search.web` - Brave web search
- `ripgrep.exec` - Ripgrep execution
- `excel.create` - Excel file creation
- `config.load` - Config loading
- `proxy.connect` - MCP proxy connection
- `mcp.server.start` - Server startup
- `mcp.server.stop` - Server shutdown
- `tool.lookup` - Tool resolution

---

## Adding Context

```python
with LogSpan(span="tool.operation") as span:
    span.add("resultCount", 42)
    span.add(returncode=0, outputLen=1024)
```

Initial context can be passed in the constructor:
```python
LogSpan(span="tool.op", query="test", timeout=30)
```

---

## Examples

### Nested Spans

```python
with LogSpan(span="webfetch.fetch", url=url) as outer:
    # Download
    with LogSpan(span="webfetch.download", url=url) as dl:
        response = download(url)
        dl.add("status", response.status)

    # Extract
    with LogSpan(span="webfetch.extract", url=url) as ext:
        content = extract_content(response)
        ext.add("length", len(content))

    outer.add("success", True)
```

### Async MCP Tool

```python
from ot.logging import LogSpan

async def execute_tool(ctx, tool_name: str, args: dict) -> str:
    async with LogSpan.async_span(ctx, span="tool.execute", tool=tool_name) as s:
        tool = registry.get(tool_name)
        if not tool:
            s.add("error", "not_found")
            return f"Tool {tool_name} not found"

        result = await tool.call(**args)
        s.add("resultLen", len(result))
        return result
```

---

## When to Use

| Scenario | Use |
|----------|-----|
| Wrapping an external call (HTTP, subprocess) | `LogSpan` |
| Recording a discrete event | `LogEntry` |
| Debug output during development | `loguru.logger.debug()` |
| User-facing output | Rich console (not logging) |

---

## Log Output

Logs are written in dev-friendly format to `logs/{log_name}.log` (relative to config directory):

```text
12:34:56.789 | INFO   | server:54  | mcp.server.start | status=SUCCESS | duration=0.042
12:34:57.123 | INFO   | brave:78   | brave.search.web | query=test | resultCount=10 | duration=1.234
12:34:58.456 | ERROR  | webfetch:92 | webfetch.fetch | url=http://... | status=FAILED | errorType=HTTPError
```

**Characteristics:**
- JSON structured format only
- File-only (no console output from library code)
- Automatic duration calculation for spans
- Sensitive data (URLs, API keys) sanitised automatically

---

## Configuration

### Log Levels

Set via `log_level` in `onetool.yaml` or `OT_LOG_LEVEL` environment variable:

| Level | Use Case |
|-------|----------|
| `DEBUG` | Verbose debugging (development only) |
| `INFO` | Normal operation (default) |
| `WARNING` | Potential issues |
| `ERROR` | Failures requiring attention |

### Log Directory

Set via `log_dir` in `onetool.yaml` or `OT_LOG_DIR` environment variable:

- Default: `../logs` (relative to config directory)
- Automatically created if it doesn't exist
- Supports `~` expansion for home directory

### File Rotation

Production logs use automatic rotation:

```python
rotation="10 MB"      # Rotate when file reaches 10 MB
retention="5 days"    # Keep logs for 5 days
```

---

## Output Formatting

Log output is automatically formatted with truncation and credential sanitization at output time. Full values are preserved in `LogEntry` for programmatic access.

### Truncation Limits

Field-based truncation limits (applied unless `OT_LOG_VERBOSE=true`):

| Field Pattern                           | Limit |
| --------------------------------------- | ----- |
| path, filepath, source, dest, directory | 200   |
| command                                 | 200   |
| url                                     | 120   |
| query, topic, pattern, prompt           | 100   |
| error                                   | 300   |
| default                                 | 120   |

### Credential Sanitization

URLs with embedded credentials are automatically masked:

```text
postgres://user:password@host/db → postgres://***:***@host/db
```

Applied to:
- Fields containing "url" in the name
- String values starting with `http://` or `https://`

### Verbose Mode

Disable truncation with `OT_LOG_VERBOSE=true` or `log_verbose: true` in config:

```bash
OT_LOG_VERBOSE=true onetool
```

Credentials are **always** sanitized, even in verbose mode.

### Formatting Functions

```python
from ot.logging import format_log_entry, sanitize_url, format_value

# Format entire log entry
formatted = format_log_entry(entry.to_dict(), verbose=False)

# Sanitize a single URL
safe_url = sanitize_url("postgres://user:pass@host/db")

# Truncate a value with field-based limit
truncated = format_value(long_string, field_name="query")
```

---

## Logger Interception

The logging system intercepts standard Python logging and redirects to Loguru:

**Intercepted loggers** (redirected to Loguru):
- `fastmcp`, `mcp`, `uvicorn`

**Silenced loggers** (set to WARNING level):
- `httpcore`, `httpx`, `hpack` - HTTP transport noise
- `openai`, `openai._base_client` - API client noise
- `anyio`, `mcp` - Async framework noise

---

## Test Logging

For tests, use `configure_test_logging()` instead:

```python
from ot.logging import configure_test_logging

# In conftest.py or test setup
configure_test_logging(
    module_name="test_tools",
    dev_output=True,   # Dev-friendly format to stderr
    dev_file=False,    # No separate dev log file
)
```

This creates:
- `logs/{module_name}.log` - JSON structured logs
- Optional `logs/{module_name}.dev.log` - Dev-friendly format (if `dev_file=True`)

---

**Related:**
- [Tool Development](../project/guides/tool-development.md) - LogSpan usage in tools
- Configuration: `onetool.yaml` → `log_level`, `log_dir`, `log_verbose`

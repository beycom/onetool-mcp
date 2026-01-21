# Logging Guide

This guide covers OneTool's structured logging infrastructure built on Loguru.

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

## Core Components

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

### LogSpan

Context manager that wraps LogEntry and auto-logs on exit with duration and status.

```python
from ot.logging import LogSpan

# Sync usage
with LogSpan(span="tool.execute", tool="search") as s:
    result = execute_tool()
    s.add("resultCount", len(result))
# Logs at INFO level with status=SUCCESS and duration

# With exception handling
with LogSpan(span="api.request", url=url):
    response = make_request()
# On exception: logs at ERROR level with status=FAILED, errorType, errorMessage
```

**Async usage with FastMCP Context:**

```python
async with LogSpan.async_span(ctx, span="tool.execute", tool="search") as s:
    result = await execute_tool()
    await s.log_info("Tool completed", resultCount=len(result))
```

### LogEntry

Low-level structured log entry with fluent API.

```python
from ot.logging import LogEntry

entry = LogEntry(span="operation", key="value")
entry.add("extra", data)
entry.success()  # or entry.failure(error=exc)
logger.info(str(entry))
```

## Span Naming Conventions

Span names use dot-notation: `{component}.{operation}[.{detail}]`

### Server Operations (serve-observability)
- `mcp.server.start` - Server startup
- `mcp.server.stop` - Server shutdown
- `tool.lookup` - Tool resolution

### CLI Operations
- `browse.session.start` - Browser session start
- `browse.navigate` - Navigation
- `browse.screenshot` - Screenshot capture

### Tool Operations

See [Creating Tools](creating-tools.md#logging-with-logspan) for tool span naming conventions.

## Examples

### CLI Initialisation

```python
# In src/ot_browse/app.py
from ot.logging import configure_logging

def main() -> None:
    configure_logging(log_name="browse")
    # ... rest of CLI
```

### Tool Functions

See [Creating Tools](creating-tools.md#logging-with-logspan) for comprehensive tool logging examples.

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

### Nested Spans

```python
with LogSpan(span="browse.session", source=source) as outer:
    # Navigate
    with LogSpan(span="browse.navigate", url=url) as nav:
        page = navigate_to(url)
        nav.add("status", page.status)

    # Capture
    with LogSpan(span="browse.capture", page=page.url) as cap:
        files = capture_page(page)
        cap.add("fileCount", len(files))

    outer.add("success", True)
```

## Log Output

Logs are written in dev-friendly format to `logs/{log_name}.log` (relative to config directory):

```text
12:34:56.789 | INFO   | server:54  | mcp.server.start | status=SUCCESS | duration=0.042
12:34:57.123 | INFO   | brave:78   | brave.search.web | query=test | resultCount=10 | duration=1.234
12:34:58.456 | ERROR  | web:92     | web.fetch | url=http://... | status=FAILED | errorType=HTTPError
```

## Configuration

### Log Levels

Set via `log_level` in `ot-serve.yaml` or `OT_LOG_LEVEL` environment variable:

| Level | Use Case |
|-------|----------|
| `DEBUG` | Verbose debugging (development only) |
| `INFO` | Normal operation (default) |
| `WARNING` | Potential issues |
| `ERROR` | Failures requiring attention |

### Log Directory

Set via `log_dir` in `ot-serve.yaml` or `OT_LOG_DIR` environment variable:

- Default: `../logs` (relative to config directory)
- Automatically created if it doesn't exist
- Supports `~` expansion for home directory

### File Rotation

Production logs use automatic rotation:

```python
rotation="10 MB"      # Rotate when file reaches 10 MB
retention="5 days"    # Keep logs for 5 days
```

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

## Logger Interception

The logging system intercepts standard Python logging and redirects to Loguru:

**Intercepted loggers** (redirected to Loguru):
- `fastmcp`, `mcp`, `uvicorn`

**Silenced loggers** (set to WARNING level):
- `httpcore`, `httpx`, `hpack` - HTTP transport noise
- `openai`, `openai._base_client` - API client noise
- `anyio`, `mcp` - Async framework noise

## Related Documentation

- [Creating Tools](creating-tools.md) - Tool-specific logging patterns and span naming

## Future Work

The following spec features are not yet implemented:
- `OT_LOG_TRUNCATE` - Configurable truncation for long values
- Console output with `--verbose` flag or `OT_LOG_LEVEL=DEBUG`

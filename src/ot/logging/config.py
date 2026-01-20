"""Loguru-based logging configuration.

Outputs structured JSON logs to file only.

Settings from ot-serve.yaml:
- log_level: INFO (default), DEBUG, WARNING, ERROR
- log_dir: Directory for log files (default: ../logs, relative to config dir)
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from loguru import logger

from ot.config.loader import get_config


class InterceptHandler(logging.Handler):
    """Intercept standard logging and redirect to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Redirect log record to Loguru."""
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Store caller info from LogRecord in extra, used by json_serializer
        logger.bind(
            _intercepted_file=record.filename,
            _intercepted_func=record.funcName,
            _intercepted_line=record.lineno,
        ).opt(exception=record.exc_info).log(level, record.getMessage())


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for log fields."""

    def default(self, o: Any) -> Any:
        """Handle non-serializable types."""
        if isinstance(o, datetime):
            if o.tzinfo is None:
                o = o.replace(tzinfo=UTC)
            return o.isoformat().replace("+00:00", "Z")
        elif isinstance(o, Decimal):
            return float(o)
        elif isinstance(o, Path):
            return str(o)
        elif hasattr(o, "__dict__"):
            return o.__dict__
        return super().default(o)


def json_serializer(record: dict[str, Any]) -> str:
    """Serialize log record to JSON.

    The message is expected to be JSON from LogEntry.__str__, so we parse
    and merge it into the log data.
    """
    extra = record["extra"]

    # Use intercepted caller info if available (from standard logging redirect)
    if "_intercepted_file" in extra:
        source = f"{extra['_intercepted_file']}:{extra['_intercepted_func']}:{extra['_intercepted_line']}"
    else:
        source = f"{record['file'].name}:{record['function']}:{record['line']}"

    # Parse source into file, func, line
    src_parts = source.split(":")
    src_file = src_parts[0] if len(src_parts) > 0 else ""
    src_func = src_parts[1] if len(src_parts) > 1 else ""
    src_line = int(src_parts[2]) if len(src_parts) > 2 and src_parts[2].isdigit() else 0

    log_data: dict[str, Any] = {
        "timestamp": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "level": record["level"].name,
        "src_file": src_file,
        "src_func": src_func,
        "src_line": src_line,
    }

    msg = record["message"]
    # Try to parse message as JSON (from LogEntry.__str__)
    if msg.startswith("{") and msg.endswith("}"):
        try:
            parsed = json.loads(msg)
            log_data.update(parsed)
        except json.JSONDecodeError:
            log_data["message"] = msg
    elif msg and msg not in ("Structured log entry", "MCP stage", "MCP tool executed"):
        log_data["message"] = msg

    # Add any extra fields (excluding internal keys)
    public_extra = {k: v for k, v in extra.items() if not k.startswith("_")}
    if public_extra:
        log_data.update(public_extra)

    if record["exception"] is not None:
        log_data["exc_info"] = str(record["exception"])

    return json.dumps(log_data, separators=(",", ":"), cls=JSONEncoder)


def dev_formatter(record: dict[str, Any]) -> str:
    """Format log record as dev-friendly single line.

    Format: HH:MM:SS.mmm | LEVL | file:line | span | key=value | ...
    """
    extra = record["extra"]

    # Short timestamp (time only, date is in filename)
    timestamp = record["time"].strftime("%H:%M:%S.%f")[:-3]

    # 6-char level with padding
    level_map = {
        "DEBUG": "DEBUG ",
        "INFO": "INFO  ",
        "WARNING": "WARN  ",
        "ERROR": "ERROR ",
        "CRITICAL": "CRIT  ",
        "TRACE": "TRACE ",
        "SUCCESS": "OK    ",
    }
    level = level_map.get(record["level"].name, record["level"].name[:6].ljust(6))

    # Short source: file:line (skip function name)
    if "_intercepted_file" in extra:
        src = f"{extra['_intercepted_file'].replace('.py', '')}:{extra['_intercepted_line']}"
    else:
        src = f"{record['file'].name.replace('.py', '')}:{record['line']}"

    parts = [timestamp, level, src]

    # Parse message if it's JSON from LogEntry
    msg = record["message"]
    fields: dict[str, Any] = {}

    if msg.startswith("{") and msg.endswith("}"):
        try:
            fields = json.loads(msg)
        except json.JSONDecodeError:
            if msg.strip():
                fields["message"] = msg
    elif msg.strip():
        fields["message"] = msg

    # Add extra fields (excluding internal keys)
    for k, v in extra.items():
        if not k.startswith("_") and k not in ("serialized", "dev"):
            fields[k] = v

    # Extract span first (most important context)
    span = fields.pop("span", None)
    if span:
        parts.append(str(span))

    # Format remaining fields
    for k, v in fields.items():
        if k == "duration" and v == 0.0:
            continue
        if isinstance(v, list):
            if len(v) > 10:
                list_items = ", ".join(str(x) for x in v[:10])
                parts.append(f"{k}=[{list_items}, ...]")
            else:
                parts.append(f"{k}={v}")
        elif isinstance(v, dict):
            # Show full dict: key={k1=v1, k2=v2, ...}
            dict_items: list[str] = [f"{dk}={dv}" for dk, dv in list(v.items())[:10]]
            if len(v) > 10:
                dict_items.append("...")
            parts.append(f"{k}={{{', '.join(dict_items)}}}")
        elif k == "message":
            # Plain message without key=
            parts.append(str(v))
        else:
            parts.append(f"{k}={v}")

    return " | ".join(parts)


def patching(record: Any) -> None:
    """Patch record with serialized JSON and dev-friendly format."""
    record["extra"]["serialized"] = json_serializer(record)
    record["extra"]["dev"] = dev_formatter(record)


def configure_logging(log_name: str = "onetool", level: str | None = None) -> None:
    """Configure Loguru for file-only output with dev-friendly format.

    Args:
        log_name: Name for the log file (e.g., "serve" -> logs/serve.log)
        level: Optional log level override. If None, uses config value.

    Settings from ot-serve.yaml:
    - log_level: Log level (default: INFO)
    - log_dir: Directory for log files (default: ../logs, relative to config dir)
    """
    logger.remove()

    config = get_config()
    level = (level or config.log_level).upper()
    log_dir = config.get_log_dir_path()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{log_name}.log"

    logger.configure(patcher=patching)

    # Dev-friendly output to log file
    logger.add(
        log_file,
        level=level,
        format="{extra[dev]}",
        colorize=False,
        backtrace=True,
        diagnose=True,
        rotation="10 MB",
        retention="5 days",
    )

    # Intercept standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Intercept FastMCP and related loggers
    for logger_name in ["fastmcp", "mcp", "uvicorn"]:
        logging.getLogger(logger_name).handlers = [InterceptHandler()]
        logging.getLogger(logger_name).propagate = False

    # Silence noisy HTTP/network loggers - set to WARNING to suppress DEBUG spam
    for logger_name in ["httpcore", "httpx", "hpack"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    logger.debug("Logging configured", level=level, file=str(log_file))


def configure_test_logging(
    module_name: str,
    dev_output: bool = True,
    dev_file: bool = False,
) -> None:
    """Configure Loguru for test file logging with optional dev-friendly output.

    Creates a separate log file for each test module in logs/.

    Args:
        module_name: Test module name (e.g., "test_tools")
        dev_output: If True, output dev-friendly logs to stderr
        dev_file: If True, also write dev-friendly logs to {module_name}.dev.log
    """
    import sys

    logger.remove()

    config = get_config()
    level = config.log_level.upper() if config.log_level != "INFO" else "DEBUG"

    # Create logs directory (resolved relative to config dir)
    log_dir = config.get_log_dir_path()
    log_dir.mkdir(parents=True, exist_ok=True)

    # Test-specific log file - append mode
    log_file = log_dir / f"{module_name}.log"

    logger.configure(patcher=patching)

    # JSON output to file
    logger.add(
        str(log_file),
        level=level,
        format="{extra[serialized]}",
        colorize=False,
        backtrace=True,
        diagnose=True,
    )

    # Dev-friendly output to stderr
    if dev_output:
        logger.add(
            sys.stderr,
            level=level,
            format="{extra[dev]}",
            colorize=False,
        )

    # Dev-friendly output to file
    if dev_file:
        dev_log_file = log_dir / f"{module_name}.dev.log"
        logger.add(
            str(dev_log_file),
            level=level,
            format="{extra[dev]}",
            colorize=False,
        )

    # Intercept standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Silence noisy HTTP/network/client loggers - set to WARNING to suppress DEBUG/INFO spam
    for logger_name in [
        "httpcore",
        "httpx",
        "mcp",
        "anyio",
        "hpack",
        "openai",
        "openai._base_client",
    ]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

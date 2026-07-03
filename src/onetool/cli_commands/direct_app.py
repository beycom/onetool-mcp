"""Top-level `onetool direct` subcommand group."""

from __future__ import annotations

import json
import socket
import sys
import time
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.console import Console

direct_app = typer.Typer(
    name="direct",
    help="Run tools through an already-running OneTool MCP process.",
    no_args_is_help=True,
)

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

_VALID_FORMATS = ("json", "json_h", "yml", "yml_h", "raw")


def _tcp_probe(host: str, port: int, timeout: float = 0.1) -> bool:
    """Return True if a TCP connection to host:port succeeds within timeout."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError, TimeoutError):
        return False


def _signed_get(host: str, port: int, *, path: str, timeout: float, ot_dir: Path) -> dict[str, Any]:
    """Return a signed GET payload from the MCP direct API."""
    import urllib.error
    import urllib.request

    from ot.direct_auth import signed_headers, verify_response

    body = b""
    req = urllib.request.Request(
        f"http://{host}:{port}{path}",
        headers=signed_headers(method="GET", path=path, body=body, base_dir=ot_dir),
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            response_body = resp.read()
            verify_response(
                path=path,
                body=response_body,
                headers=dict(resp.headers),
                status_code=resp.status,
                base_dir=ot_dir,
            )
            return cast("dict[str, Any]", json.loads(response_body.decode("utf-8")))
    except urllib.error.HTTPError as e:
        response_body = e.read()
        verify_response(
            path=path,
            body=response_body,
            headers=dict(e.headers),
            status_code=e.code,
            base_dir=ot_dir,
        )
        payload = json.loads(response_body.decode("utf-8"))
        raise RuntimeError(payload.get("result", payload.get("error", str(e)))) from e


def _signed_ready_probe(host: str, port: int, *, ot_dir: Path, timeout: float = 0.5) -> dict[str, Any]:
    """Return signed readiness payload from the MCP direct API."""
    from ot.direct_auth import READY_PATH

    return _signed_get(host, port, path=READY_PATH, timeout=timeout, ot_dir=ot_dir)


def _signed_health_probe(host: str, port: int, *, ot_dir: Path, timeout: float = 0.5) -> dict[str, Any]:
    """Return signed health payload from the MCP direct API."""
    from ot.direct_auth import HEALTH_PATH

    return _signed_get(host, port, path=HEALTH_PATH, timeout=timeout, ot_dir=ot_dir)


def _run_via_server(
    command: str,
    host: str,
    port: int,
    *,
    fmt: str,
    sanitize: bool,
    ot_dir: Path,
    timeout: int = 60,
) -> tuple[str, bool]:
    """POST command to the MCP direct API, return (result, success)."""
    import urllib.error
    import urllib.request

    from ot.direct_api import PROTOCOL_VERSION
    from ot.direct_auth import RUN_PATH, signed_headers, verify_response

    body = json.dumps(
        {
            "protocol_version": PROTOCOL_VERSION,
            "operation": "run",
            "command": command,
            "format": fmt,
            "sanitize": sanitize,
        },
        separators=(",", ":"),
    ).encode()
    req = urllib.request.Request(
        f"http://{host}:{port}{RUN_PATH}",
        data=body,
        headers={
            "Content-Type": "application/json",
            **signed_headers(method="POST", path=RUN_PATH, body=body, base_dir=ot_dir),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            response_body = resp.read()
            status_code = resp.status
            headers = dict(resp.headers)
    except urllib.error.HTTPError as e:
        response_body = e.read()
        status_code = e.code
        headers = dict(e.headers)

    verify_response(
        path=RUN_PATH,
        body=response_body,
        headers=headers,
        status_code=status_code,
        base_dir=ot_dir,
    )
    data = json.loads(response_body)
    if data.get("protocol_version") != PROTOCOL_VERSION:
        raise RuntimeError("Direct API protocol mismatch")
    return data.get("result", ""), bool(data.get("success", True))


def _resolve_command_source(cmd_str: str | None) -> str | None:
    """Resolve the command source from the raw argument.

    - None → None (no command given)
    - "-" → read from stdin
    - "foo.py" (file exists, .py extension) → read file contents
    - anything else → use as-is
    """
    if cmd_str is None:
        return None
    if cmd_str == "-":
        return sys.stdin.read().strip() or None
    p = Path(cmd_str)
    if p.suffix == ".py" and p.exists():
        return p.read_text(encoding="utf-8").strip() or None
    return cmd_str


def _default_ot_dir() -> Path:
    """Return the default client-side OneTool directory."""
    from ot.paths import expand_path

    return expand_path("~/.onetool")


def _resolve_ot_dir(value: Path | None) -> Path:
    """Resolve and validate the direct client auth directory."""
    from ot.paths import expand_path

    if value is None:
        return _default_ot_dir()

    if not str(value).startswith("~") and not value.is_absolute():
        err_console.print("[red]Error: --ot-dir must be an absolute path after ~ expansion.[/red]")
        raise typer.Exit(2)
    resolved = expand_path(str(value))
    return resolved


# ---------------------------------------------------------------------------
# `onetool direct run`
# ---------------------------------------------------------------------------


@direct_app.command("run")
def direct_run(
    command: Annotated[
        str | None,
        typer.Argument(
            help="Tool command to execute. Use '-' to read from stdin, or a .py file path."
        ),
    ] = None,
    port: Annotated[
        int | None,
        typer.Option("--port", "-p", help="Target MCP direct API port", min=1, max=65535),
    ] = None,
    ot_dir: Annotated[
        Path | None,
        typer.Option(
            "--ot-dir",
            help="Absolute OneTool directory containing auth/mcp-direct.key",
        ),
    ] = None,
    fmt: Annotated[
        str,
        typer.Option(
            "--format", "-f",
            help="Output format: json_h (default), json, yml, yml_h, raw",
        ),
    ] = "json_h",
    sanitize: Annotated[
        bool,
        typer.Option("--sanitize", help="Enable output sanitization (for AI pipeline use)"),
    ] = False,
    timeout_opt: Annotated[
        int | None,
        typer.Option(
            "--timeout",
            "-t",
            help="Direct API request timeout in seconds",
        ),
    ] = None,
) -> None:
    """Execute a tool command from the shell.

    COMMAND is the tool call to execute, e.g. 'ot.debug()'.
    Pass '-' to read from stdin, or a path to an existing .py file.

    The command connects to an MCP process exposing the direct API on --port.

    Examples:
        onetool direct run --port 8765 "ot.debug()"
        onetool direct run --ot-dir ~/.onetool --port 8765 "ot.debug()"
        echo "ot.debug()" | onetool direct run --port 8765 -
        onetool direct run --port 8765 report.py
    """
    if fmt not in _VALID_FORMATS:
        err_console.print(
            f"[red]Error: --format must be one of {', '.join(_VALID_FORMATS)} (got {fmt!r})[/red]"
        )
        raise typer.Exit(2)

    cmd_str = _resolve_command_source(command)
    if not cmd_str:
        err_console.print("[red]Error: no command provided.[/red]")
        raise typer.Exit(2)

    if port is None:
        err_console.print("[red]Error: target port required. Use --port / -p.[/red]")
        raise typer.Exit(2)

    resolved_ot_dir = _resolve_ot_dir(ot_dir)
    host = "127.0.0.1"
    timeout = timeout_opt if timeout_opt is not None else 120
    err_console.print(f"[dim]direct.run target port: {port}[/dim]")
    start = time.monotonic()
    try:
        if not _tcp_probe(host, port):
            err_console.print(f"[red]Direct API unreachable on 127.0.0.1:{port}[/red]")
            raise typer.Exit(1)
        err_console.print("[dim]direct.run signed health/readiness check[/dim]")
        health = _signed_health_probe(host, port, ot_dir=resolved_ot_dir, timeout=min(timeout, 5))
        if health.get("protocol_version") != 1:
            err_console.print("[red]Direct API protocol mismatch during health check[/red]")
            raise typer.Exit(1)
        _signed_ready_probe(host, port, ot_dir=resolved_ot_dir, timeout=min(timeout, 5))
        err_console.print("[dim]direct.run authenticated connect succeeded[/dim]")
        result_text, success = _run_via_server(
            cmd_str,
            host,
            port,
            fmt=fmt,
            sanitize=sanitize,
            ot_dir=resolved_ot_dir,
            timeout=timeout,
        )
    except Exception as e:
        if isinstance(e, typer.Exit):
            raise
        err_console.print(f"[red]Direct API error:[/red] {e}")
        raise typer.Exit(1) from e

    duration_ms = int((time.monotonic() - start) * 1000)
    err_console.print(
        f"[dim]direct.run completed duration_ms={duration_ms} success={success}[/dim]"
    )
    print(result_text)
    raise typer.Exit(0 if success else 1)

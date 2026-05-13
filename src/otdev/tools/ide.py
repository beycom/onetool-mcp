"""Read-only IDE state from a local VS Code companion bridge."""

from __future__ import annotations

pack = "ide"
__all__ = [
    "connect",
    "editor",
    "file",
    "get_state",
    "paths",
    "sel",
    "state",
    "workspace",
]

import json
from typing import Any, Literal
from urllib.parse import urljoin

import httpx
from otpack import (
    HmacAuthError,
    LogSpan,
    NonceCache,
    ensure_hmac_key,
    get_effective_cwd,
    get_tool_config,
    sign_http_message,
    verify_http_message,
)
from otpack import (
    get_state as get_project_state,
)
from otpack import (
    set_state as set_project_state,
)
from pydantic import BaseModel, Field, ValidationError


def register_services(registry: object) -> None:
    """Register IDE output handling policy."""
    from ot.services import OutputPolicy

    registry.register_output_policy(  # type: ignore[attr-defined]
        lambda tool_name: OutputPolicy(allow_sanitize=False)
        if tool_name.startswith("ide.")
        else None
    )

from ot.utils import lazy_client

PROTOCOL_VERSION = 1
DEFAULT_PORT_START = 58764
DEFAULT_PORT_COUNT = 10
STATE_PACK = "ide"
STATE_CONNECTION_ID = "connection_id"
INCLUDE_VALUES = {"connection", "selection", "active_editor", "workspace"}

IncludeName = Literal["connection", "selection", "active_editor", "workspace"]
IncludeArg = Literal["all"] | list[IncludeName]
DEFAULT_CONNECTION_ID: str | None = None
DISCOVERED_BASE_URLS: dict[str, str] = {}
_RESPONSE_NONCES = NonceCache()


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    base_url: str | None = Field(
        default=None,
        description="Explicit loopback URL override for the VS Code IDE bridge.",
    )
    port_start: int = Field(
        default=DEFAULT_PORT_START,
        ge=1024,
        le=65535,
        description="First loopback port to scan for the VS Code IDE bridge.",
    )
    port_count: int = Field(
        default=DEFAULT_PORT_COUNT,
        ge=1,
        le=10,
        description="Number of loopback ports to scan for the VS Code IDE bridge.",
    )
    timeout: float = Field(
        default=3.0,
        ge=0.1,
        le=30.0,
        description="Bridge request timeout in seconds.",
    )

class IdeStateError(RuntimeError):
    """Raised when the IDE bridge or response contract is invalid."""


class Connection(BaseModel):
    """User-facing IDE connection metadata."""

    id: str


class Workspace(BaseModel):
    """VS Code workspace metadata."""

    name: str | None = None
    workspace_folders: list[str] = Field(default_factory=list)
    workspace_file: str | None = None


class Document(BaseModel):
    """Active editor document metadata."""

    path: str
    dirty: bool
    untitled: bool


class VisibleRange(BaseModel):
    """One visible range in the active editor viewport."""

    start_line: int
    end_line: int


class ActiveEditor(BaseModel):
    """Active editor metadata and viewport."""

    visible_ranges: list[VisibleRange] = Field(default_factory=list)
    document: Document


class SelectionRange(BaseModel):
    """One editor selection range."""

    start_line: int
    start_character: int
    end_line: int
    end_character: int


class Selection(BaseModel):
    """Active editor selection snapshot."""

    path: str
    ranges: list[SelectionRange]
    text: str


class Snapshot(BaseModel):
    """Stable bridge snapshot shape returned by the extension."""

    connection: Connection
    workspace: Workspace = Field(default_factory=Workspace)
    active_editor: ActiveEditor | None = None
    selection: Selection | None = None


class BridgeResponse(BaseModel):
    """Bridge response envelope."""

    protocol_version: int
    snapshot: Snapshot


class BridgeHealth(BaseModel):
    """Bridge health response used for discovery."""

    ok: bool
    protocol_version: int
    connection: Connection
    workspace: Workspace = Field(default_factory=Workspace)


def _get_config() -> Config:
    """Return typed pack configuration."""
    return get_tool_config("ide", Config)


def _create_http_client() -> httpx.Client:
    """Create the shared bridge HTTP client."""
    return httpx.Client(timeout=_get_config().timeout)


_get_http_client = lazy_client(_create_http_client)


def _normalise_base_url(base_url: str) -> str:
    """Return a safe loopback base URL."""
    if not base_url.startswith(("http://127.0.0.1:", "http://localhost:")):
        raise IdeStateError("IDE bridge base_url must use local loopback HTTP")
    return base_url.rstrip("/") + "/"


def _scan_base_urls(cfg: Config) -> list[str]:
    """Return the configured loopback base URLs to scan."""
    if cfg.port_start + cfg.port_count - 1 > 65535:
        raise IdeStateError("IDE bridge port_start + port_count exceeds 65535")
    return [
        f"http://127.0.0.1:{port}/"
        for port in range(cfg.port_start, cfg.port_start + cfg.port_count)
    ]


def _validate_include(include: IncludeArg) -> set[IncludeName]:
    """Validate requested sections and expand all."""
    if include == "all":
        return {"connection", "selection", "active_editor", "workspace"}
    if not isinstance(include, list):
        raise ValueError(
            'include must be "all" or a list containing connection, selection, active_editor, workspace'
        )

    invalid = [item for item in include if item not in INCLUDE_VALUES]
    if invalid:
        accepted = ", ".join(sorted(INCLUDE_VALUES))
        raise ValueError(
            f"Invalid include value(s): {', '.join(invalid)}. Accepted values: all, {accepted}"
        )
    return set(include)


def _auth_key() -> bytes:
    """Return the IDE bridge HMAC key."""
    from ot.meta import resolve_ot_path

    return ensure_hmac_key("ide", base_dir=resolve_ot_path("."))


def _json_bytes(payload: object) -> bytes:
    """Return stable compact JSON bytes for bridge signing."""
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _signed_headers(
    *,
    method: str,
    path: str,
    body: bytes,
) -> dict[str, str]:
    """Return request headers for an authenticated bridge call."""
    headers = sign_http_message(
        key=_auth_key(),
        method=method,
        path=path,
        body=body,
    )
    headers["content-type"] = "application/json"
    return headers


def _verify_response(
    *,
    response: httpx.Response,
    path: str,
) -> None:
    """Verify a signed bridge response."""
    try:
        verify_http_message(
            key=_auth_key(),
            status_code=response.status_code,
            path=path,
            body=response.content,
            headers=dict(response.headers),
            nonce_cache=_RESPONSE_NONCES,
        )
    except HmacAuthError as exc:
        raise IdeStateError(f"IDE bridge authentication failed: {exc}") from exc


def _bridge_health(*, base_url: str) -> BridgeHealth | None:
    """Fetch authenticated bridge health, returning None for non-bridges."""
    url = urljoin(base_url, "health")
    try:
        response = _get_http_client().get(
            url,
            headers=_signed_headers(method="GET", path="/health", body=b""),
            timeout=_get_config().timeout,
        )
    except httpx.RequestError:
        return None

    if response.status_code >= 400:
        return None

    try:
        _verify_response(response=response, path="/health")
        data = response.json()
        parsed = BridgeHealth.model_validate(data)
    except (IdeStateError, ValueError, ValidationError):
        return None

    if not parsed.ok or parsed.protocol_version != PROTOCOL_VERSION:
        return None
    return parsed


def _discover_base_url(*, connection_id: str, force: bool = False) -> str:
    """Find and cache a bridge base URL for a connection id."""
    cfg = _get_config()
    if cfg.base_url:
        return _normalise_base_url(cfg.base_url)
    if not force and connection_id in DISCOVERED_BASE_URLS:
        return DISCOVERED_BASE_URLS[connection_id]

    for base_url in _scan_base_urls(cfg):
        health = _bridge_health(base_url=base_url)
        if health is not None and health.connection.id == connection_id:
            DISCOVERED_BASE_URLS[connection_id] = base_url
            return base_url

    raise IdeStateError(
        f"No authenticated IDE bridge found for connection id {connection_id!r} "
        f"on 127.0.0.1:{cfg.port_start}..{cfg.port_start + cfg.port_count - 1}"
    )


def _request_state(
    *,
    connection_id: str,
    base_url: str,
) -> BridgeResponse:
    """Fetch and validate state from the companion bridge."""
    cfg = _get_config()
    url = urljoin(base_url, "state")
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "operation": "get_state",
        "connection_id": connection_id,
    }
    body = _json_bytes(payload)

    try:
        response = _get_http_client().post(
            url,
            content=body,
            headers=_signed_headers(method="POST", path="/state", body=body),
            timeout=cfg.timeout,
        )
    except httpx.ConnectError as exc:
        raise IdeStateError(
            f"IDE bridge unavailable at {base_url}. Is the VS Code companion extension running?"
        ) from exc
    except httpx.RequestError as exc:
        raise IdeStateError(f"IDE bridge request failed: {exc}") from exc

    _verify_response(response=response, path="/state")

    if response.status_code == 404:
        raise IdeStateError(f"Unknown IDE connection id: {connection_id}")
    if response.status_code >= 400:
        raise IdeStateError(
            f"IDE bridge returned HTTP {response.status_code}: {response.text}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise IdeStateError("IDE bridge returned malformed JSON") from exc

    try:
        parsed = BridgeResponse.model_validate(data)
    except ValidationError as exc:
        fields = sorted(
            ".".join(str(part) for part in error["loc"]) for error in exc.errors()
        )
        raise IdeStateError(
            "IDE bridge schema validation failed for: " + ", ".join(fields)
        ) from exc

    if parsed.protocol_version != PROTOCOL_VERSION:
        raise IdeStateError(
            f"IDE bridge protocol mismatch: expected {PROTOCOL_VERSION}, got {parsed.protocol_version}"
        )
    if parsed.snapshot.connection.id != connection_id:
        raise IdeStateError(
            f"IDE bridge returned connection {parsed.snapshot.connection.id}, expected {connection_id}"
        )
    return parsed


def _bridge_get_state(*, connection_id: str) -> BridgeResponse:
    """Fetch and validate state from the companion bridge."""
    base_url = _discover_base_url(connection_id=connection_id)
    try:
        return _request_state(connection_id=connection_id, base_url=base_url)
    except IdeStateError as exc:
        if _get_config().base_url:
            raise
        if "authentication failed" not in str(exc) and "unavailable" not in str(exc) and "Unknown IDE connection" not in str(exc):
            raise
        DISCOVERED_BASE_URLS.pop(connection_id, None)
        base_url = _discover_base_url(connection_id=connection_id, force=True)
        return _request_state(connection_id=connection_id, base_url=base_url)


def _resolve_connection_id(id: str | None) -> str:
    """Resolve an explicit or stored IDE connection id."""
    if id:
        return id
    if DEFAULT_CONNECTION_ID:
        return DEFAULT_CONNECTION_ID
    stored = get_project_state(STATE_PACK, STATE_CONNECTION_ID)
    if isinstance(stored, str) and stored:
        return stored
    raise IdeStateError("No IDE connection selected. Run ide.connect(id=...) or pass id=... to this call.")


def _filter_snapshot(
    snapshot: Snapshot,
    requested: set[IncludeName],
) -> dict[str, Any]:
    """Apply OneTool-side include filtering."""
    result: dict[str, Any] = {}
    if "connection" in requested:
        result["connection"] = snapshot.connection.model_dump()
    if "selection" in requested:
        result["selection"] = (
            snapshot.selection.model_dump() if snapshot.selection is not None else None
        )
    if "active_editor" in requested:
        result["active_editor"] = (
            snapshot.active_editor.model_dump()
            if snapshot.active_editor is not None
            else None
        )
    if "workspace" in requested:
        result["workspace"] = snapshot.workspace.model_dump()
    return result


def _workspace_warning(snapshot: Snapshot) -> str | None:
    """Return a warning when VS Code context is outside the current working tree."""
    cwd = str(get_effective_cwd().resolve())
    folders = [folder.rstrip("/") for folder in snapshot.workspace.workspace_folders]
    if (
        folders
        and cwd not in folders
        and not any(cwd.startswith(f"{f}/") for f in folders)
    ):
        return f"OneTool cwd {cwd} is not inside the IDE workspace folders"
    return None


def connect(*, id: str) -> dict[str, Any]:
    """Select the default VS Code IDE connection for subsequent calls.

    Args:
        id: User-facing connection id from the VS Code companion extension.

    Returns:
        Connection metadata for the selected IDE connection.
    """
    global DEFAULT_CONNECTION_ID

    with LogSpan(span="ide.connect", connectionId=id) as span:
        response = _bridge_get_state(connection_id=id)
        DEFAULT_CONNECTION_ID = id
        set_project_state(STATE_PACK, STATE_CONNECTION_ID, id)
        span.add("connected", True)
        return response.snapshot.connection.model_dump()


def state(*, id: str | None = None, include: IncludeArg = "all") -> dict[str, Any]:
    """Return read-only state from a VS Code IDE connection.

    Args:
        id: Optional connection id. Uses the default from `connect()` when omitted.
        include: "all" or a list containing connection, selection, active_editor,
            and workspace.

    Returns:
        Validated IDE state snapshot filtered to requested sections.
    """
    requested = _validate_include(include)
    connection_id = _resolve_connection_id(id)
    with LogSpan(span="ide.state", connectionId=connection_id, include=include) as span:
        response = _bridge_get_state(connection_id=connection_id)
        result = _filter_snapshot(response.snapshot, requested)
        warning = _workspace_warning(response.snapshot)
        if warning is not None:
            result["warnings"] = [warning]
            span.add("warning", "workspace_mismatch")
        span.add("sections", sorted(result))
        return result


def get_state(*, id: str | None = None, include: IncludeArg = "all") -> dict[str, Any]:
    """Return read-only state from a VS Code IDE connection."""
    return state(id=id, include=include)


def sel(*, id: str | None = None) -> str:
    """Return the active editor selection state."""
    selection = state(id=id, include=["selection"])["selection"]
    if selection is None:
        return "No active selection."
    ranges = ", ".join(
        f"{item['start_line']}:{item['start_character']}-{item['end_line']}:{item['end_character']}"
        for item in selection["ranges"]
    )
    return f"{selection['path']}\nRanges: {ranges}\n\n{selection['text']}"


def file(*, id: str | None = None) -> str:
    """Return the active editor document metadata."""
    active_editor = state(id=id, include=["active_editor"])["active_editor"]
    if active_editor is None:
        return "No active editor."
    document = active_editor["document"]
    flags = []
    if document["dirty"]:
        flags.append("dirty")
    if document["untitled"]:
        flags.append("untitled")
    suffix = f" ({', '.join(flags)})" if flags else ""
    return f"{document['path']}{suffix}"


def editor(*, id: str | None = None) -> str:
    """Return active editor metadata and visible ranges."""
    active_editor = state(id=id, include=["active_editor"])["active_editor"]
    if active_editor is None:
        return "No active editor."
    document = active_editor["document"]
    ranges = ", ".join(
        f"{item['start_line']}-{item['end_line']}"
        for item in active_editor["visible_ranges"]
    )
    return f"{document['path']}\nVisible ranges: {ranges or 'none'}"


def workspace(*, id: str | None = None) -> str:
    """Return VS Code workspace metadata."""
    workspace_state = state(id=id, include=["workspace"])["workspace"]
    lines = [workspace_state["name"] or "Unnamed workspace"]
    if workspace_state["workspace_file"]:
        lines.append(f"Workspace file: {workspace_state['workspace_file']}")
    lines.extend(workspace_state["workspace_folders"])
    return "\n".join(lines)


def paths(*, id: str | None = None) -> str:
    """Return useful paths from the current IDE state."""
    snapshot = state(id=id, include=["workspace", "active_editor", "selection"])
    result: list[str] = []
    result.extend(snapshot["workspace"]["workspace_folders"])
    active_editor = snapshot["active_editor"]
    if active_editor is not None:
        result.append(active_editor["document"]["path"])
    selection = snapshot["selection"]
    if selection is not None:
        result.append(selection["path"])
    return "\n".join(dict.fromkeys(result))

"""State management for the browser CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, CDPSession, Page


class ConnectionState(Enum):
    """Browser connection state."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class Annotation:
    """A single element annotation."""

    id: str  # e.g., "btn-1", "err-1"
    label: str  # Human/LLM-readable description
    selector: str  # CSS selector
    comment: str = ""  # User comment


@dataclass
class ConsoleMessage:
    """A captured console message."""

    type: str  # log, warn, error, info, debug
    text: str
    timestamp: float
    location: str | None = None


@dataclass
class NetworkRequest:
    """A captured network request with response."""

    url: str
    method: str
    resource_type: str
    status: int | None = None
    status_text: str | None = None
    headers: dict[str, str] | None = None
    response_headers: dict[str, str] | None = None
    post_data: str | None = None
    response_body: str | None = None  # For JSON/text responses
    timing: dict[str, float] | None = None
    size: int | None = None
    timestamp: float = 0.0


@dataclass
class BrowserState:
    """Current browser state."""

    connection: ConnectionState = ConnectionState.DISCONNECTED
    url: str = ""
    title: str = ""
    error: str | None = None

    # Playwright objects (None when disconnected)
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None
    cdp: CDPSession | None = None

    # Event collection (populated by listeners)
    console_messages: list[ConsoleMessage] = field(default_factory=list)
    network_requests: list[NetworkRequest] = field(default_factory=list)


@dataclass
class AppState:
    """Application state."""

    browser: BrowserState = field(default_factory=BrowserState)
    annotations: list[Annotation] = field(default_factory=list)
    annotation_mode: bool = False
    session_name: str | None = None
    capture_count: int = 0

    # Counters for annotation IDs
    _id_counters: dict[str, int] = field(default_factory=dict)

    def next_annotation_id(self, prefix: str = "el") -> str:
        """Generate the next annotation ID with the given prefix."""
        count = self._id_counters.get(prefix, 0) + 1
        self._id_counters[prefix] = count
        return f"{prefix}-{count}"

    def add_annotation(
        self, selector: str, label: str, prefix: str = "el", comment: str = ""
    ) -> Annotation:
        """Add a new annotation."""
        ann = Annotation(
            id=self.next_annotation_id(prefix),
            label=label,
            selector=selector,
            comment=comment,
        )
        self.annotations.append(ann)
        return ann

    def remove_annotation(self, annotation_id: str) -> bool:
        """Remove an annotation by ID."""
        for i, ann in enumerate(self.annotations):
            if ann.id == annotation_id:
                self.annotations.pop(i)
                return True
        return False

    def clear_annotations(self) -> None:
        """Clear all annotations."""
        self.annotations.clear()

"""Browser service package.

Provides browser connection and inspection capabilities via Playwright CDP.
"""

from __future__ import annotations

from .actions import BrowserActionsMixin
from .capture import BrowserCaptureMixin
from .core import BrowserServiceCore

__all__ = ["BrowserService"]


class BrowserService(BrowserServiceCore, BrowserActionsMixin, BrowserCaptureMixin):
    """Complete browser service with connection, actions, and capture capabilities.

    Composed from:
    - BrowserServiceCore: Connection, navigation, event handling
    - BrowserActionsMixin: Annotation and element operations
    - BrowserCaptureMixin: Screenshot and comprehensive capture
    """

    pass

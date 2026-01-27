"""Factory utilities for OneTool SDK.

Provides thread-safe lazy initialization patterns for API clients.

Example:
    from ot_sdk import lazy_client

    # Define a client factory
    def create_my_client():
        from mylib import Client
        api_key = get_secret("MY_API_KEY")
        return Client(api_key=api_key)

    # Create a lazy-initialized getter
    get_client = lazy_client(create_my_client)

    # Use it anywhere - initialized once, thread-safe
    client = get_client()
"""

from __future__ import annotations

import threading
from typing import Callable, TypeVar

T = TypeVar("T")


def lazy_client(
    factory: Callable[[], T | None],
    *,
    allow_none: bool = False,
) -> Callable[[], T | None]:
    """Create a thread-safe lazy-initialized client getter.

    Wraps a factory function with double-checked locking to ensure
    the client is created exactly once, even under concurrent access.

    The factory function should:
    - Return the client instance on success
    - Return None if required credentials are missing
    - Raise exceptions for other errors

    Args:
        factory: Callable that creates and returns the client instance
        allow_none: If True, cache None results. If False (default), retry
                   factory on each call when it returns None.

    Returns:
        A callable that returns the lazily-initialized client

    Example:
        from ot_sdk import lazy_client, get_secret, get_config

        def create_firecrawl():
            from firecrawl import FirecrawlApp
            api_key = get_secret("FIRECRAWL_API_KEY")
            if not api_key:
                return None
            api_url = get_config("tools.firecrawl.api_url")
            return FirecrawlApp(api_key=api_key, api_url=api_url or None)

        get_firecrawl = lazy_client(create_firecrawl)

        # Later, in tool functions:
        def scrape(url: str) -> str:
            client = get_firecrawl()
            if client is None:
                return "Error: FIRECRAWL_API_KEY not configured"
            return client.scrape_url(url)
    """
    client: T | None = None
    initialized = False
    lock = threading.Lock()

    def get_client() -> T | None:
        nonlocal client, initialized

        # Fast path: already initialized
        if initialized:
            return client

        # Slow path: acquire lock and initialize
        with lock:
            # Double-check after acquiring lock
            if initialized:
                return client

            result = factory()

            # Cache result if successful or allow_none is True
            if result is not None or allow_none:
                client = result
                initialized = True

            return result

    return get_client


class LazyClient:
    """Class-based lazy client for more complex initialization patterns.

    Useful when you need to pass the factory as a method or need
    additional client management features.

    Example:
        class MyPack:
            def __init__(self):
                self._client = LazyClient(self._create_client)

            def _create_client(self):
                return SomeClient(api_key=get_secret("API_KEY"))

            def search(self, query: str) -> str:
                client = self._client.get()
                if client is None:
                    return "Error: API_KEY not configured"
                return client.search(query)
    """

    def __init__(
        self,
        factory: Callable[[], T | None],
        *,
        allow_none: bool = False,
    ) -> None:
        """Initialize the lazy client wrapper.

        Args:
            factory: Callable that creates the client
            allow_none: If True, cache None results
        """
        self._factory = factory
        self._allow_none = allow_none
        self._client: T | None = None
        self._initialized = False
        self._lock = threading.Lock()

    def get(self) -> T | None:
        """Get the client, initializing if necessary.

        Returns:
            The client instance, or None if not available
        """
        if self._initialized:
            return self._client

        with self._lock:
            if self._initialized:
                return self._client

            result = self._factory()

            if result is not None or self._allow_none:
                self._client = result
                self._initialized = True

            return result

    def reset(self) -> None:
        """Reset the client, forcing re-initialization on next access.

        Useful for testing or when configuration changes.
        """
        with self._lock:
            self._client = None
            self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if the client has been initialized."""
        return self._initialized

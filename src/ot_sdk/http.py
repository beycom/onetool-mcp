"""HTTP client utilities for worker tools.

Provides a pre-configured httpx client with sensible defaults for tool use.
The client is reused across calls to benefit from connection pooling.
"""

from __future__ import annotations

from typing import Any

import httpx

# Default timeout for HTTP requests (seconds)
DEFAULT_TIMEOUT = 30.0

# Global client instance (lazy initialized)
_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    """Get or create the shared HTTP client with connection pooling."""
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=httpx.Timeout(DEFAULT_TIMEOUT),
            follow_redirects=True,
            headers={
                "User-Agent": "OneTool-Worker/1.0",
            },
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30.0,
            ),
        )
    return _client


class HttpNamespace:
    """HTTP client namespace with convenient methods."""

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Make a GET request.

        Args:
            url: Request URL
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout override

        Returns:
            httpx.Response object
        """
        client = _get_client()
        return client.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
        )

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        content: bytes | str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Make a POST request.

        Args:
            url: Request URL
            json: JSON body
            data: Form data
            content: Raw content body (bytes or str)
            headers: Additional headers
            timeout: Request timeout override

        Returns:
            httpx.Response object
        """
        client = _get_client()
        return client.post(
            url,
            json=json,
            data=data,
            content=content,
            headers=headers,
            timeout=timeout,
        )

    def client(
        self,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        headers: dict[str, str] | None = None,
    ) -> httpx.Client:
        """Create a custom HTTP client.

        Use this when you need different settings than the shared client.

        Args:
            base_url: Base URL for all requests
            timeout: Request timeout in seconds
            headers: Default headers

        Returns:
            New httpx.Client instance
        """
        # Build kwargs - only include base_url if provided (httpx doesn't accept None)
        kwargs: dict[str, Any] = {
            "timeout": httpx.Timeout(timeout),
            "follow_redirects": True,
            "headers": {
                "User-Agent": "OneTool-Worker/1.0",
                **(headers or {}),
            },
        }
        if base_url is not None:
            kwargs["base_url"] = base_url

        return httpx.Client(**kwargs)


# Singleton instance
http = HttpNamespace()

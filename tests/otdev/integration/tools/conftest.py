"""Shared fixtures for integration tests.

Loads and decrypts API keys from tests/.onetool/secrets.yaml.
Injects them into the runtime secret cache so tools get keys without
depending on the runtime secret resolver path resolution.

Starts all configured MCP server connections (session-scoped) so that
whiteboard, play_util, and chrome_util integration tests can run.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
import pytest

from ot.config.loader import get_config
from ot.proxy.manager import get_proxy_manager

from tests._test_secrets import _PROJECT_ROOT, _secrets, _secrets_module, get_test_secret


def require_server(name: str) -> None:
    """Fail the test if the named MCP server is not connected.

    Args:
        name: Server name (e.g., "playwright", "chrome_devtools")
    """
    proxy = get_proxy_manager()
    if name not in proxy.servers:
        connected = ", ".join(proxy.servers) or "none"
        pytest.fail(
            f"'{name}' MCP server not connected. "
            f"Connected: {connected}. "
            f"Check tests/.onetool/onetool.yaml."
        )


@pytest.fixture(autouse=True)
def _inject_secrets():
    """Inject test secrets into the runtime cache.

    Sets the module-level _secrets dict directly so all call sites
    (regardless of import style) resolve keys from secrets.yaml.
    """
    old = _secrets_module._secrets
    _secrets_module._secrets = _secrets
    yield
    _secrets_module._secrets = old


_TEST_CONFIG = _PROJECT_ROOT / "tests" / ".onetool" / "onetool.yaml"


@pytest.fixture(scope="session")
def _connect_proxy_servers():
    """Connect all MCP proxy servers configured in the test onetool.yaml.

    Session-scoped: runs once for the entire test session.
    Fails immediately if the connection attempt itself errors.
    Individual tests call require_server() to check their specific server.
    """
    config = get_config(config_path=_TEST_CONFIG)
    if not config.servers:
        pytest.fail("No servers configured in test onetool.yaml — cannot run integration tests")

    proxy = get_proxy_manager()

    loop = asyncio.new_event_loop()
    ready = threading.Event()
    error: list[Exception] = []

    def _run_loop() -> None:
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(proxy.connect(config.servers))
        except Exception as exc:
            error.append(exc)
        finally:
            ready.set()
        # Keep the loop running so call_tool_sync / run_coroutine_threadsafe work
        loop.run_forever()

    thread = threading.Thread(target=_run_loop, daemon=True)
    thread.start()
    ready.wait(timeout=180)

    if error:
        pytest.fail(f"Proxy connection failed: {error[0]}")

    yield

    # Teardown: shutdown proxy and stop the loop
    future = asyncio.run_coroutine_threadsafe(proxy.shutdown(), loop)
    with contextlib.suppress(Exception):
        future.result(timeout=10)
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)


__all__ = ["get_test_secret", "require_server"]

"""Tests for worker proxy classes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ot.executor.worker_proxy import (
    WorkerFunctionProxy,
    WorkerPackProxy,
    create_worker_function,
    create_worker_proxy,
)


@pytest.mark.unit
@pytest.mark.core
class TestWorkerFunctionProxy:
    """Tests for WorkerFunctionProxy class."""

    def test_calls_worker_pool(self) -> None:
        """Should route calls through worker pool."""
        mock_pool = MagicMock()
        mock_pool.call.return_value = "result"

        with patch("ot.executor.worker_proxy.get_worker_pool", return_value=mock_pool):
            proxy = WorkerFunctionProxy(
                tool_path=Path("/path/to/tool.py"),
                function_name="search",
                config={"key": "value"},
                secrets={"API_KEY": "secret"},
            )

            result = proxy(query="test")

            assert result == "result"
            mock_pool.call.assert_called_once_with(
                tool_path=Path("/path/to/tool.py"),
                function="search",
                kwargs={"query": "test"},
                config={"key": "value"},
                secrets={"API_KEY": "secret"},
            )

    def test_repr(self) -> None:
        """Should have informative repr."""
        proxy = WorkerFunctionProxy(
            tool_path=Path("/path/to/brave_search.py"),
            function_name="search",
            config={},
            secrets={},
        )

        assert "brave_search" in repr(proxy)
        assert "search" in repr(proxy)


@pytest.mark.unit
@pytest.mark.core
class TestWorkerPackProxy:
    """Tests for WorkerPackProxy class."""

    def test_getattr_returns_function_proxy(self) -> None:
        """Should return function proxy for valid function name."""
        proxy = WorkerPackProxy(
            tool_path=Path("/path/to/tool.py"),
            functions=["search", "fetch"],
            config={},
            secrets={},
        )

        func_proxy = proxy.search
        assert isinstance(func_proxy, WorkerFunctionProxy)
        assert func_proxy.function_name == "search"

    def test_getattr_caches_function_proxy(self) -> None:
        """Should cache function proxies."""
        proxy = WorkerPackProxy(
            tool_path=Path("/path/to/tool.py"),
            functions=["search"],
            config={},
            secrets={},
        )

        func1 = proxy.search
        func2 = proxy.search

        assert func1 is func2

    def test_getattr_raises_for_unknown_function(self) -> None:
        """Should raise AttributeError for unknown function."""
        proxy = WorkerPackProxy(
            tool_path=Path("/path/to/tool.py"),
            functions=["search"],
            config={},
            secrets={},
        )

        with pytest.raises(AttributeError, match="has no function 'unknown'"):
            _ = proxy.unknown

    def test_getattr_raises_for_private_attr(self) -> None:
        """Should raise AttributeError for private attribute access."""
        proxy = WorkerPackProxy(
            tool_path=Path("/path/to/tool.py"),
            functions=["search"],
            config={},
            secrets={},
        )

        with pytest.raises(AttributeError, match="Cannot access private"):
            _ = proxy._private

    def test_dir_returns_function_names(self) -> None:
        """Should return function names for introspection."""
        proxy = WorkerPackProxy(
            tool_path=Path("/path/to/tool.py"),
            functions=["search", "fetch"],
            config={},
            secrets={},
        )

        assert set(dir(proxy)) == {"search", "fetch"}

    def test_repr(self) -> None:
        """Should have informative repr."""
        proxy = WorkerPackProxy(
            tool_path=Path("/path/to/brave.py"),
            functions=["search", "web"],
            config={},
            secrets={},
        )

        result = repr(proxy)
        assert "brave" in result
        assert "search" in result
        assert "web" in result


@pytest.mark.unit
@pytest.mark.core
class TestCreateWorkerProxy:
    """Tests for create_worker_proxy factory function."""

    def test_creates_namespace_proxy(self) -> None:
        """Should create WorkerPackProxy."""
        proxy = create_worker_proxy(
            tool_path=Path("/path/to/tool.py"),
            functions=["search", "fetch"],
            config={"key": "value"},
            secrets={"API_KEY": "secret"},
        )

        assert isinstance(proxy, WorkerPackProxy)
        assert "search" in dir(proxy)
        assert "fetch" in dir(proxy)

    def test_defaults_to_empty_config_and_secrets(self) -> None:
        """Should default config and secrets to empty dicts."""
        proxy = create_worker_proxy(
            tool_path=Path("/path/to/tool.py"),
            functions=["search"],
        )

        assert proxy.config == {}
        assert proxy.secrets == {}


@pytest.mark.unit
@pytest.mark.core
class TestCreateWorkerFunction:
    """Tests for create_worker_function factory function."""

    def test_creates_function_proxy(self) -> None:
        """Should create WorkerFunctionProxy."""
        func = create_worker_function(
            tool_path=Path("/path/to/tool.py"),
            function_name="search",
            config={"key": "value"},
            secrets={"API_KEY": "secret"},
        )

        assert isinstance(func, WorkerFunctionProxy)
        assert func.function_name == "search"
        assert callable(func)

    def test_defaults_to_empty_config_and_secrets(self) -> None:
        """Should default config and secrets to empty dicts."""
        func = create_worker_function(
            tool_path=Path("/path/to/tool.py"),
            function_name="search",
        )

        assert func.config == {}
        assert func.secrets == {}

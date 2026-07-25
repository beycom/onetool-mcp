"""Behavioral tests for the canonical standalone batch helpers."""

from __future__ import annotations

from typing import Any

import pytest

import otpack.batch as batch_module
from otpack import batch_execute_enveloped


@pytest.mark.unit
@pytest.mark.pkg
class TestBatchExceptionProvenance:
    def test_value_error_is_one_attempt_error(self, monkeypatch: pytest.MonkeyPatch):
        calls = 0
        sleeps: list[float] = []

        def fail(_query: str, _label: str) -> str:
            nonlocal calls
            calls += 1
            raise ValueError("timeout while parsing")

        monkeypatch.setattr(batch_module.time, "sleep", sleeps.append)
        output = batch_execute_enveloped(
            fail,
            [("query", "label")],
            retries=3,
            retry_delay_ms=25,
        )

        item = output["results"][0]
        assert calls == 1
        assert sleeps == []
        assert item["status"] == "error"
        assert item["attempts"] == 1
        assert item["retried"] is False
        assert item["final_failure"] is True
        assert item["error"] == {
            "error_code": "unknown_error",
            "error_message": "ValueError: timeout while parsing",
            "provider_status": None,
        }

    def test_timeout_exception_exhausts_configured_attempts(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        sleeps: list[float] = []

        def timeout(_query: str, _label: str) -> str:
            raise TimeoutError("provider stalled")

        monkeypatch.setattr(batch_module.time, "sleep", sleeps.append)
        output = batch_execute_enveloped(
            timeout,
            [("query", "label")],
            retries=2,
            retry_delay_ms=25,
        )

        item = output["results"][0]
        assert sleeps == [0.025, 0.05]
        assert item["status"] == "error"
        assert item["attempts"] == 3
        assert item["retried"] is True
        assert item["final_failure"] is True
        assert item["error"] == {
            "error_code": "timeout",
            "error_message": "TimeoutError: provider stalled",
            "provider_status": None,
        }

    def test_connection_exception_retries_then_recovers(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        calls = 0
        sleeps: list[float] = []

        def connect(_query: str, _label: str) -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ConnectionError("peer reset")
            return "recovered"

        monkeypatch.setattr(batch_module.time, "sleep", sleeps.append)
        output = batch_execute_enveloped(
            connect,
            [("query", "label")],
            retries=2,
            retry_delay_ms=10,
        )

        item = output["results"][0]
        assert calls == 2
        assert sleeps == [0.01]
        assert item["status"] == "ok"
        assert item["data"] == "recovered"
        assert item["attempts"] == 2
        assert item["retried"] is True
        assert item["final_failure"] is False

    def test_exception_like_returned_string_remains_successful_data(self):
        output = batch_execute_enveloped(
            lambda _query, _label: "ValueError: boom",
            [("query", "label")],
            retries=3,
            retry_delay_ms=0,
        )

        item = output["results"][0]
        assert item["status"] == "ok"
        assert item["data"] == "ValueError: boom"
        assert item["attempts"] == 1
        assert output["meta"]["success_count"] == 1
        assert output["meta"]["error_count"] == 0

    def test_mixed_results_preserve_order_counts_and_per_item_errors(self):
        class ProviderHttpError(RuntimeError):
            pass

        def execute(query: str, _label: str) -> Any:
            if query == "bad":
                raise ProviderHttpError("HTTP 503 unavailable")
            return {"query": query}

        output = batch_execute_enveloped(
            execute,
            [("first", "First"), ("bad", "Bad"), ("last", "Last")],
            retry_delay_ms=0,
        )

        assert [item["query"] for item in output["results"]] == [
            "first",
            "bad",
            "last",
        ]
        assert [item["status"] for item in output["results"]] == [
            "ok",
            "error",
            "ok",
        ]
        assert output["results"][1]["error"] == {
            "error_code": "http_5xx",
            "error_message": "ProviderHttpError: HTTP 503 unavailable",
            "provider_status": 503,
        }
        assert output["meta"] == {
            "query_count": 3,
            "success_count": 2,
            "error_count": 1,
            "partial_success": True,
            "retries": 0,
            "retry_delay_ms": 0,
        }

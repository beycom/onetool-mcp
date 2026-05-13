"""Batch processing utilities for OneTool packs.

Provides concurrent execution helpers for tools that process multiple items.

Example:
    from otpack import batch_execute, normalize_items

    # Process URLs concurrently
    def fetch_one(url: str, label: str) -> tuple[str, str]:
        result = fetch(url)
        return label, result

    urls = ["https://a.com", ("https://b.com", "Custom Label")]
    normalized = normalize_items(urls)  # [(url, label), ...]
    results = batch_execute(fetch_one, normalized, max_workers=5)
"""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any, Literal, TypedDict, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "BatchEnvelope",
    "BatchError",
    "BatchMeta",
    "BatchResultItem",
    "batch_execute",
    "batch_execute_enveloped",
    "format_batch_results",
    "normalize_items",
]

T = TypeVar("T")
R = TypeVar("R")


class BatchError(TypedDict):
    """Structured per-item batch error."""

    error_code: str
    error_message: str
    provider_status: int | None


class BatchResultItem(TypedDict):
    """Structured per-item batch result."""

    label: str
    query: str
    status: Literal["ok", "error"]
    data: Any | None
    error: BatchError | None
    attempts: int
    retried: bool
    final_failure: bool


class BatchMeta(TypedDict):
    """Structured batch summary metadata."""

    query_count: int
    success_count: int
    error_count: int
    partial_success: bool
    retries: int
    retry_delay_ms: int


class BatchEnvelope(TypedDict):
    """Structured batch envelope."""

    results: list[BatchResultItem]
    meta: BatchMeta


_HTTP_STATUS_RE = re.compile(r"\b(?:HTTP|status)\s*(\d{3})\b", re.IGNORECASE)


def _is_error_result(result: Any) -> bool:
    """Return True when a tool result appears to represent an error."""
    if isinstance(result, str):
        lowered = result.lower()
        return (
            lowered.startswith("error:")
            or lowered.startswith("search failed:")
            or lowered.startswith("request failed")
            or lowered.startswith("request timeout")
            or lowered.startswith("connection error")
            or lowered.startswith("http error")
        )
    return False


def _classify_error(error_message: str) -> tuple[str, bool, int | None]:
    """Classify errors into normalized codes and transient/non-transient classes."""
    lowered = error_message.lower()
    status_match = _HTTP_STATUS_RE.search(error_message)
    provider_status = int(status_match.group(1)) if status_match else None

    if "timeout" in lowered or "timed out" in lowered:
        return "timeout", True, provider_status
    if "connection" in lowered or "network" in lowered:
        return "connection_error", True, provider_status
    if provider_status == 429 or "rate limit" in lowered:
        return "rate_limited", True, provider_status
    if provider_status is not None and 500 <= provider_status <= 599:
        return "http_5xx", True, provider_status
    if provider_status is not None and 400 <= provider_status <= 499:
        return "http_4xx", False, provider_status
    return "unknown_error", False, provider_status


def batch_execute_enveloped(
    func: Callable[[str, str], Any],
    items: list[tuple[str, str]],
    *,
    retries: int = 0,
    retry_delay_ms: int = 250,
    max_workers: int | None = None,
) -> BatchEnvelope:
    """Execute batch items with structured envelopes and transient retry handling."""
    if retries < 0:
        raise ValueError("retries must be >= 0")
    if retry_delay_ms < 0:
        raise ValueError("retry_delay_ms must be >= 0")
    if not items:
        return {
            "results": [],
            "meta": {
                "query_count": 0,
                "success_count": 0,
                "error_count": 0,
                "partial_success": False,
                "retries": retries,
                "retry_delay_ms": retry_delay_ms,
            },
        }

    if max_workers is None:
        max_workers = min(len(items), 10)

    def _execute_one(query: str, label: str) -> BatchResultItem:
        attempts = 0
        max_attempts = retries + 1

        while attempts < max_attempts:
            attempts += 1
            try:
                result = func(query, label)
            except Exception as exc:  # pragma: no cover - exercised via search pack tests
                result = f"{type(exc).__name__}: {exc}"

            if not _is_error_result(result):
                return {
                    "label": label,
                    "query": query,
                    "status": "ok",
                    "data": result,
                    "error": None,
                    "attempts": attempts,
                    "retried": attempts > 1,
                    "final_failure": False,
                }

            message = str(result)
            error_code, is_transient, provider_status = _classify_error(message)
            should_retry = is_transient and attempts < max_attempts
            if should_retry:
                backoff_ms = retry_delay_ms * (2 ** (attempts - 1))
                if backoff_ms > 0:
                    time.sleep(backoff_ms / 1000.0)
                continue

            return {
                "label": label,
                "query": query,
                "status": "error",
                "data": None,
                "error": {
                    "error_code": error_code,
                    "error_message": message,
                    "provider_status": provider_status,
                },
                "attempts": attempts,
                "retried": attempts > 1,
                "final_failure": True,
            }

        return {
            "label": label,
            "query": query,
            "status": "error",
            "data": None,
            "error": {
                "error_code": "unknown_error",
                "error_message": "Error: unknown batch execution failure",
                "provider_status": None,
            },
            "attempts": attempts,
            "retried": attempts > 1,
            "final_failure": True,
        }

    ordered_results: list[BatchResultItem] = [
        {
            "label": label,
            "query": query,
            "status": "error",
            "data": None,
            "error": {
                "error_code": "unknown_error",
                "error_message": "Error: result missing",
                "provider_status": None,
            },
            "attempts": 0,
            "retried": False,
            "final_failure": True,
        }
        for query, label in items
    ]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_execute_one, query, label): idx
            for idx, (query, label) in enumerate(items)
        }
        for future in as_completed(futures):
            ordered_results[futures[future]] = future.result()

    success_count = sum(1 for item in ordered_results if item["status"] == "ok")
    error_count = len(ordered_results) - success_count
    return {
        "results": ordered_results,
        "meta": {
            "query_count": len(ordered_results),
            "success_count": success_count,
            "error_count": error_count,
            "partial_success": success_count > 0 and error_count > 0,
            "retries": retries,
            "retry_delay_ms": retry_delay_ms,
        },
    }


def normalize_items(
    items: list[str] | list[tuple[str, str]] | list[str | tuple[str, str]],
) -> list[tuple[str, str]]:
    """Normalize a list of items to (value, label) tuples.

    Accepts items as either:
    - A string (used as both value and label)
    - A tuple of (value, label)

    Args:
        items: List of items as strings or (value, label) tuples

    Returns:
        List of (value, label) tuples
    """
    normalized: list[tuple[str, str]] = []
    for item in items:
        if isinstance(item, str):
            normalized.append((item, item))
        else:
            normalized.append(item)
    return normalized


def batch_execute(
    func: Callable[[str, str], tuple[str, R]],
    items: list[tuple[str, str]],
    *,
    max_workers: int | None = None,
    preserve_order: bool = True,
) -> dict[str, R]:
    """Execute a function concurrently on multiple items.

    Runs the provided function on each item using a ThreadPoolExecutor.
    The function receives (value, label) and must return (label, result).

    Args:
        func: Function taking (value: str, label: str) and returning (label, result)
        items: List of (value, label) tuples (use normalize_items to prepare)
        max_workers: Maximum concurrent workers. Defaults to len(items) (up to 10)
        preserve_order: If True (default), results maintain input order

    Returns:
        Dict mapping labels to results
    """
    if not items:
        return {}

    if max_workers is None:
        max_workers = min(len(items), 10)

    results: dict[str, R] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(func, value, label): label for value, label in items
        }
        for future in as_completed(futures):
            label, result = future.result()
            results[label] = result

    if preserve_order:
        # Rebuild dict in original order
        ordered: dict[str, R] = {}
        for _, label in items:
            if label in results:
                ordered[label] = results[label]
        return ordered

    return results


def format_batch_results(
    results: dict[str, Any],
    items: list[tuple[str, str]],
    separator: str = "===",
) -> str:
    """Format batch results as labeled sections.

    Creates a formatted string with section headers for each result,
    preserving the original order from the items list.

    Args:
        results: Dict mapping labels to result strings
        items: Original list of (value, label) tuples for ordering
        separator: Section separator character(s) (default: "===")

    Returns:
        Formatted string with sections like "=== Label ===\\n{content}"
    """
    sections = []
    for _, label in items:
        if label in results:
            content = results[label]
            sections.append(f"{separator} {label} {separator}\n{content}")
    return "\n\n".join(sections)

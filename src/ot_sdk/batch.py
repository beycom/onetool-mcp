"""Batch processing utilities for OneTool SDK.

Provides concurrent execution helpers for tools that process multiple items.

Example:
    from ot_sdk import batch_execute, normalize_items

    # Process URLs concurrently
    def fetch_one(url: str, label: str) -> tuple[str, str]:
        result = fetch(url)
        return label, result

    urls = ["https://a.com", ("https://b.com", "Custom Label")]
    normalized = normalize_items(urls)  # [(url, label), ...]
    results = batch_execute(fetch_one, normalized, max_workers=5)
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def normalize_items(
    items: list[str] | list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Normalize a list of items to (value, label) tuples.

    Accepts items as either:
    - A string (used as both value and label)
    - A tuple of (value, label)

    This is the standard pattern for batch operations in OneTool,
    allowing users to provide custom labels for results.

    Args:
        items: List of items as strings or (value, label) tuples

    Returns:
        List of (value, label) tuples

    Example:
        # Simple list
        normalize_items(["a", "b", "c"])
        # Returns: [("a", "a"), ("b", "b"), ("c", "c")]

        # Mixed list
        normalize_items(["a", ("b", "Custom B")])
        # Returns: [("a", "a"), ("b", "Custom B")]

        # Labeled list
        normalize_items([
            ("https://example.com", "Example"),
            ("https://docs.python.org", "Python Docs"),
        ])
        # Returns: [("https://example.com", "Example"), ...]
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

    Example:
        def search_one(query: str, label: str) -> tuple[str, str]:
            result = some_search(query)
            return label, result

        items = normalize_items(["query1", ("query2", "Custom")])
        results = batch_execute(search_one, items, max_workers=5)
        # results = {"query1": ..., "Custom": ...}
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

    Example:
        results = {"A": "content a", "B": "content b"}
        items = [("x", "A"), ("y", "B")]
        output = format_batch_results(results, items)
        # "=== A ===\\ncontent a\\n\\n=== B ===\\ncontent b"
    """
    sections = []
    for _, label in items:
        if label in results:
            content = results[label]
            sections.append(f"{separator} {label} {separator}\n{content}")
    return "\n\n".join(sections)

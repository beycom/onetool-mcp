"""Exception handling utilities."""

from __future__ import annotations


def flatten_exception_group(
    eg: BaseExceptionGroup[BaseException],
) -> list[BaseException]:
    """Recursively flatten nested ExceptionGroups to get leaf exceptions.

    Args:
        eg: The exception group to flatten.

    Returns:
        List of leaf exceptions (non-group exceptions).
    """
    result: list[BaseException] = []
    for exc in eg.exceptions:
        if isinstance(exc, BaseExceptionGroup):
            result.extend(flatten_exception_group(exc))
        else:
            result.append(exc)
    return result

"""Demo tools for OneTool testing and benchmarking.

These tools return deterministic but non-guessable outputs based on input.
Used to verify that code was actually executed rather than guessed by an LLM.
"""

from __future__ import annotations

import hashlib

# Pack for dot notation: demo.foo(), demo.bar()
pack = "demo"

__all__ = ["foo", "bar"]

_FOO_WORDS = [
    "red",
    "blue",
    "green",
    "yellow",
    "purple",
    "orange",
    "pink",
    "brown",
    "silver",
    "gold",
    "cyan",
    "magenta",
    "teal",
    "coral",
    "navy",
    "olive",
]

_BAR_WORDS = [
    "tiger",
    "eagle",
    "dolphin",
    "wolf",
    "falcon",
    "panther",
    "cobra",
    "fox",
    "hawk",
    "lion",
    "shark",
    "raven",
    "bear",
    "lynx",
    "orca",
    "viper",
]


def foo(*, text: str) -> str:
    """Map a string to a color word.

    Returns a deterministic but non-guessable color based on the input.
    The mapping cannot be predicted without execution.

    Args:
        text: Any input string.

    Returns:
        A color word (e.g., "red", "blue", "green").

    Example:
        demo.foo(text="hello world")
    """
    h = hashlib.md5(f"foo-{text}".encode()).digest()
    index = h[0] % len(_FOO_WORDS)
    return _FOO_WORDS[index]


def bar(*, text: str) -> str:
    """Map a string to an animal word.

    Returns a deterministic but non-guessable animal based on the input.
    The mapping cannot be predicted without execution.

    Args:
        text: Any input string.

    Returns:
        An animal word (e.g., "tiger", "eagle", "dolphin").

    Example:
        demo.bar(text="hello world")
    """
    h = hashlib.md5(f"bar-{text}".encode()).digest()
    index = h[0] % len(_BAR_WORDS)
    return _BAR_WORDS[index]



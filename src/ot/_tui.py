"""Shared TUI primitives for interactive CLI tools.

Used by ot-bench for interactive selection prompts.
"""

from __future__ import annotations

import questionary
from questionary import Style

# Consistent style across all prompts
APP_STYLE = Style(
    [
        ("qmark", "fg:#5c9aff bold"),
        ("question", "fg:#e0e0e0 bold"),
        ("answer", "fg:#7dd3a8"),
        ("pointer", "fg:#5c9aff bold"),
        ("highlighted", "fg:#ffffff bg:#3d5a80"),
        ("selected", "fg:#7dd3a8"),
    ]
)


async def safe_ask(question: questionary.Question) -> str | None:
    """Wrap questionary ask with graceful cancellation."""
    try:
        result = await question.ask_async()
        return str(result) if result is not None else None
    except KeyboardInterrupt:
        return None


async def ask_select(
    prompt: str,
    choices: list[questionary.Choice],
) -> str | None:
    """Prompt for selection with shortcuts."""
    return await safe_ask(
        questionary.select(
            prompt,
            choices=choices,
            style=APP_STYLE,
            use_shortcuts=True,
            use_arrow_keys=True,
            instruction="",
        )
    )


async def ask_text(prompt: str, default: str = "") -> str | None:
    """Prompt for text input. Ctrl+C to cancel, empty = None."""
    result = await safe_ask(questionary.text(prompt, default=default, style=APP_STYLE))
    return result if result else None

"""Shared TUI primitives for interactive CLI tools."""

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
        ("checkbox", "fg:#e0e0e0"),
        ("checkbox-selected", "fg:#7dd3a8 bold"),
    ]
)


async def safe_ask(question: questionary.Question) -> object:
    """Wrap questionary ask with graceful cancellation."""
    try:
        return await question.ask_async()
    except KeyboardInterrupt:
        return None


async def ask_select(
    prompt: str,
    choices: list[questionary.Choice],
) -> str | None:
    """Prompt for single selection with shortcuts."""
    result = await safe_ask(
        questionary.select(
            prompt,
            choices=choices,
            style=APP_STYLE,
            use_shortcuts=True,
            use_arrow_keys=True,
            instruction="(↑↓ to move, enter to select, ctrl+c to exit)",
        )
    )
    return str(result) if result is not None else None


async def ask_text(prompt: str, default: str = "") -> str | None:
    """Prompt for text input. Ctrl+C to cancel, empty = None."""
    result = await safe_ask(questionary.text(prompt, default=default, style=APP_STYLE))
    return str(result) if result else None


def ask_checkbox(
    prompt: str,
    choices: list[questionary.Choice],
) -> list[str] | None:
    """Synchronous checkbox prompt. Returns None on Ctrl+C."""
    try:
        result: list[str] | None = questionary.checkbox(
            prompt,
            choices=choices,
            instruction="(space to toggle, enter to confirm, ctrl+c to exit)",
            style=APP_STYLE,
        ).ask()
        return result
    except KeyboardInterrupt:
        return None


def ask_text_sync(prompt: str, default: str = "") -> str | None:
    """Synchronous text input prompt. Returns None on Ctrl+C."""
    try:
        result = questionary.text(prompt, default=default, style=APP_STYLE).ask()
        return str(result) if result is not None else None
    except KeyboardInterrupt:
        return None

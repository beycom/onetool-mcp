"""Shortcuts system for OneTool.

Provides aliases and snippets for simplified tool invocation:
- Aliases: Short names mapping to full function names (e.g., ws -> brave.web_search)
- Snippets: Jinja2 templates with variable substitution ($wsq q1=AI q2=ML p=Compare)
"""

from ot.shortcuts.aliases import resolve_alias
from ot.shortcuts.snippets import expand_snippet, parse_snippet

__all__ = [
    "expand_snippet",
    "parse_snippet",
    "resolve_alias",
]

from __future__ import annotations

import pytest

from otdev.docsgen.tool_index import (
    description_by_arg,
    format_text,
    short_description,
    signature_args,
)

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def test_signature_args_compacts_keyword_only_and_string_annotations() -> None:
    signature = "(thing: 'str', *, limit: \"int\" = 10, enabled: bool = True)"

    assert signature_args(signature) == "thing: str, limit: int=10, enabled: bool=True"


def test_signature_args_returns_empty_for_invalid_signature() -> None:
    assert signature_args("not a signature") == ""


def test_description_by_arg_ignores_non_argument_rows() -> None:
    detail = {"args": ["path: Project path", "invalid", 123, "limit: Max rows"]}

    assert description_by_arg(detail) == {
        "path": "Project path",
        "limit": "Max rows",
    }


def test_short_description_uses_first_non_empty_line() -> None:
    assert short_description("\n\n First line.\nSecond line.") == "First line."


def test_format_text_renders_descriptions_and_arg_docs() -> None:
    inventory = [
        {
            "pack": "demo",
            "short": "dm",
            "tools": [
                {
                    "name": "demo.run",
                    "args": "path: str",
                    "description": "Run demo.",
                    "arg_descriptions": {"path": "Project path"},
                }
            ],
        }
    ]

    output = format_text(
        inventory,
        include_tool_descriptions=True,
        include_descriptions=True,
    )

    assert output == "\n".join(
        [
            "# OneTool MCP Tool Index",
            "",
            "packs=1 tools=1",
            "\n## demo, dm",
            "```python",
            "demo.run(path: str)  # Run demo.",
            "# path: Project path",
            "```",
        ]
    )


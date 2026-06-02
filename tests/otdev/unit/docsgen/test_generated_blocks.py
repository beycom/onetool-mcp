from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from otdev.docsgen.generated_blocks import (
    load_pack_descriptions,
    render_pack_table,
    replace_block_text,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def test_replace_block_text_replaces_existing_block() -> None:
    text = "\n".join(
        [
            "Before",
            "<!-- BEGIN GENERATED:DEMO -->",
            "old",
            "<!-- END GENERATED:DEMO -->",
            "After",
        ]
    )

    assert replace_block_text(text, "DEMO", "new") == "\n".join(
        [
            "Before",
            "<!-- BEGIN GENERATED:DEMO -->",
            "new",
            "<!-- END GENERATED:DEMO -->",
            "After",
        ]
    )


def test_replace_block_text_appends_missing_block() -> None:
    output = replace_block_text("Before\n", "DEMO", "new")

    assert output == "\n".join(
        [
            "Before",
            "",
            "<!-- BEGIN GENERATED:DEMO -->",
            "new",
            "<!-- END GENERATED:DEMO -->",
            "",
        ]
    )


def test_load_pack_descriptions_normalizes_multiline_descriptions(tmp_path: Path) -> None:
    prompts = tmp_path / "prompts.yaml"
    prompts.write_text(
        "prompts:\n  packs:\n    demo: |\n      First line\n      second line\n",
        encoding="utf-8",
    )

    assert load_pack_descriptions(prompts) == [("demo", "First line second line")]


def test_load_pack_descriptions_rejects_non_mapping(tmp_path: Path) -> None:
    prompts = tmp_path / "prompts.yaml"
    prompts.write_text("prompts:\n  packs: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"prompts\.packs must be a mapping"):
        load_pack_descriptions(prompts)


def test_render_pack_table_uses_shared_metadata_for_docs_links() -> None:
    output = render_pack_table(
        [("ot", "Core tools"), ("unknown", "Unknown pack")],
        include_docs=True,
    )

    assert output == "\n".join(
        [
            "| Pack | Extra | Description | Docs |",
            "|---|---|---|---|",
            "| `ot` | `core` | Core tools | [link](./ot_core.md) |",
            "| `unknown` | `-` | Unknown pack | - |",
        ]
    )

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ot.catalog import (
    ActivationCondition,
    InstallExtra,
    PackRequirement,
    RequirementKind,
    pack_by_name,
    skill_by_name,
)
from otdev.docsgen.generated_blocks import (
    generated_files,
    generated_targets,
    load_pack_descriptions,
    render_pack_requirements,
    render_pack_table,
    render_skill_catalog_block,
    render_skill_profiles,
    render_skill_workflow_resource,
    replace_block_text,
    replace_requirements_block_text,
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


def test_replace_requirements_block_text_migrates_authored_section() -> None:
    output = replace_requirements_block_text(
        "# Pack\n\n## Requires\n\nOld facts.\n\n## Examples\n",
        "## Runtime requirements\n\nGenerated facts.",
    )

    assert "## Requires" not in output
    assert "Old facts" not in output
    assert output.count("BEGIN GENERATED:PACK_REQUIREMENTS") == 1
    assert "## Runtime requirements\n\nGenerated facts." in output
    assert output.endswith("## Examples\n")


def test_replace_requirements_block_text_inserts_before_configuration() -> None:
    output = replace_requirements_block_text(
        "# Pack\n\n## Configuration\n",
        "## Runtime requirements\n\nGenerated facts.",
    )

    assert output.index("## Runtime requirements") < output.index("## Configuration")


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


def test_render_pack_requirements_discloses_safe_normalized_facts() -> None:
    entry = pack_by_name()["ot_image"]
    output = render_pack_requirements(
        entry,
        (
            PackRequirement(
                kind=RequirementKind.LIB,
                name="Pillow",
                import_name="PIL",
                install_extra=InstallExtra.CORE,
                purpose="Load images",
            ),
            PackRequirement(
                kind=RequirementKind.SECRET,
                name="OPENAI_API_KEY",
                purpose="Authenticate requests | safely",
                optional=True,
                activation=ActivationCondition(field="model", equals=True),
            ),
        ),
    )

    assert "Pack distribution: OneTool `core`." in output
    assert "`Pillow` (import `PIL`, OneTool `core`)" in output
    assert "`OPENAI_API_KEY`" in output
    assert "Authenticate requests \\| safely" in output
    assert "Conditional: `model` is enabled" in output
    assert "ot.help(query='<pack>', topic='setup')" in output


def test_render_skill_catalog_block_is_stable_and_catalog_owned() -> None:
    entry = skill_by_name()["ot-file"]

    first = render_skill_catalog_block(entry)
    second = render_skill_catalog_block(entry)

    assert first == second
    assert "| `file` | `[util]` |" in first
    assert "| `ripgrep` | `[dev]` |" in first
    assert "ot-setup" in first
    assert "ot-mcp-proxy" in first


def test_render_router_catalog_block_reaches_every_other_skill() -> None:
    router = render_skill_catalog_block(skill_by_name()["ot-ask"])

    for name in skill_by_name():
        if name != "ot-ask":
            assert f"| `{name}` |" in router


def test_generated_targets_are_stable_and_named() -> None:
    first = generated_targets()
    second = generated_targets()

    assert first == second
    assert len({(path, marker) for path, marker, _block in first}) == len(first)
    assert {
        "PACK_SUMMARY",
        "WB_HELP_SUMMARY",
        "SKILL_INSTALLATION_PROFILES",
        "CATALOG_COVERAGE",
        "PACK_REQUIREMENTS",
    } == {marker for _path, marker, _block in first}


def test_generated_workflow_resources_preserve_authored_sections() -> None:
    entry = skill_by_name()["ot-whiteboard"]
    output = render_skill_workflow_resource(entry)

    assert "## Capability boundary" in output
    assert "## Workflow" in output
    assert "## Safety and side effects" in output
    assert "## Verification and recovery" in output
    assert "BEGIN GENERATED:CATALOG_COVERAGE" not in output
    assert generated_files() == generated_files()


def test_render_skill_profiles_uses_derived_membership_and_current_cli() -> None:
    output = render_skill_profiles()

    assert "**Foundation**" in output
    assert "--skill ot-ref" in output
    assert "--skill ot-setup" in output
    assert "npx skills@latest add" in output
    assert "not native installer profile names" in output

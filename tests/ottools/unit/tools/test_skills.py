"""Unit tests for ot.skills() (bundled skill content API)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def fake_skills_dir(tmp_path: Path):
    """Create a temporary skills directory with test skills."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    (skills_dir / "my-skill.md").write_text(
        "---\nname: my-skill\ndescription: A test skill\ntags: [test]\n---\n\n# My Skill\n\nBody content here."
    )
    (skills_dir / "other-skill.md").write_text(
        "---\nname: other-skill\ndescription: Another skill\n---\n\nOther body."
    )
    return skills_dir


def _patch_skills_dir(fake_dir: Path):
    """Context manager to patch the skills directory."""
    return patch("ottools.skills._get_skills_dir", return_value=fake_dir)


# =============================================================================
# Parse Frontmatter Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_parse_frontmatter_basic() -> None:
    """Frontmatter is parsed and body is returned separately."""
    from ottools.skills import _parse_frontmatter

    content = "---\nname: test\ndescription: A test\n---\n\nBody content."
    fm, body = _parse_frontmatter(content)

    assert fm["name"] == "test"
    assert fm["description"] == "A test"
    assert body == "Body content."


@pytest.mark.unit
@pytest.mark.tools
def test_parse_frontmatter_no_frontmatter() -> None:
    """Content without --- markers returns empty dict and original content."""
    from ottools.skills import _parse_frontmatter

    content = "Just plain content."
    fm, body = _parse_frontmatter(content)

    assert fm == {}
    assert body == "Just plain content."


@pytest.mark.unit
@pytest.mark.tools
def test_parse_frontmatter_body_stripped() -> None:
    """Body text is stripped of leading/trailing whitespace."""
    from ottools.skills import _parse_frontmatter

    content = "---\nname: test\n---\n\n\n  Body with whitespace.  \n"
    _, body = _parse_frontmatter(content)

    assert body.strip() == "Body with whitespace."


@pytest.mark.unit
@pytest.mark.tools
def test_parse_frontmatter_warning_includes_path_context(tmp_path: Path) -> None:
    """Malformed frontmatter warnings include stable structured fields."""
    from ottools.skills import _parse_frontmatter

    source_path = tmp_path / "bad-skill.md"

    with patch("loguru.logger.warning") as mock_warning:
        fm, body = _parse_frontmatter(
            "---\nname: [unterminated\n---\n\nBody.",
            source_path=source_path,
        )

    assert fm == {}
    assert body == "Body."
    entry = mock_warning.call_args.args[0]
    assert entry.fields["event"] == "skills.frontmatter.malformed"
    assert entry.fields["path"] == source_path
    assert entry.fields["errorType"]


# =============================================================================
# skills() Listing Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_skills_list_all(fake_skills_dir: Path) -> None:
    """skills() with no args lists all skills."""
    from ottools.skills import skills

    with _patch_skills_dir(fake_skills_dir):
        result = skills()

    assert "my-skill" in result
    assert "other-skill" in result


@pytest.mark.unit
@pytest.mark.tools
def test_skills_list_includes_description(fake_skills_dir: Path) -> None:
    """skills() default (info=default) includes description."""
    from ottools.skills import skills

    with _patch_skills_dir(fake_skills_dir):
        result = skills()

    assert "A test skill" in result


@pytest.mark.unit
@pytest.mark.tools
def test_skills_filter_by_pattern(fake_skills_dir: Path) -> None:
    """skills(pattern=...) returns only matching skills."""
    from ottools.skills import skills

    with _patch_skills_dir(fake_skills_dir):
        result = skills(pattern="my")

    assert "my-skill" in result
    assert "other-skill" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_skills_pattern_no_match(fake_skills_dir: Path) -> None:
    """skills(pattern=...) with no match returns appropriate message."""
    from ottools.skills import skills

    with _patch_skills_dir(fake_skills_dir):
        result = skills(pattern="nonexistent-xyz")

    assert "No skills matched" in result or "nonexistent-xyz" in result


@pytest.mark.unit
@pytest.mark.tools
def test_skills_info_list(fake_skills_dir: Path) -> None:
    """skills(info='min') returns names only."""
    from ottools.skills import skills

    with _patch_skills_dir(fake_skills_dir):
        result = skills(info="min")

    assert "my-skill" in result
    # Description should NOT be in list-only output
    assert "A test skill" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_skills_info_full(fake_skills_dir: Path) -> None:
    """skills(info='full') includes tags and path."""
    from ottools.skills import skills

    with _patch_skills_dir(fake_skills_dir):
        result = skills(info="full")

    assert "my-skill" in result
    assert "test" in result  # tag
    assert "path" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
def test_skills_rejects_list_info(fake_skills_dir: Path) -> None:
    """skills(info='list') is invalid after info-level standardization."""
    from ottools.skills import skills

    with _patch_skills_dir(fake_skills_dir):
        with pytest.raises(ValueError, match="info='list' is not valid"):
            skills(info="list")


# =============================================================================
# skills(name=...) Retrieval Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_skills_retrieve_by_name(fake_skills_dir: Path) -> None:
    """skills(name=...) returns body content without frontmatter."""
    from ottools.skills import skills

    with _patch_skills_dir(fake_skills_dir):
        result = skills(name="my-skill")

    assert "# My Skill" in result
    assert "Body content here." in result
    # Frontmatter should NOT be in result
    assert "---" not in result
    assert "name: my-skill" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_skills_retrieve_unknown_name(fake_skills_dir: Path) -> None:
    """skills(name=...) with unknown name returns error with available names."""
    from ottools.skills import skills

    with _patch_skills_dir(fake_skills_dir):
        result = skills(name="does-not-exist")

    assert "Error" in result or "Unknown" in result
    assert "my-skill" in result  # lists available skills


# =============================================================================
# Bundled Skills Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_bundled_skills_exist() -> None:
    """Bundled skills directory contains the expected skill files."""
    from ot.paths import get_global_templates_dir

    skills_dir = get_global_templates_dir() / "skills"
    assert skills_dir.exists(), "skills/ directory must exist in global_templates"

    expected = {"ot-ref"}
    found = {f.stem for f in skills_dir.glob("*.md")}
    assert expected.issubset(found), f"Missing bundled skills: {expected - found}"


@pytest.mark.unit
@pytest.mark.tools
def test_bundled_skills_have_frontmatter() -> None:
    """Each bundled skill has valid YAML frontmatter with name and description."""
    from ot.paths import get_global_templates_dir
    from ottools.skills import _parse_frontmatter

    skills_dir = get_global_templates_dir() / "skills"
    for skill_file in skills_dir.glob("*.md"):
        content = skill_file.read_text()
        fm, body = _parse_frontmatter(content)
        assert "name" in fm, f"{skill_file.name} missing 'name' in frontmatter"
        assert "description" in fm, f"{skill_file.name} missing 'description' in frontmatter"
        assert body.strip(), f"{skill_file.name} has empty body"


@pytest.mark.unit
@pytest.mark.tools
def test_ot_ref_frontmatter_triggers_direct_run_requests() -> None:
    """ot-ref frontmatter includes direct OneTool run trigger terms."""
    from ot.paths import get_global_templates_dir
    from ottools.skills import _parse_frontmatter

    content = (get_global_templates_dir() / "skills" / "ot-ref.md").read_text()
    fm, body = _parse_frontmatter(content)
    description = fm["description"]

    assert "__onetool" in description
    assert "MCP run" in description
    assert "direct pack calls" in description
    assert "run-vs-local-script" in description
    assert "OneTool `__onetool`/MCP run request" in body

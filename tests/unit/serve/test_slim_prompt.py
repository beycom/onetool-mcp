"""Tests for MCP server instructions prompt."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.serve
def test_instructions_is_short() -> None:
    """instructions prompt template is at most 50 lines (before pack_summary substitution)."""
    from ot.prompts import load_prompts

    prompts = load_prompts()
    assert len(prompts.instructions.strip().splitlines()) <= 50


@pytest.mark.unit
@pytest.mark.serve
def test_instructions_has_required_elements() -> None:
    """instructions contains invocation, reference, security, and boundary guidance."""
    from ot.prompts import load_prompts

    prompts = load_prompts()
    text = prompts.instructions

    assert "run(command=" in text, "Missing MCP run preference in instructions"
    assert "ot.security()" in text, "Missing security check pointer"
    assert "external-content" in text or "boundary" in text.lower(), (
        "Missing external content boundary warning in instructions"
    )


@pytest.mark.unit
@pytest.mark.serve
def test_run_description_has_invocation_contract() -> None:
    """run tool description carries the critical invocation contract."""
    from ot.prompts import load_prompts

    prompts = load_prompts()
    desc = prompts.tools["run"].description or ""

    assert "__onetool" in desc
    assert "__ot" in desc
    assert "__run" not in desc
    assert ":name key=value" in desc
    # Colon rule is stated exactly once, with a right/wrong pair (p21 §A).
    assert "The `:` prefix belongs to snippets only" in desc
    assert "Call shape: `pack.tool(arg=value)`, not `ot.pack.tool(...)`." in desc
    assert "Do not guess tool names, parameter names, or allowed values." in desc
    assert "Mode by shape:" in desc
    assert "Two request forms" in desc
    assert "run(command=" in desc
    # No reference to the removed ot.skills surface (p11/p21).
    assert "ot.skills" not in desc


@pytest.mark.unit
@pytest.mark.serve
def test_run_description_documents_shape_based_modes() -> None:
    """run description distinguishes code, snippet, and natural-language modes by shape."""
    from ot.prompts import load_prompts

    prompts = load_prompts()
    desc = prompts.tools["run"].description or ""

    assert "Mode by shape:" in desc
    assert "Fenced/backticked content" in desc
    assert "literal Python code" in desc
    assert "Valid unfenced Python is also code" in desc
    assert ":name key=value" in desc
    assert "not Python" in desc
    assert "plain strings" in desc
    assert "natural-language intent" in desc
    # Forgiveness line covers kwarg prefixes + pack aliases + proxy-name case (p21 §A).
    assert "short kwarg prefixes resolve" in desc
    assert "Packs have short aliases" in desc
    assert "keyword args for keyword-only tools" in desc
    assert "Do not send obvious syntax failures" in desc


@pytest.mark.unit
@pytest.mark.serve
def test_run_description_avoids_old_unscoped_pass_through_rule() -> None:
    """run description does not use broad pass-through wording for all input."""
    from ot.prompts import load_prompts

    prompts = load_prompts()
    desc = prompts.tools["run"].description or ""

    assert "Pass code EXACTLY as-is" not in desc
    assert "JUST pass the exact command string" not in desc


@pytest.mark.unit
@pytest.mark.serve
def test_instructions_stay_concise_and_defer_contract() -> None:
    """Server instructions stay short and defer full invocation details to run."""
    from ot.prompts import load_prompts

    prompts = load_prompts()
    text = prompts.instructions

    assert len(text.strip().splitlines()) <= 50
    assert "Follow the `run` tool description first" in text
    assert "The `run` tool description is authoritative" in text
    assert "Mode by shape" not in text
    assert "natural-language intent" not in text
    assert "Large results may return handle dicts" not in text


@pytest.mark.unit
@pytest.mark.serve
def test_ot_ref_skill_carries_pack_map_and_index_pointer() -> None:
    """ot-ref SKILL.md (p21 §B) carries the pack map, forgiveness, and index pointer."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    text = (root / "skills" / "ot-ref" / "SKILL.md").read_text()

    assert "## Pack map" in text
    assert "<!-- packmap:begin" in text and "<!-- packmap:end -->" in text
    assert "reference/tool-index.md" in text
    assert "### Forgiveness boundaries" in text
    assert "Kwarg prefixes" in text
    assert "ambiguous or colliding prefix errors" in text
    assert "info='signatures'" in text
    assert "ot.skills" not in text

    # Deep-dive recovery content lives in reference/recovery.md, not the body.
    recovery = (root / "skills" / "ot-ref" / "reference" / "recovery.md").read_text()
    assert "Fast recovery" in recovery
    assert "Param prefixes" in recovery
    assert "__format__ = 'yml_h'; ot.help(query='search')" in recovery


@pytest.mark.unit
@pytest.mark.serve
def test_prompts_config_no_slim_fields() -> None:
    """PromptsConfig no longer has slim or instructions_slim fields."""
    from ot.prompts import PromptsConfig

    config = PromptsConfig(instructions="Hello")
    assert not hasattr(config, "slim")
    assert not hasattr(config, "instructions_slim")


@pytest.mark.unit
@pytest.mark.serve
def test_servers_yaml_has_source_field() -> None:
    """servers.yaml template entries have 'source:' fields pointing to upstream repos."""
    from ot.paths import get_global_templates_dir

    servers_yaml = get_global_templates_dir() / "servers.yaml"
    content = servers_yaml.read_text()

    import yaml

    data = yaml.safe_load(content) or {}
    servers = data.get("servers", {})
    assert "chunkhound" not in servers

    for name, cfg in servers.items():
        if isinstance(cfg, dict):
            assert "source" in cfg, (
                f"Server '{name}' is missing source: field in servers.yaml"
            )


@pytest.mark.unit
@pytest.mark.serve
def test_run_examples_are_zero_config() -> None:
    """run examples avoid key-gated calls (p21 §A): status/help/ripgrep/snippet."""
    from ot.prompts import load_prompts

    prompts = load_prompts()
    examples = prompts.tools["run"].examples or []

    assert "ot.status()" in examples
    assert "ot.help(query='search')" in examples
    assert ":pkg_npm packages=react" in examples
    # No key-gated example (e.g. brave.search) in the runnable examples list.
    assert not any("brave.search" in ex for ex in examples)


@pytest.mark.unit
@pytest.mark.serve
def test_catalog_provides_localhist_default_without_prompt_duplication() -> None:
    """The typed catalog owns defaults; prompt packs remain user overrides."""
    from ot.catalog import pack_by_name
    from ot.prompts import load_prompts

    prompts = load_prompts()
    assert "localhist" in pack_by_name()
    assert prompts.packs == {}


@pytest.mark.unit
@pytest.mark.serve
def test_instructions_point_at_ot_ref_skill() -> None:
    """Connection instructions point at the ot-ref skill, not ot.skills (p21 §A)."""
    from ot.prompts import load_prompts

    prompts = load_prompts()
    assert "ot-ref" in prompts.instructions
    assert "ot.skills" not in prompts.instructions
    assert "{pack_summary}" not in prompts.instructions

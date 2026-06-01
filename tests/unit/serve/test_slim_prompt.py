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
    assert "ot.skills(name='ot-ref')" in text, "Missing optional ot-ref pointer"
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

    assert "__run" in desc
    assert "__r" in desc
    assert "__ot" in desc
    assert ":name" in desc
    assert "Call shape: `pack.tool(arg=value)`, not `ot.pack.tool(...)`." in desc
    assert "Do not guess tool names, parameter names, or allowed values." in desc
    assert "Mode by shape:" in desc
    assert "run(command=" in desc


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
    assert "OneTool resolves param prefixes" in desc
    assert "keyword-only tools" in desc
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
def test_ot_ref_contains_advanced_recovery_not_core_contract() -> None:
    """ot-ref carries advanced reference details without owning normal invocation."""
    from ot.paths import get_global_templates_dir

    text = (get_global_templates_dir() / "skills" / "ot-ref.md").read_text()

    assert "Close-call recovery" in text
    assert "Param prefixes" in text
    assert "first in signature/schema order wins" in text
    assert "__format__ = 'yml_h'; ot.help(query='topic')" in text
    assert "OneTool `__run`/MCP run request" in text
    assert "Natural language to code" not in text


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

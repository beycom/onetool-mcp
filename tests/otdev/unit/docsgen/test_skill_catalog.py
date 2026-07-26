from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ot.catalog import (
    PACK_CATALOG,
    SKILL_CATALOG,
    PackStability,
    ProfileRole,
    SkillRole,
)
from otdev.docsgen.registry_check import runtime_registry
from otdev.docsgen.skill_catalog import (
    _runtime_pack_sources,
    _validate_runtime_metadata,
    derive_profiles,
    validate_catalog,
)

pytestmark = [pytest.mark.unit, pytest.mark.tools]

ROOT = Path(__file__).resolve().parents[4]
RUNTIME_PACKS = {item.pack for item in PACK_CATALOG}


def _copy_catalog(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(ROOT / "skills", root / "skills")
    docs = root / "docs" / "reference" / "tools"
    docs.mkdir(parents=True)
    for source in (ROOT / "docs" / "reference" / "tools").glob("*.md"):
        shutil.copy2(source, docs)
    installation = root / "docs" / "learn" / "installation.md"
    installation.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "docs" / "learn" / "installation.md", installation)
    shutil.copy2(ROOT / "docs" / "llms.txt", root / "docs" / "llms.txt")
    shutil.copytree(
        ROOT / "src" / "ot" / "help_resources",
        root / "src" / "ot" / "help_resources",
    )
    return root


def test_catalog_matches_reviewed_contract() -> None:
    assert validate_catalog() == []


def test_profiles_are_derived_from_roles_and_pack_ownership() -> None:
    profiles = derive_profiles()

    assert {"ot-ref", "ot-ask", "ot-setup"} <= profiles["Foundation"]
    assert "ot-runtime" in profiles["Core"]
    assert profiles["Foundation"] <= profiles["Core"]
    assert profiles["Core"] <= profiles["Core + [util]"]
    assert profiles["Core"] <= profiles["Core + [dev]"]
    assert profiles["[all]"] == {entry.name for entry in SKILL_CATALOG}


def test_reviewed_special_ownership_and_beta_exclusion() -> None:
    packs = {entry.pack: entry for entry in PACK_CATALOG}

    assert packs["ripgrep"].skill_owner == "ot-file"
    assert packs["ot_timer"].skill_owner == "ot-ref"
    assert packs["ot_servers"].skill_owner == "ot-mcp-proxy"
    assert packs["console"].stability is PackStability.BETA
    assert packs["console"].skill_owner is None
    assert packs["console"].skill_exclusion_reason
    assert "pivot" not in packs["excel"].default_summary.lower()
    assert "security" not in packs["package"].default_summary.lower()
    assert "vulnerab" not in packs["package"].default_summary.lower()
    assert "template" not in packs["ot_forge"].default_summary.lower()


def test_proxy_and_runtime_skills_preserve_approved_boundaries() -> None:
    proxy = (ROOT / "skills" / "ot-mcp-proxy" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    runtime = (ROOT / "skills" / "ot-runtime" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "current authoritative MCP documentation" in proxy
    assert "no server-specific preset catalog" in proxy
    assert "Propose a disabled persistent entry" in proxy
    assert "ot.resources" in proxy
    assert "ot.prompts" in proxy
    assert "Root HTTP has no built-in authentication" in runtime
    assert "onetool direct run" in runtime
    assert "direct start" not in runtime
    assert "direct repl" not in runtime


def test_invocation_and_profile_roles_are_explicit() -> None:
    skills = {entry.name: entry for entry in SKILL_CATALOG}

    assert skills["ot-ask"].invocation.user_invocable
    assert not skills["ot-ask"].invocation.model_invocable
    for name in ("ot-setup", "ot-runtime", "ot-mcp-proxy"):
        assert skills[name].invocation.user_invocable
        assert skills[name].invocation.model_invocable
    assert skills["ot-setup"].profile_role is ProfileRole.FOUNDATION
    assert skills["ot-runtime"].profile_role is ProfileRole.CORE


def test_imported_and_subclassed_config_models_resolve() -> None:
    registry = runtime_registry()

    assert {
        "arch",
        "knowledge",
        "localhist",
        "mem",
        "ot_image",
    } <= set(registry.config_models)


def test_validation_rejects_duplicate_pack() -> None:
    failures = validate_catalog(
        runtime_packs=RUNTIME_PACKS,
        packs=(*PACK_CATALOG, PACK_CATALOG[0]),
    )

    assert "pack 'ot' has 2 catalog entries" in failures


def test_validation_rejects_missing_runtime_pack() -> None:
    failures = validate_catalog(runtime_packs=RUNTIME_PACKS - {"db"})

    assert "catalog contains unknown runtime pack 'db'" in failures


def test_validation_rejects_missing_beta_exclusion_reason() -> None:
    packs = tuple(
        entry.model_copy(update={"skill_exclusion_reason": None})
        if entry.pack == "console"
        else entry
        for entry in PACK_CATALOG
    )

    failures = validate_catalog(runtime_packs=RUNTIME_PACKS, packs=packs)

    assert "ownerless pack 'console' has no skill exclusion reason" in failures


def test_validation_rejects_missing_docs_page(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    (root / "docs" / "reference" / "tools" / "db.md").unlink()

    failures = validate_catalog(root=root, runtime_packs=RUNTIME_PACKS)

    assert "pack 'db' doc slug 'db' has no MkDocs page" in failures


def test_validation_rejects_ownerless_capability_skill() -> None:
    skills = tuple(
        entry.model_copy(update={"name": "ot-orphan", "role": SkillRole.CAPABILITY_OWNER})
        if entry.name == "ot-runtime"
        else entry
        for entry in SKILL_CATALOG
    )

    failures = validate_catalog(runtime_packs=RUNTIME_PACKS, skills=skills)

    assert "catalog skill 'ot-orphan' owns no pack" in failures


def test_validation_rejects_invocation_policy_mismatch(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    sidecar = root / "skills" / "ot-ask" / "agents" / "openai.yaml"
    sidecar.write_text("policy:\n  allow_implicit_invocation: true\n", encoding="utf-8")

    failures = validate_catalog(root=root, runtime_packs=RUNTIME_PACKS)

    assert "ot-ask: allow_implicit_invocation must be false" in failures


def test_validation_rejects_model_sidecar_disabling_implicit(
    tmp_path: Path,
) -> None:
    root = _copy_catalog(tmp_path)
    sidecar = root / "skills" / "ot-file" / "agents" / "openai.yaml"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(
        "policy:\n  allow_implicit_invocation: false\n", encoding="utf-8"
    )

    failures = validate_catalog(root=root, runtime_packs=RUNTIME_PACKS)

    assert "ot-file: allow_implicit_invocation must be true" in failures


def test_validation_rejects_incomplete_router(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    router = root / "skills" / "ot-ask" / "SKILL.md"
    router.write_text(
        router.read_text(encoding="utf-8").replace("`ot-runtime`", "`runtime guide`"),
        encoding="utf-8",
    )

    failures = validate_catalog(root=root, runtime_packs=RUNTIME_PACKS)

    assert "ot-ask omits catalog skill 'ot-runtime'" in failures


def test_validation_rejects_beta_pack_in_skill_index(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    index = root / "skills" / "ot-ref" / "reference" / "tool-index.md"
    index.write_text(
        index.read_text(encoding="utf-8") + "\n## console\n```python\n```\n",
        encoding="utf-8",
    )

    failures = validate_catalog(root=root, runtime_packs=RUNTIME_PACKS)

    assert "ot-ref tool index includes excluded beta pack 'console'" in failures


def test_validation_rejects_missing_config_hook(tmp_path: Path) -> None:
    source = tmp_path / "src" / "otutil" / "tools"
    source.mkdir(parents=True)
    (source / "brave.py").write_text(
        'pack = "brave"\n'
        "from pydantic import BaseModel\n"
        "class Config(BaseModel):\n"
        "    timeout: int = 30\n",
        encoding="utf-8",
    )

    failures = _validate_runtime_metadata(
        root=tmp_path,
        runtime_packs={"brave"},
        config_hooks=set(),
    )

    assert any(
        failure.startswith("configurable pack 'brave' has no valid config_model hook")
        for failure in failures
    )


def test_validation_rejects_runtime_doc_slug_drift() -> None:
    failures = _validate_runtime_metadata(
        root=ROOT,
        runtime_packs=RUNTIME_PACKS,
        config_hooks=set(runtime_registry().config_hooks),
        runtime_doc_slugs={"brave": "stale-brave-route"},
    )

    assert (
        "pack 'brave' runtime doc slug 'stale-brave-route' does not match "
        "catalog slug 'brave'"
    ) in failures


def test_validation_rejects_duplicate_runtime_pack_declarations(
    tmp_path: Path,
) -> None:
    for package in ("ottools", "otdev/tools"):
        source = tmp_path / "src" / package
        source.mkdir(parents=True)
        (source / "duplicate.py").write_text('pack = "duplicate"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="runtime pack 'duplicate' is declared by both"):
        _runtime_pack_sources(tmp_path)


def test_validation_rejects_missing_semantic_section(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    skill = root / "skills" / "ot-file" / "SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8").replace(
            "## Verification and recovery",
            "## Completion",
        ),
        encoding="utf-8",
    )

    failures = validate_catalog(root=root, runtime_packs=RUNTIME_PACKS)

    assert (
        "ot-file: missing semantic section '## Verification and recovery'"
        in failures
    )


def test_validation_rejects_stale_generated_skill_block(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    skill = root / "skills" / "ot-file" / "SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8").replace(
            "| `file` | `[util]` |",
            "| `file` | `core` |",
        ),
        encoding="utf-8",
    )

    failures = validate_catalog(root=root, runtime_packs=RUNTIME_PACKS)

    assert "ot-file: generated catalog coverage block is stale" in failures


def test_validation_rejects_duplicate_generated_markers(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    skill = root / "skills" / "ot-file" / "SKILL.md"
    body = skill.read_text(encoding="utf-8")
    generated = body[body.index("<!-- BEGIN GENERATED:CATALOG_COVERAGE -->") :]
    skill.write_text(f"{body}\n{generated}", encoding="utf-8")

    failures = validate_catalog(root=root, runtime_packs=RUNTIME_PACKS)

    assert (
        "ot-file: generated catalog coverage markers must appear exactly once"
        in failures
    )


def test_validation_rejects_skill_over_token_ceiling(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    skill = root / "skills" / "ot-file" / "SKILL.md"
    skill.write_text(
        skill.read_text(encoding="utf-8") + "\n" + ("x" * 40_000),
        encoding="utf-8",
    )

    failures = validate_catalog(root=root, runtime_packs=RUNTIME_PACKS)

    assert any(
        failure.startswith(
            "ot-file: body exceeds generous estimated 8000-token ceiling"
        )
        for failure in failures
    )


def test_validation_rejects_stale_generated_profile_block(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    source = ROOT / "docs" / "learn" / "installation.md"
    target = root / "docs" / "learn" / "installation.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            "--skill ot-ref",
            "--skill missing-reference",
            1,
        ),
        encoding="utf-8",
    )

    failures = validate_catalog(root=root, runtime_packs=RUNTIME_PACKS)

    assert "stale generated target 'docs/learn/installation.md'" in failures


def test_validation_rejects_stale_packaged_workflow(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    target = root / "src" / "ot" / "help_resources" / "workflows" / "ot-file.md"
    target.write_text("# stale\n", encoding="utf-8")

    failures = validate_catalog(root=root, runtime_packs=RUNTIME_PACKS)

    assert (
        "stale generated target "
        "'src/ot/help_resources/workflows/ot-file.md'"
    ) in failures

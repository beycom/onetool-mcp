from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from otdev.docsgen.metadata import CURATED_SKILLS, PACK_DOCS, PROFILE_SKILLS
from otdev.docsgen.skill_catalog import derive_profiles, validate_catalog

pytestmark = [pytest.mark.unit, pytest.mark.tools]

ROOT = Path(__file__).resolve().parents[4]
RUNTIME_PACKS = {item.pack for item in PACK_DOCS}


def _copy_catalog(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(ROOT / "skills", root / "skills")
    docs = root / "docs" / "reference" / "tools"
    docs.mkdir(parents=True)
    shutil.copy2(ROOT / "docs" / "reference" / "tools" / "tool-index.md", docs)
    return root


def test_catalog_matches_reviewed_contract() -> None:
    assert len(CURATED_SKILLS) == 20
    assert len(PACK_DOCS) == 28
    assert validate_catalog(runtime_packs=RUNTIME_PACKS) == []


def test_profiles_derive_to_exact_membership() -> None:
    derived = derive_profiles()

    assert derived == PROFILE_SKILLS
    assert {name: len(skills) for name, skills in derived.items()} == {
        "Foundation": 2,
        "Core": 8,
        "Core + [util]": 15,
        "Core + [dev]": 14,
        "[all]": 20,
    }


def test_pack_ownership_matches_acceptance_oracle() -> None:
    owners = {item.pack: item.skill_owner for item in PACK_DOCS}

    assert owners == {
        "ot": "ot-ref",
        "console": "ot-ref",
        "ot_timer": "ot-ref",
        "ripgrep": "ot-ref",
        "ot_context": "ot-context",
        "ot_forge": "ot-forge",
        "ot_image": "ot-image",
        "ot_llm": "ot-llm",
        "ot_secrets": "ot-secrets",
        "ot_servers": "ot-servers",
        "convert": "ot-convert",
        "excel": "ot-excel",
        "file": "ot-file",
        "knowledge": "ot-knowledge",
        "mem": "ot-mem",
        "whiteboard": "ot-whiteboard",
        "arch": "ot-arch",
        "db": "ot-db",
        "diagram": "ot-diagram",
        "localhist": "ot-localhist",
        "brave": "ot-research",
        "ground": "ot-research",
        "tavily": "ot-research",
        "webfetch": "ot-research",
        "context7": "ot-research",
        "package": "ot-research",
        "chrome_util": "ot-browser-guidance",
        "play_util": "ot-browser-guidance",
    }


def test_capability_skills_are_lean_and_advisory() -> None:
    capability_skills = set(CURATED_SKILLS) - {"ot-ref", "ot-ask"}

    for skill in capability_skills:
        text = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        normalized = " ".join(text.lower().split())
        assert 15 <= len(text.splitlines()) <= 40, skill
        assert "## Availability" in text, skill
        assert "__ot ot.packs(" in text, skill
        assert "stop" in normalized, skill
        assert "without a separate" in normalized and "request" in normalized, skill


def test_model_invoked_skills_use_default_codex_policy() -> None:
    model_invoked = set(CURATED_SKILLS) - {"ot-ask"}

    for skill in model_invoked:
        assert not (ROOT / "skills" / skill / "agents" / "openai.yaml").exists()
    assert (ROOT / "skills" / "ot-ask" / "agents" / "openai.yaml").exists()


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
        router.read_text(encoding="utf-8").replace("`ot-db`", "`database guide`"),
        encoding="utf-8",
    )

    failures = validate_catalog(root=root, runtime_packs=RUNTIME_PACKS)

    assert "ot-ask omits guidance owner 'ot-db'" in failures


def test_validation_rejects_missing_pack_from_central_index(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    for index in (
        root / "docs" / "reference" / "tools" / "tool-index.md",
        root / "skills" / "ot-ref" / "reference" / "tool-index.md",
    ):
        index.write_text(
            index.read_text(encoding="utf-8").replace("## db\n", "## removed\n"),
            encoding="utf-8",
        )

    failures = validate_catalog(root=root, runtime_packs=RUNTIME_PACKS)

    assert "ot-ref tool index omits mapped pack 'db'" in failures

"""Validate the curated OneTool skill catalog."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from otdev.docsgen.metadata import CURATED_SKILLS, PACK_DOCS, PROFILE_SKILLS
from otdev.docsgen.registry_check import runtime_tool_counts

ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = ROOT / "skills"

_SKILL_NAME = re.compile(r"^ot-[a-z0-9]+(?:-[a-z0-9]+)*$")
_ROUTER_SKILL = re.compile(r"\bot-[a-z0-9]+(?:-[a-z0-9]+)*\b")
_INDEX_PACK = re.compile(r"^## ([a-z][a-z0-9_]*)(?:,.*)?$", re.MULTILINE)


def _frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing YAML frontmatter")
    try:
        raw, body = text[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError("unterminated YAML frontmatter") from exc
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict):
        raise ValueError("frontmatter must be a mapping")
    return parsed, body


def derive_profiles() -> dict[str, frozenset[str]]:
    """Derive catalog profiles from pack extras and reviewed owners."""
    foundation = {"ot-ref", "ot-ask"}
    core_owners = {item.skill_owner for item in PACK_DOCS if item.extra == "core"}
    util_owners = {item.skill_owner for item in PACK_DOCS if item.extra == "[util]"}
    dev_owners = {item.skill_owner for item in PACK_DOCS if item.extra == "[dev]"}
    core = foundation | core_owners
    return {
        "Foundation": frozenset(foundation),
        "Core": frozenset(core),
        "Core + [util]": frozenset(core | util_owners),
        "Core + [dev]": frozenset(core | dev_owners),
        "[all]": frozenset(CURATED_SKILLS),
    }


def _validate_metadata(*, runtime_packs: set[str]) -> list[str]:
    failures: list[str] = []
    packs = [item.pack for item in PACK_DOCS]
    owners = [item.skill_owner for item in PACK_DOCS]

    for skill, count in Counter(CURATED_SKILLS).items():
        if count != 1:
            failures.append(f"catalog skill '{skill}' appears {count} times")
        if not _SKILL_NAME.fullmatch(skill):
            failures.append(f"catalog contains invalid skill name '{skill}'")
    for pack, count in Counter(packs).items():
        if count != 1:
            failures.append(f"pack '{pack}' has {count} metadata entries")
    for item in PACK_DOCS:
        if not item.skill_owner:
            failures.append(f"pack '{item.pack}' has no skill owner")
        elif item.skill_owner not in CURATED_SKILLS:
            failures.append(
                f"pack '{item.pack}' has unknown skill owner '{item.skill_owner}'"
            )
    for pack in sorted(set(packs) - runtime_packs):
        failures.append(f"metadata contains unknown runtime pack '{pack}'")
    for pack in sorted(runtime_packs - set(packs)):
        failures.append(f"runtime pack '{pack}' has no skill owner")

    mapped_owners = set(owners)
    capability_skills = set(CURATED_SKILLS) - {"ot-ask"}
    for skill in sorted(capability_skills - mapped_owners):
        failures.append(f"catalog skill '{skill}' owns no pack")

    derived = derive_profiles()
    for profile, expected in PROFILE_SKILLS.items():
        actual = derived.get(profile)
        if actual != expected:
            failures.append(
                f"profile '{profile}' mismatch: "
                f"expected={sorted(expected)} actual={sorted(actual or ())}"
            )
    return failures


def _validate_skill(skill: str, path: Path) -> tuple[list[str], str]:
    failures: list[str] = []
    try:
        frontmatter, body = _frontmatter(path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [f"{skill}: {exc}"], ""

    expected_keys = {"name", "description", "user-invocable"}
    if skill == "ot-ask":
        expected_keys.add("disable-model-invocation")
    if set(frontmatter) != expected_keys:
        failures.append(
            f"{skill}: frontmatter keys must be {sorted(expected_keys)}, "
            f"got {sorted(frontmatter)}"
        )
    if frontmatter.get("name") != skill:
        failures.append(f"{skill}: frontmatter name must match directory")
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        failures.append(f"{skill}: description must be a non-empty string")

    user_invocable = frontmatter.get("user-invocable")
    disable_model = frontmatter.get("disable-model-invocation")
    expected_user_invocable = skill == "ot-ask"
    if user_invocable is not expected_user_invocable:
        failures.append(
            f"{skill}: user-invocable must be {str(expected_user_invocable).lower()}"
        )
    if skill == "ot-ask" and disable_model is not True:
        failures.append(f"{skill}: disable-model-invocation must be true")
    if skill != "ot-ask" and "disable-model-invocation" in frontmatter:
        failures.append(f"{skill}: disable-model-invocation must be omitted")

    sidecar = path.parent / "agents" / "openai.yaml"
    if not sidecar.exists():
        if skill == "ot-ask":
            failures.append(f"{skill}: missing agents/openai.yaml")
    else:
        try:
            sidecar_data = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            failures.append(f"{skill}: invalid agents/openai.yaml: {exc}")
        else:
            if not isinstance(sidecar_data, dict):
                failures.append(f"{skill}: agents/openai.yaml must be a mapping")
                return failures, body
            policy = sidecar_data.get("policy", {})
            if not isinstance(policy, dict):
                failures.append(f"{skill}: agents/openai.yaml policy must be a mapping")
                return failures, body
            expected_implicit = skill != "ot-ask"
            actual_implicit = policy.get("allow_implicit_invocation", True)
            if actual_implicit is not expected_implicit:
                failures.append(
                    f"{skill}: allow_implicit_invocation must be "
                    f"{str(expected_implicit).lower()}"
                )
    return failures, body


def validate_catalog(
    *,
    root: Path = ROOT,
    runtime_packs: set[str] | None = None,
) -> list[str]:
    """Return deterministic catalog validation failures."""
    skills_root = root / "skills"
    failures = _validate_metadata(
        runtime_packs=(
            set(runtime_tool_counts()) if runtime_packs is None else runtime_packs
        )
    )

    directory_names = sorted(
        path.name for path in skills_root.iterdir() if path.is_dir()
    )
    invalid_names = sorted(
        name for name in directory_names if not _SKILL_NAME.fullmatch(name)
    )
    for name in invalid_names:
        failures.append(f"invalid skill directory name '{name}'")
    duplicates = sorted(
        name for name, count in Counter(directory_names).items() if count > 1
    )
    for name in duplicates:
        failures.append(f"duplicate skill directory '{name}'")

    actual_skills = set(directory_names)
    expected_skills = set(CURATED_SKILLS)
    for name in sorted(expected_skills - actual_skills):
        failures.append(f"missing catalog skill '{name}'")
    for name in sorted(actual_skills - expected_skills):
        failures.append(f"unknown catalog skill '{name}'")

    bodies: dict[str, str] = {}
    frontmatter_names: list[str] = []
    for skill in sorted(expected_skills & actual_skills):
        skill_path = skills_root / skill / "SKILL.md"
        skill_failures, body = _validate_skill(skill, skill_path)
        failures.extend(skill_failures)
        bodies[skill] = body
        try:
            frontmatter, _ = _frontmatter(skill_path)
        except (OSError, ValueError, yaml.YAMLError):
            continue
        if isinstance(frontmatter.get("name"), str):
            frontmatter_names.append(frontmatter["name"])
    for name, count in Counter(frontmatter_names).items():
        if count > 1:
            failures.append(f"duplicate frontmatter skill name '{name}'")

    router = bodies.get("ot-ask", "")
    owners = {item.skill_owner for item in PACK_DOCS}
    router_names = set(_ROUTER_SKILL.findall(router))
    for owner in sorted(owners - router_names):
        failures.append(f"ot-ask omits guidance owner '{owner}'")
    for name in sorted(router_names - expected_skills):
        failures.append(f"ot-ask names unknown skill '{name}'")

    docs_index = root / "docs" / "reference" / "tools" / "tool-index.md"
    skill_index = skills_root / "ot-ref" / "reference" / "tool-index.md"
    if not docs_index.exists():
        failures.append(f"missing {docs_index}")
    if not skill_index.exists():
        failures.append(f"missing {skill_index}")
    if docs_index.exists() and skill_index.exists():
        docs_text = docs_index.read_text(encoding="utf-8")
        skill_text = skill_index.read_text(encoding="utf-8")
        if docs_text != skill_text:
            failures.append("docs and ot-ref tool indexes differ")
        indexed_packs = set(_INDEX_PACK.findall(skill_text))
        for pack in sorted({item.pack for item in PACK_DOCS} - indexed_packs):
            failures.append(f"ot-ref tool index omits mapped pack '{pack}'")

    return failures


def main() -> int:
    """Run the curated skill catalog check."""
    failures = validate_catalog()
    if failures:
        print("skills check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("skills check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

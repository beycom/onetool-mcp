"""Validate the typed OneTool guidance and skill catalog."""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from ot.catalog import (
    PACK_CATALOG,
    SKILL_CATALOG,
    HelpTopicKind,
    PackGuidanceEntry,
    PackStability,
    ProfileRole,
    SkillCatalogEntry,
    SkillRole,
    derive_skill_profiles,
)
from otdev.docsgen.generated_blocks import (
    ROOT as GENERATED_ROOT,
)
from otdev.docsgen.generated_blocks import (
    generated_files,
    generated_targets,
    render_skill_catalog_block,
    replace_block_text,
)
from otdev.docsgen.registry_check import runtime_registry

if TYPE_CHECKING:
    from collections.abc import Sequence

ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = ROOT / "skills"

_SKILL_NAME = re.compile(r"^ot-[a-z0-9]+(?:-[a-z0-9]+)*$")
_ROUTER_SKILL = re.compile(r"\bot-[a-z0-9]+(?:-[a-z0-9]+)*\b")
_INDEX_PACK = re.compile(r"^## ([a-z][a-z0-9_]*)(?:,.*)?$", re.MULTILINE)
_CONFIG_SIGNAL = re.compile(
    r"(?:get_tool_config\s*\(|class\s+\w*Config\s*\(|Config\s+as\s+_Config)"
)
_MAX_SKILL_TOKENS = 8_000
_SEMANTIC_HEADINGS = (
    "## Capability boundary",
    "## Workflow",
    "## Safety and side effects",
    "## Verification and recovery",
)
_GENERATED_COVERAGE_MARKER = "<!-- BEGIN GENERATED:CATALOG_COVERAGE -->"
_GENERATED_COVERAGE_END = "<!-- END GENERATED:CATALOG_COVERAGE -->"


def _estimated_token_count(text: str) -> int:
    """Return a conservative dependency-free token estimate for Markdown."""

    return (len(text.encode("utf-8")) + 3) // 4


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


def _derive_profiles(
    *,
    packs: Sequence[PackGuidanceEntry],
    skills: Sequence[SkillCatalogEntry],
) -> dict[str, frozenset[str]]:
    foundation = {
        skill.name
        for skill in skills
        if skill.profile_role is ProfileRole.FOUNDATION
    }
    explicit_core = {
        skill.name for skill in skills if skill.profile_role is ProfileRole.CORE
    }
    core_owners = {
        pack.skill_owner
        for pack in packs
        if pack.extra.value == "core" and pack.skill_owner is not None
    }
    util_owners = {
        pack.skill_owner
        for pack in packs
        if pack.extra.value == "[util]" and pack.skill_owner is not None
    }
    dev_owners = {
        pack.skill_owner
        for pack in packs
        if pack.extra.value == "[dev]" and pack.skill_owner is not None
    }
    core = foundation | explicit_core | core_owners
    skill_names = {skill.name for skill in skills}
    return {
        "Foundation": frozenset(foundation),
        "Core": frozenset(core),
        "Core + [util]": frozenset(core | util_owners),
        "Core + [dev]": frozenset(core | dev_owners),
        "[all]": frozenset(skill_names),
    }


def derive_profiles() -> dict[str, frozenset[str]]:
    """Derive public skill profiles from the runtime-safe catalog."""

    return derive_skill_profiles()


def _runtime_pack_sources(root: Path) -> dict[str, tuple[Path, str]]:
    """Return top-level built-in pack source text keyed by static pack name."""

    result: dict[str, tuple[Path, str]] = {}
    roots = (
        root / "src" / "ottools",
        root / "src" / "otutil" / "tools",
        root / "src" / "otdev" / "tools",
    )
    for source_root in roots:
        if not source_root.exists():
            continue
        for path in sorted(source_root.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(text, filename=str(path))
            except SyntaxError:
                continue
            pack: str | None = None
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                if not any(
                    isinstance(target, ast.Name) and target.id == "pack"
                    for target in node.targets
                ):
                    continue
                if isinstance(node.value, ast.Constant) and isinstance(
                    node.value.value, str
                ):
                    pack = node.value.value
                    break
            if pack is not None:
                if pack in result:
                    previous = result[pack][0]
                    raise ValueError(
                        f"runtime pack '{pack}' is declared by both {previous} and {path}"
                    )
                result[pack] = (path, text)
    return result


def _validate_runtime_metadata(
    *,
    root: Path,
    runtime_packs: set[str],
    config_hooks: set[str],
    runtime_doc_slugs: dict[str, str] | None = None,
) -> list[str]:
    failures: list[str] = []
    try:
        sources = _runtime_pack_sources(root)
    except ValueError as exc:
        return [str(exc)]

    for pack, (path, text) in sources.items():
        if pack not in runtime_packs:
            continue
        configurable = bool(_CONFIG_SIGNAL.search(text))
        if configurable and pack not in config_hooks:
            failures.append(
                f"configurable pack '{pack}' has no valid config_model hook ({path})"
            )

    for item in PACK_CATALOG:
        runtime_slug = (runtime_doc_slugs or {}).get(item.pack)
        if runtime_slug is not None and runtime_slug != item.doc_slug:
            failures.append(
                f"pack '{item.pack}' runtime doc slug '{runtime_slug}' does not "
                f"match catalog slug '{item.doc_slug}'"
            )
        for topic in item.topics:
            if topic.kind is HelpTopicKind.RESOURCE:
                package, separator, relative = topic.source.partition("/")
                resource = root / "src" / Path(package.replace(".", "/")) / relative
                if not separator or not resource.is_file():
                    failures.append(
                        f"pack '{item.pack}' topic '{topic.name}' has missing "
                        f"resource '{topic.source}'"
                    )
    return failures


def _validate_metadata(
    *,
    root: Path,
    runtime_packs: set[str],
    packs: Sequence[PackGuidanceEntry],
    skills: Sequence[SkillCatalogEntry],
) -> list[str]:
    failures: list[str] = []
    pack_names = [item.pack for item in packs]
    skill_names = [item.name for item in skills]
    skill_name_set = set(skill_names)

    for skill, count in Counter(skill_names).items():
        if count != 1:
            failures.append(f"catalog skill '{skill}' appears {count} times")
        if not _SKILL_NAME.fullmatch(skill):
            failures.append(f"catalog contains invalid skill name '{skill}'")
    for pack, count in Counter(pack_names).items():
        if count != 1:
            failures.append(f"pack '{pack}' has {count} catalog entries")

    for item in packs:
        if item.stability is PackStability.STABLE and not item.skill_owner:
            failures.append(f"stable pack '{item.pack}' has no skill owner")
        if item.skill_owner is None and not item.skill_exclusion_reason:
            failures.append(
                f"ownerless pack '{item.pack}' has no skill exclusion reason"
            )
        if item.skill_owner and item.skill_owner not in skill_name_set:
            failures.append(
                f"pack '{item.pack}' has unknown skill owner '{item.skill_owner}'"
            )
        topic_names = [topic.name for topic in item.topics]
        for topic, count in Counter(topic_names).items():
            if count != 1:
                failures.append(
                    f"pack '{item.pack}' help topic '{topic}' appears {count} times"
                )
        doc = root / "docs" / "reference" / "tools" / f"{item.doc_slug}.md"
        if not doc.exists():
            failures.append(
                f"pack '{item.pack}' doc slug '{item.doc_slug}' has no MkDocs page"
            )

    for pack in sorted(set(pack_names) - runtime_packs):
        failures.append(f"catalog contains unknown runtime pack '{pack}'")
    for pack in sorted(runtime_packs - set(pack_names)):
        failures.append(f"runtime pack '{pack}' has no catalog entry")

    owned_skills = {item.skill_owner for item in packs if item.skill_owner}
    ownerless_roles = {
        SkillRole.CATALOG_ROUTER,
        SkillRole.SETUP,
        SkillRole.RUNTIME_OPERATIONS,
    }
    for skill_entry in skills:
        if (
            skill_entry.name not in owned_skills
            and skill_entry.role not in ownerless_roles
        ):
            failures.append(f"catalog skill '{skill_entry.name}' owns no pack")

        expected_user = skill_entry.role in {
            SkillRole.CATALOG_ROUTER,
            SkillRole.SETUP,
            SkillRole.RUNTIME_OPERATIONS,
            SkillRole.PROXY_LIFECYCLE,
        }
        expected_model = skill_entry.role is not SkillRole.CATALOG_ROUTER
        if skill_entry.invocation.user_invocable is not expected_user:
            failures.append(
                f"{skill_entry.name}: catalog user invocation conflicts with role "
                f"'{skill_entry.role.value}'"
            )
        if skill_entry.invocation.model_invocable is not expected_model:
            failures.append(
                f"{skill_entry.name}: catalog model invocation conflicts with role "
                f"'{skill_entry.role.value}'"
            )

    profiles = _derive_profiles(packs=packs, skills=skills)
    if not profiles["Foundation"] <= profiles["Core"]:
        failures.append("Foundation profile is not contained in Core")
    if not profiles["Core"] <= profiles["Core + [util]"]:
        failures.append("Core profile is not contained in Core + [util]")
    if not profiles["Core"] <= profiles["Core + [dev]"]:
        failures.append("Core profile is not contained in Core + [dev]")
    if set(profiles["[all]"]) != skill_name_set:
        failures.append("[all] profile does not contain every catalog skill")
    return failures


def _validate_skill(
    entry: SkillCatalogEntry,
    path: Path,
) -> tuple[list[str], str]:
    failures: list[str] = []
    try:
        frontmatter, body = _frontmatter(path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [f"{entry.name}: {exc}"], ""

    expected_keys = {"name", "description", "user-invocable"}
    if not entry.invocation.model_invocable:
        expected_keys.add("disable-model-invocation")
    if set(frontmatter) != expected_keys:
        failures.append(
            f"{entry.name}: frontmatter keys must be {sorted(expected_keys)}, "
            f"got {sorted(frontmatter)}"
        )
    if frontmatter.get("name") != entry.name:
        failures.append(f"{entry.name}: frontmatter name must match directory")
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        failures.append(f"{entry.name}: description must be a non-empty string")

    if frontmatter.get("user-invocable") is not entry.invocation.user_invocable:
        failures.append(
            f"{entry.name}: user-invocable must be "
            f"{str(entry.invocation.user_invocable).lower()}"
        )
    disable_model = frontmatter.get("disable-model-invocation")
    if not entry.invocation.model_invocable and disable_model is not True:
        failures.append(
            f"{entry.name}: disable-model-invocation must be true"
        )
    if entry.invocation.model_invocable and "disable-model-invocation" in frontmatter:
        failures.append(
            f"{entry.name}: disable-model-invocation must be omitted"
        )

    sidecar = path.parent / "agents" / "openai.yaml"
    if not sidecar.exists():
        if not entry.invocation.model_invocable:
            failures.append(f"{entry.name}: missing agents/openai.yaml")
    else:
        try:
            sidecar_data = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            failures.append(f"{entry.name}: invalid agents/openai.yaml: {exc}")
        else:
            if not isinstance(sidecar_data, dict):
                failures.append(f"{entry.name}: agents/openai.yaml must be a mapping")
                return failures, body
            policy = sidecar_data.get("policy", {})
            if not isinstance(policy, dict):
                failures.append(
                    f"{entry.name}: agents/openai.yaml policy must be a mapping"
                )
                return failures, body
            actual_implicit = policy.get("allow_implicit_invocation", True)
            if actual_implicit is not entry.invocation.model_invocable:
                failures.append(
                    f"{entry.name}: allow_implicit_invocation must be "
                    f"{str(entry.invocation.model_invocable).lower()}"
                )
    token_count = _estimated_token_count(body)
    if token_count > _MAX_SKILL_TOKENS:
        failures.append(
            f"{entry.name}: body exceeds generous estimated "
            f"{_MAX_SKILL_TOKENS}-token ceiling ({token_count})"
        )
    for heading in _SEMANTIC_HEADINGS:
        if heading not in body:
            failures.append(f"{entry.name}: missing semantic section '{heading}'")
    if (
        body.count(_GENERATED_COVERAGE_MARKER) != 1
        or body.count(_GENERATED_COVERAGE_END) != 1
    ):
        failures.append(
            f"{entry.name}: generated catalog coverage markers must appear exactly once"
        )
    expected_block = "\n".join(
        (
            _GENERATED_COVERAGE_MARKER,
            render_skill_catalog_block(entry),
            _GENERATED_COVERAGE_END,
        )
    )
    if expected_block not in body:
        failures.append(f"{entry.name}: generated catalog coverage block is stale")
    return failures, body


def validate_catalog(
    *,
    root: Path = ROOT,
    runtime_packs: set[str] | None = None,
    packs: Sequence[PackGuidanceEntry] = PACK_CATALOG,
    skills: Sequence[SkillCatalogEntry] = SKILL_CATALOG,
) -> list[str]:
    """Return deterministic typed-catalog validation failures."""

    skills_root = root / "skills"
    loaded_registry = None
    if runtime_packs is None:
        loaded_registry = runtime_registry()
        resolved_runtime_packs = set(loaded_registry.packs)
    else:
        resolved_runtime_packs = runtime_packs

    failures = _validate_metadata(
        root=root,
        runtime_packs=resolved_runtime_packs,
        packs=packs,
        skills=skills,
    )
    if loaded_registry is not None:
        failures.extend(
            _validate_runtime_metadata(
                root=root,
                runtime_packs=resolved_runtime_packs,
                config_hooks=set(loaded_registry.config_hooks),
                runtime_doc_slugs=loaded_registry.doc_slugs,
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

    actual_skills = set(directory_names)
    expected_skills = {entry.name for entry in skills}
    for name in sorted(expected_skills - actual_skills):
        failures.append(f"missing catalog skill '{name}'")
    for name in sorted(actual_skills - expected_skills):
        failures.append(f"unknown catalog skill '{name}'")

    skill_entries = {entry.name: entry for entry in skills}
    bodies: dict[str, str] = {}
    frontmatter_names: list[str] = []
    for skill in sorted(expected_skills & actual_skills):
        skill_path = skills_root / skill / "SKILL.md"
        skill_failures, body = _validate_skill(skill_entries[skill], skill_path)
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
    router_names = set(_ROUTER_SKILL.findall(router))
    routable = expected_skills - {"ot-ask"}
    for skill in sorted(routable - router_names):
        failures.append(f"ot-ask omits catalog skill '{skill}'")
    for name in sorted(router_names - expected_skills):
        failures.append(f"ot-ask names unknown skill '{name}'")

    excluded_beta = {
        item.pack
        for item in packs
        if item.stability is PackStability.BETA and item.skill_owner is None
    }
    for skill, body in bodies.items():
        for pack in excluded_beta:
            if re.search(rf"\b{re.escape(pack)}\b", body, re.IGNORECASE):
                failures.append(
                    f"{skill}: excluded beta pack '{pack}' appears in skill content"
                )

    docs_index = root / "docs" / "reference" / "tools" / "tool-index.md"
    skill_index = skills_root / "ot-ref" / "reference" / "tool-index.md"
    if not docs_index.exists():
        failures.append(f"missing {docs_index}")
    if not skill_index.exists():
        failures.append(f"missing {skill_index}")
    if docs_index.exists():
        docs_packs = set(_INDEX_PACK.findall(docs_index.read_text(encoding="utf-8")))
        for pack in sorted({item.pack for item in packs} - docs_packs):
            failures.append(f"public tool index omits catalog pack '{pack}'")
    if skill_index.exists():
        skill_packs = set(_INDEX_PACK.findall(skill_index.read_text(encoding="utf-8")))
        stable_packs = {
            item.pack for item in packs if item.stability is PackStability.STABLE
        }
        for pack in sorted(stable_packs - skill_packs):
            failures.append(f"ot-ref tool index omits stable pack '{pack}'")
        for pack in sorted(excluded_beta & skill_packs):
            failures.append(f"ot-ref tool index includes excluded beta pack '{pack}'")

    for generated_path, marker, block in generated_targets():
        if marker == "CATALOG_COVERAGE":
            continue
        relative = generated_path.relative_to(GENERATED_ROOT)
        target = root / relative
        if not target.exists():
            failures.append(f"missing generated target '{relative}'")
            continue
        text = target.read_text(encoding="utf-8")
        if text != replace_block_text(text, marker, block):
            failures.append(f"stale generated target '{relative}'")
    for generated_path, expected in generated_files():
        relative = generated_path.relative_to(GENERATED_ROOT)
        target = root / relative
        if not target.exists():
            failures.append(f"missing generated target '{relative}'")
            continue
        if target.read_text(encoding="utf-8") != expected:
            failures.append(f"stale generated target '{relative}'")

    return failures


def main() -> int:
    """Run the typed skill catalog check."""

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

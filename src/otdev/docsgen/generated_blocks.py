"""Generate and replace managed documentation blocks."""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import cast

import yaml

from ot.catalog import (
    PACK_CATALOG,
    SKILL_CATALOG,
    PackGuidanceEntry,
    PackRequirement,
    PackStability,
    RequirementKind,
    SkillCatalogEntry,
    SkillRole,
    derive_skill_profiles,
)
from otdev.docsgen.metadata import DOC_PATH_BY_PACK, EXTRA_BY_PACK

ROOT = Path(__file__).resolve().parents[3]


def replace_block_text(text: str, marker_name: str, block: str) -> str:
    """Return text with a generated block replaced or appended."""
    begin = f"<!-- BEGIN GENERATED:{marker_name} -->"
    end = f"<!-- END GENERATED:{marker_name} -->"
    marker = re.compile(
        rf"{re.escape(begin)}[\s\S]*?{re.escape(end)}",
        re.MULTILINE,
    )
    replacement = f"{begin}\n{block}\n{end}"

    if marker.search(text):
        return marker.sub(replacement, text, count=1)
    return text.rstrip() + "\n\n" + replacement + "\n"


def replace_block(path: Path, marker_name: str, block: str) -> None:
    """Replace or append a generated block in a Markdown file."""
    text = path.read_text(encoding="utf-8")
    path.write_text(replace_block_text(text, marker_name, block), encoding="utf-8")


def replace_requirements_block_text(text: str, block: str) -> str:
    """Replace requirements markers or migrate one authored ``Requires`` section."""

    begin = "<!-- BEGIN GENERATED:PACK_REQUIREMENTS -->"
    if begin in text:
        return replace_block_text(text, "PACK_REQUIREMENTS", block)

    replacement = "\n".join(
        [
            begin,
            block,
            "<!-- END GENERATED:PACK_REQUIREMENTS -->",
        ]
    )
    authored_section = re.compile(
        r"^## Requires\s*\n[\s\S]*?(?=^## |\Z)",
        re.MULTILINE,
    )
    if authored_section.search(text):
        return authored_section.sub(replacement + "\n\n", text, count=1).rstrip() + "\n"

    insertion_heading = re.search(
        r"^## (?:Configuration|Examples)(?:\s|$)",
        text,
        re.MULTILINE,
    )
    if insertion_heading:
        offset = insertion_heading.start()
        return text[:offset].rstrip() + "\n\n" + replacement + "\n\n" + text[offset:]
    return text.rstrip() + "\n\n" + replacement + "\n"


def replace_requirements_block(path: Path, block: str) -> None:
    """Replace or migrate the generated runtime-requirements block."""

    text = path.read_text(encoding="utf-8")
    path.write_text(replace_requirements_block_text(text, block), encoding="utf-8")


def load_pack_descriptions(path: Path | None = None) -> list[tuple[str, str]]:
    """Return catalog defaults or explicit prompt-override descriptions."""
    if path is None:
        return [(entry.pack, entry.default_summary) for entry in PACK_CATALOG]

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    prompts = data.get("prompts") or {}
    packs = prompts.get("packs", {}) if isinstance(prompts, dict) else {}
    if not isinstance(packs, dict):
        raise ValueError("prompts.packs must be a mapping")

    out: list[tuple[str, str]] = []
    for name, desc in packs.items():
        if not isinstance(name, str):
            continue
        text = str(desc).strip().replace("\n", " ")
        text = re.sub(r"\s+", " ", text)
        out.append((name, text))
    return out


def render_pack_table(packs: list[tuple[str, str]], *, include_docs: bool) -> str:
    """Render the generated pack summary table."""
    lines = [
        "| Pack | Extra | Description" + (" | Docs |" if include_docs else " |"),
        "|---|---|---" + ("|---|" if include_docs else "|"),
    ]
    for name, desc in packs:
        extra = EXTRA_BY_PACK.get(name, "-")
        if include_docs and name in DOC_PATH_BY_PACK:
            doc = f"[link](./{DOC_PATH_BY_PACK[name]})"
            lines.append(f"| `{name}` | `{extra}` | {desc} | {doc} |")
        elif include_docs:
            lines.append(f"| `{name}` | `{extra}` | {desc} | - |")
        else:
            lines.append(f"| `{name}` | `{extra}` | {desc} |")
    return "\n".join(lines)


def render_whiteboard_help_table() -> str:
    """Render the generated whiteboard help table."""
    from otdev.tools import excalidraw as whiteboard

    lines = [
        "| Function | Summary |",
        "|---|---|",
    ]
    for name in whiteboard.__all__:
        fn = getattr(whiteboard, name)
        sig = inspect.signature(fn, eval_str=True)
        doc = (inspect.getdoc(fn) or "").splitlines()[0].strip()
        lines.append(f"| `whiteboard.{name}{sig}` | {doc} |")
    return "\n".join(lines)


def _runtime_pack_requirements() -> dict[str, tuple[PackRequirement, ...]]:
    """Read normalized requirements through the static runtime registry."""

    from ot.registry import ToolRegistry

    files = sorted(
        path
        for directory in (
            ROOT / "src" / "ottools",
            ROOT / "src" / "otutil" / "tools",
            ROOT / "src" / "otdev" / "tools",
        )
        for path in directory.glob("*.py")
        if path.name != "__init__.py"
    )
    registry = ToolRegistry()
    registry.scan_files(files)
    requirements = {
        pack: cast("tuple[PackRequirement, ...]", metadata["requirements"])
        for pack, metadata in registry.pack_metadata.items()
    }
    # The root ``ot`` control pack is assembled by the server rather than declared
    # by a scanned tool module. It has no external runtime requirements.
    requirements.setdefault("ot", ())
    missing = sorted(entry.pack for entry in PACK_CATALOG if entry.pack not in requirements)
    if missing:
        raise ValueError(
            "runtime requirement metadata missing for catalog packs: "
            + ", ".join(missing)
        )
    return requirements


def _requirement_availability(requirement: PackRequirement) -> str:
    """Render optionality and activation without exposing active config values."""

    activation = requirement.activation
    if activation is None:
        return "Optional" if requirement.optional else "Required"
    expected = activation.equals
    if expected is True:
        condition = f"`{activation.field}` is enabled"
    elif expected is False:
        condition = f"`{activation.field}` is disabled"
    else:
        condition = f"`{activation.field}` = `{expected}`"
    return f"Conditional: {condition}"


def _requirement_identity(requirement: PackRequirement) -> str:
    """Render the safe installation or configuration identity for a requirement."""

    if requirement.kind is RequirementKind.LIB:
        if requirement.install_extra is None:
            raise ValueError(
                f"library requirement {requirement.name!r} has no install extra"
            )
        return (
            f"`{requirement.name}` (import `{requirement.import_name}`, "
            f"OneTool `{requirement.install_extra.value}`)"
        )
    if requirement.kind is RequirementKind.CLI:
        name = requirement.name
        if requirement.authoritative_url:
            name = f"[{name}]({requirement.authoritative_url})"
        return f"{name} (executable `{requirement.executable}`)"
    return f"`{requirement.name}`"


def _markdown_cell(value: str) -> str:
    """Keep generated requirement values inside one Markdown table cell."""

    return value.replace("|", r"\|").replace("\n", " ")


def render_pack_requirements(
    entry: PackGuidanceEntry,
    requirements: tuple[PackRequirement, ...],
) -> str:
    """Render catalog and normalized runtime requirement facts for one pack."""

    lines = [
        "## Runtime requirements",
        "",
        f"Pack distribution: OneTool `{entry.extra.value}`.",
    ]
    if not requirements:
        lines.extend(["", "No additional runtime requirements are declared."])
        return "\n".join(lines)

    lines.extend(
        [
            "",
            "| Kind | Requirement | Purpose | Availability |",
            "|---|---|---|---|",
        ]
    )
    for requirement in requirements:
        lines.append(
            f"| `{requirement.kind.value}` | "
            f"{_markdown_cell(_requirement_identity(requirement))} | "
            f"{_markdown_cell(requirement.purpose)} | "
            f"{_markdown_cell(_requirement_availability(requirement))} |"
        )
    lines.extend(
        [
            "",
            "Use `ot.help(query='<pack>', topic='setup')` for current readiness "
            "and non-mutating setup guidance.",
        ]
    )
    return "\n".join(lines)


def render_skill_catalog_block(skill: SkillCatalogEntry) -> str:
    """Render compact catalog-owned coverage without duplicating authored prose."""

    owned = [
        pack
        for pack in PACK_CATALOG
        if pack.skill_owner == skill.name and pack.stability is PackStability.STABLE
    ]
    lines = [
        "## Catalog coverage",
        "",
        f"**Role:** `{skill.role.value}`",
    ]
    if skill.role is SkillRole.CATALOG_ROUTER:
        lines.extend(["", "| Skill | Role | Purpose |", "|---|---|---|"])
        for routed in SKILL_CATALOG:
            if routed.name == skill.name:
                continue
            lines.append(
                f"| `{routed.name}` | `{routed.role.value}` | {routed.purpose} |"
            )
    elif owned:
        lines.extend(["", "| Pack | Extra | Help topics | Docs |", "|---|---|---|---|"])
        for pack in owned:
            topics = ", ".join(f"`{topic.name}`" for topic in pack.topics)
            lines.append(
                f"| `{pack.pack}` | `{pack.extra.value}` | {topics} | "
                f"[reference](https://onetool.beycom.online/reference/tools/{pack.doc_slug}/) |"
            )
    else:
        lines.extend(
            [
                "",
                "This cross-catalog skill owns a workflow rather than a single pack.",
            ]
        )
    lines.extend(
        [
            "",
            "For a missing pack, dependency, secret, or config field, inspect "
            "`ot.help(query='<pack>', topic='setup')` and hand off to `ot-setup`. "
            "For outbound MCP server setup or lifecycle, hand off to `ot-mcp-proxy`.",
        ]
    )
    return "\n".join(lines)


def render_skill_profiles() -> str:
    """Render selectable recipes from derived catalog membership."""

    profiles = derive_skill_profiles()
    lines = [
        "| Recipe | Skills |",
        "|---|---|",
    ]
    for profile, members in profiles.items():
        skill_list = ", ".join(f"`{name}`" for name in sorted(members))
        lines.append(f"| **{profile}** | {skill_list} |")

    lines.extend(
        [
            "",
            "These are documentation recipes, not native installer profile names. "
            "Replace `<agent>` with a supported agent such as `codex` or "
            "`claude-code`.",
        ]
    )
    for profile, members in profiles.items():
        flags = " ".join(f"--skill {name}" for name in sorted(members))
        lines.extend(
            [
                "",
                f"**{profile}**",
                "",
                "```bash",
                "npx skills@latest add https://github.com/beycom/onetool-mcp "
                f"--agent <agent> {flags}",
                "```",
            ]
        )
    return "\n".join(lines)


def render_skill_workflow_resource(skill: SkillCatalogEntry) -> str:
    """Project authored operating guidance into an installed runtime resource."""

    source = ROOT / "skills" / skill.name / "SKILL.md"
    text = source.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{source}: missing frontmatter")
    try:
        _frontmatter, body = text[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError(f"{source}: unterminated frontmatter") from exc
    authored = body.partition("<!-- BEGIN GENERATED:CATALOG_COVERAGE -->")[0].strip()
    return "\n".join(
        [
            f"<!-- Generated from skills/{skill.name}/SKILL.md; do not edit. -->",
            authored,
            "",
        ]
    )


def generated_files() -> tuple[tuple[Path, str], ...]:
    """Return complete generated files and their in-memory rendering."""

    return tuple(
        (
            ROOT / "src" / "ot" / "help_resources" / "workflows" / f"{skill.name}.md",
            render_skill_workflow_resource(skill),
        )
        for skill in SKILL_CATALOG
    )


def generated_targets() -> tuple[tuple[Path, str, str], ...]:
    """Return every managed-block target and its in-memory rendering."""

    packs = load_pack_descriptions()
    targets: list[tuple[Path, str, str]] = [
        (
            ROOT / "docs" / "llms.txt",
            "PACK_SUMMARY",
            render_pack_table(packs, include_docs=False),
        ),
        (
            ROOT / "docs" / "reference" / "tools" / "whiteboard.md",
            "WB_HELP_SUMMARY",
            render_whiteboard_help_table(),
        ),
        (
            ROOT / "docs" / "learn" / "installation.md",
            "SKILL_INSTALLATION_PROFILES",
            render_skill_profiles(),
        ),
    ]
    for skill in SKILL_CATALOG:
        targets.append(
            (
                ROOT / "skills" / skill.name / "SKILL.md",
                "CATALOG_COVERAGE",
                render_skill_catalog_block(skill),
            )
        )
    requirements_by_pack = _runtime_pack_requirements()
    for entry in PACK_CATALOG:
        targets.append(
            (
                ROOT / "docs" / "reference" / "tools" / f"{entry.doc_slug}.md",
                "PACK_REQUIREMENTS",
                render_pack_requirements(
                    entry,
                    requirements_by_pack.get(entry.pack, ()),
                ),
            )
        )
    return tuple(targets)


def sync_all() -> None:
    """Synchronize all generated documentation blocks."""

    for path, marker, block in generated_targets():
        if marker == "PACK_REQUIREMENTS":
            replace_requirements_block(path, block)
        else:
            replace_block(path, marker, block)
    for path, content in generated_files():
        path.write_text(content, encoding="utf-8")


def main() -> int:
    """Synchronize generated documentation blocks."""
    sync_all()
    print("synced generated docs blocks")
    return 0

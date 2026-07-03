"""Skill content retrieval for OneTool.

Lists and retrieves bundled skill content from global_templates/skills/.
Skills are Markdown files with YAML frontmatter.

Example:
    skills()                          # list all skills
    skills(pattern="devtools")        # filter by name substring
    skills(name="ot-chrome-devtools-mcp")  # retrieve skill body
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ot.logging import LogEntry
from otpack import LogSpan, cache

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["skills"]
_VALID_INFO_LEVELS = {"min", "default", "full"}


def _get_skills_dir() -> Path:
    """Get the bundled skills directory."""
    from ot.paths import get_global_templates_dir

    return get_global_templates_dir() / "skills"


def _parse_frontmatter(
    content: str,
    *,
    source_path: Path | None = None,
) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from Markdown content.

    Args:
        content: Full file content with optional --- frontmatter ---
        source_path: Optional source path for structured warning context.

    Returns:
        (frontmatter_dict, body_text) where body has leading whitespace stripped
    """
    import yaml

    if not content.startswith("---"):
        return {}, content

    end = content.find("\n---", 3)
    if end == -1:
        return {}, content

    fm_text = content[3:end].strip()
    body = content[end + 4:].strip()

    try:
        fm: dict[str, Any] = yaml.safe_load(fm_text) or {}
    except Exception as e:
        from loguru import logger

        logger.warning(
            LogEntry(
                event="skills.frontmatter.malformed",
                path=source_path,
                errorType=type(e).__name__,
                error=str(e),
            )
        )
        fm = {}

    return fm, body


@cache.memoize(ttl=3600)
def _load_skill_index() -> dict[str, tuple[dict[str, Any], str]]:
    """Load and parse all bundled skills. Cached for 1 hour.

    Returns:
        Mapping of skill name → (frontmatter dict, body text)
    """
    skills_dir = _get_skills_dir()
    if not skills_dir.exists():
        return {}
    result: dict[str, tuple[dict[str, Any], str]] = {}
    for skill_file in sorted(skills_dir.glob("*.md")):
        if skill_file.name.startswith("_"):
            continue
        content = skill_file.read_text(encoding="utf-8")
        fm, body = _parse_frontmatter(content, source_path=skill_file)
        result[skill_file.stem] = (fm, body)
    return result


def skills(
    name: str | None = None,
    pattern: str | None = None,
    info: str = "default",
) -> str:
    """List available skills or retrieve a skill's body content.

    Lists bundled skills from global_templates/skills/.

    Args:
        name: Skill name to retrieve body for (e.g., "ot-guide")
        pattern: Filter skills by substring match on name
        info: Detail level — "min" (names only), "default" (+ description), "full" (everything)

    Returns:
        Skill body if name= provided; formatted list of skills otherwise

    Example:
        skills()                                  # list all
        skills(pattern="ot-")                     # filter by pattern
        skills(name="ot-chrome-devtools-mcp")     # retrieve body
        skills(info="full")                       # full info for each skill
    """
    with LogSpan(span="skills.list") as s:
        if info not in _VALID_INFO_LEVELS:
            raise ValueError(f"info={info!r} is not valid. Use 'min', 'default', or 'full'.")

        index: dict[str, tuple[dict[str, Any], str]] = {**_load_skill_index()}

        if name is not None:
            # Retrieve body of a specific skill
            if name not in index:
                available = ", ".join(sorted(index)) or "(none)"
                s.add(error="unknown_skill", name=name)
                return f"Error: Unknown skill '{name}'. Available skills: {available}"
            _, body = index[name]
            s.add(skill=name)
            return body

        # List skills
        if not index:
            return "No skills found."

        results: list[str] = []
        skills_dir = _get_skills_dir()
        for stem, (fm, _) in index.items():
            if pattern and pattern.lower() not in stem.lower():
                continue
            description = fm.get("description", "")
            source = fm.get("source", "bundled")
            if info == "min":
                results.append(stem)
            elif info == "full":
                tags = fm.get("tags", [])
                tags_str = f"  tags: {tags}" if tags else ""
                source_str = (
                    "  source: user-defined"
                    if source == "user"
                    else f"  path: {skills_dir / f'{stem}.md'}"
                )
                results.append(f"- {stem}: {description}{tags_str}\n{source_str}")
            else:  # "default"
                results.append(f"- {stem}: {description}")

        if not results:
            return f"No skills matched pattern: '{pattern}'"

        return "\n".join(results)

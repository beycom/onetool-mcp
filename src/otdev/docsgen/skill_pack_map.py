"""Generate the ot-ref SKILL.md pack-map block from the runtime registry.

Ported from the old ``_build_pack_summary()`` (formerly ``src/ot/server.py``),
extended to include each pack's short aliases from the registry. Rewrites the
block between the ``<!-- packmap:begin ... -->`` / ``<!-- packmap:end -->``
markers in ``skills/ot-ref/SKILL.md``; never hand-edit that block.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL_MD = ROOT / "skills" / "ot-ref" / "SKILL.md"

_BEGIN = "<!-- packmap:begin"
_END = "<!-- packmap:end -->"


def build_pack_map() -> str:
    """Render the pack map as ``- **pack** (alias) — description`` lines."""
    from ot.executor.tool_loader import load_tool_registry
    from ot.meta._discovery import packs as _packs

    registry = load_tool_registry()
    aliases = getattr(registry, "pack_aliases", {})

    lines: list[str] = []
    for pack in _packs(info="default"):
        if not isinstance(pack, dict):
            continue
        name = str(pack.get("name", ""))
        desc = str(pack.get("description", "") or "")
        alias_tuple = tuple(aliases.get(name, ()) or ())
        alias_str = f" ({', '.join(alias_tuple)})" if alias_tuple else ""
        if desc and desc != "(no description)":
            lines.append(f"- **{name}**{alias_str} — {desc}")
        else:
            lines.append(f"- **{name}**{alias_str}")
    return "\n".join(lines)


def rewrite_skill(path: Path = SKILL_MD) -> None:
    """Replace the packmap block in ``path`` with a freshly generated pack map."""
    text = path.read_text(encoding="utf-8")
    marker = re.compile(
        rf"({re.escape(_BEGIN)}[^\n]*-->)\n[\s\S]*?\n({re.escape(_END)})"
    )
    if not marker.search(text):
        raise ValueError(f"packmap markers not found in {path}")
    block = build_pack_map()
    path.write_text(
        marker.sub(lambda m: f"{m.group(1)}\n{block}\n{m.group(2)}", text),
        encoding="utf-8",
    )


def main() -> int:
    """Load config and rewrite the SKILL.md pack-map block."""
    from loguru import logger

    from ot.config.loader import get_config

    from .tool_index import default_config

    logger.remove()
    get_config(default_config(), reload=True)
    rewrite_skill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

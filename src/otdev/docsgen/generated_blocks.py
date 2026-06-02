"""Generate and replace managed documentation blocks."""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from otdev.docsgen.metadata import DOC_PATH_BY_PACK, EXTRA_BY_PACK

ROOT = Path(__file__).resolve().parents[3]
PROMPTS = ROOT / "src" / "ot" / "config" / "global_templates" / "prompts.yaml"


@dataclass(frozen=True)
class BlockTarget:
    """Generated documentation block target."""

    path: Path
    include_docs: bool = False


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


def load_pack_descriptions(path: Path = PROMPTS) -> list[tuple[str, str]]:
    """Load pack descriptions from the prompt template metadata."""
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


def sync_all() -> None:
    """Synchronize all generated documentation blocks."""
    packs = load_pack_descriptions()

    replace_block(
        ROOT / "docs" / "llms.txt",
        "PACK_SUMMARY",
        render_pack_table(packs, include_docs=False),
    )
    replace_block(
        ROOT / "docs" / "reference" / "tools" / "whiteboard.md",
        "WB_HELP_SUMMARY",
        render_whiteboard_help_table(),
    )


def main() -> int:
    """Synchronize generated documentation blocks."""
    sync_all()
    print("synced generated docs blocks")
    return 0

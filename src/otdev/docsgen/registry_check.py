"""Validate generated tool docs against the runtime registry."""

from __future__ import annotations

import re
from pathlib import Path

from ot.config.loader import get_config
from ot.executor.tool_loader import load_tool_registry
from otdev.docsgen.metadata import PACK_BY_DISPLAY_NAME

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / "docs" / "reference" / "tools" / "index.md"
CFG = ROOT / "tests" / ".onetool" / "onetool.yaml"

_RE_BOLD_NAME = re.compile(r"\*\*([^*]+)\*\*")
_RE_HEADER_COUNT = re.compile(r"\*\*(\d+) Packs\. (\d+) Tools\.\*\*")
_RE_OT_SECRETS_LINK = re.compile(r"\[\*\*OT Secrets\*\*\]\(ot_secrets\.md\)")


def parse_table(text: str) -> dict[str, int]:
    """Parse display-name to tool-count rows from the tools reference table."""
    rows: dict[str, int] = {}
    for line in text.splitlines():
        if not line.startswith("| [**"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        name_cell = cols[0]
        match = _RE_BOLD_NAME.search(name_cell)
        if not match:
            continue
        name = match.group(1)
        count = int(cols[3])
        rows[name] = count
    return rows


def runtime_tool_counts() -> dict[str, int]:
    """Load runtime tool counts using the all-packs test config."""
    get_config(CFG, secrets_path=None)
    reg = load_tool_registry()

    actual_counts: dict[str, int] = {}
    for pack, funcs in reg.packs.items():
        actual_counts[pack] = len(funcs)
    return actual_counts


def validate_registry_text(text: str, actual_counts: dict[str, int]) -> list[str]:
    """Return docs registry validation failures for Markdown text."""
    rows = parse_table(text)
    failures: list[str] = []

    match = _RE_HEADER_COUNT.search(text)
    if not match:
        failures.append("Missing header count line '**N Packs. M Tools.**'")
    else:
        docs_pack_count = int(match.group(1))
        docs_tool_count = int(match.group(2))
        runtime_pack_count = len(actual_counts)
        runtime_tool_count = sum(actual_counts.values())
        if docs_pack_count != runtime_pack_count:
            failures.append(
                f"Header pack count mismatch: docs={docs_pack_count} runtime={runtime_pack_count}"
            )
        if docs_tool_count != runtime_tool_count:
            failures.append(
                f"Header tool count mismatch: docs={docs_tool_count} runtime={runtime_tool_count}"
            )

    for display_name, pack in PACK_BY_DISPLAY_NAME.items():
        if display_name not in rows:
            failures.append(f"Missing table row for '{display_name}'")
            continue
        if pack not in actual_counts:
            failures.append(f"Pack '{pack}' missing from runtime registry")
            continue
        if rows[display_name] != actual_counts[pack]:
            failures.append(
                f"Count mismatch for {display_name}: docs={rows[display_name]} runtime={actual_counts[pack]}"
            )

    if not _RE_OT_SECRETS_LINK.search(text):
        failures.append("OT Secrets row must link to secrets.md")

    return failures


def validate_registry_doc(path: Path = DOC) -> list[str]:
    """Validate the tools reference page against the runtime registry."""
    if not path.exists():
        return [f"missing {path}"]
    return validate_registry_text(path.read_text(encoding="utf-8"), runtime_tool_counts())


def _check_skill_index_in_sync() -> list[str]:
    """The ot-ref skill's tool-index copy must be byte-identical to the docs copy."""
    docs_index = ROOT / "docs" / "reference" / "tools" / "tool-index.md"
    skill_index = ROOT / "skills" / "ot-ref" / "reference" / "tool-index.md"
    if not skill_index.exists():
        return [f"missing {skill_index} — run `just docs-sync`"]
    if not docs_index.exists():
        return [f"missing {docs_index} — run `just docs-sync`"]
    if docs_index.read_text(encoding="utf-8") != skill_index.read_text(encoding="utf-8"):
        return [
            f"{skill_index} differs from {docs_index} — run `just docs-sync` and commit"
        ]
    return []


def main() -> int:
    """Run the docs registry check."""
    failures = validate_registry_doc()
    failures += _check_skill_index_in_sync()
    if failures:
        print("docs registry check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("docs registry check passed")
    return 0

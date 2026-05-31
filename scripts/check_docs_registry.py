#!/usr/bin/env python3
"""Validate docs/reference/tools/index.md against runtime registry.

Checks:
- Header tool count matches runtime tool count
- Per-pack tool counts in table match runtime
- OT Secrets row links to a doc page
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ot.config.loader import get_config  # noqa: E402
from ot.executor.tool_loader import load_tool_registry  # noqa: E402
from ot.executor.worker_proxy import WorkerPackProxy  # noqa: E402

DOC = ROOT / "docs/reference/tools/index.md"

_RE_BOLD_NAME = re.compile(r"\*\*([^*]+)\*\*")
_RE_HEADER_COUNT = re.compile(r"\*\*(\d+) Packs\. (\d+) Tools\.\*\*")
_RE_OT_SECRETS_LINK = re.compile(r"\[\*\*OT Secrets\*\*\]\(ot_secrets\.md\)")
CFG = ROOT / "tests/.onetool/onetool.yaml"

NAME_TO_PACK = {
    "AWS": "aws",
    "Brave": "brave",
    "Chat Ops": "chat_ops",
    "Chrome DevTools Util": "chrome_util",
    "OT Context": "ot_context",
    "Context7": "context7",
    "Convert": "convert",
    "DB": "db",
    "Diagram": "diagram",
    "Excel": "excel",
    "File": "file",
    "OT Forge": "ot_forge",
    "Ground": "ground",
    "OT LLM": "ot_llm",
    "Mem": "mem",
    "OT Core": "ot",
    "OT Image": "ot_image",
    "OT Secrets": "ot_secrets",
    "Package": "package",
    "Playwright Util": "play_util",
    "Ripgrep": "ripgrep",
    "Tavily": "tavily",
    "OT Timer": "ot_timer",
    "WB (Whiteboard)": "whiteboard",
    "Webfetch": "webfetch",
}


def parse_table(text: str) -> dict[str, int]:
    rows: dict[str, int] = {}
    for line in text.splitlines():
        if not line.startswith("| [**"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        name_cell = cols[0]
        m = _RE_BOLD_NAME.search(name_cell)
        if not m:
            continue
        name = m.group(1)
        count = int(cols[3])
        rows[name] = count
    return rows


def main() -> int:
    if not DOC.exists():
        print(f"ERROR: missing {DOC}")
        return 1

    # Load full tool registry with test config that enables all packs.
    get_config(CFG, secrets_path=None)
    reg = load_tool_registry()

    actual_counts: dict[str, int] = {}
    for pack, funcs in reg.packs.items():
        if isinstance(funcs, WorkerPackProxy):
            actual_counts[pack] = len(funcs.functions)
        else:
            actual_counts[pack] = len(funcs)

    text = DOC.read_text(encoding="utf-8")
    rows = parse_table(text)

    failures: list[str] = []

    # Header count check
    m = _RE_HEADER_COUNT.search(text)
    if not m:
        failures.append("Missing header count line '**N Packs. M Tools.**'")
    else:
        docs_pack_count, docs_tool_count = int(m.group(1)), int(m.group(2))
        runtime_pack_count, runtime_tool_count = len(actual_counts), sum(actual_counts.values())
        if docs_pack_count != runtime_pack_count:
            failures.append(
                f"Header pack count mismatch: docs={docs_pack_count} runtime={runtime_pack_count}"
            )
        if docs_tool_count != runtime_tool_count:
            failures.append(
                f"Header tool count mismatch: docs={docs_tool_count} runtime={runtime_tool_count}"
            )

    # Row-by-row count checks
    for display_name, pack in NAME_TO_PACK.items():
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

    # Ensure OT Secrets has a page link
    if not _RE_OT_SECRETS_LINK.search(text):
        failures.append("OT Secrets row must link to secrets.md")

    if failures:
        print("docs registry check failed:")
        for f in failures:
            print(f"- {f}")
        return 1

    print("docs registry check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

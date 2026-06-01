#!/usr/bin/env python3
"""Print a compact Tool Index of OneTool packs, tools, and arguments."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _default_config() -> Path:
    candidates = [
        ROOT / ".onetool" / "onetool.yaml",
        ROOT / "tests" / ".onetool" / "onetool.yaml",
        ROOT / "src" / "ot" / "config" / "global_templates" / "onetool.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No OneTool config found. Pass --config <path>.")


def _signature_args(signature: str) -> str:
    start = signature.find("(")
    end = signature.rfind(")")
    if start == -1 or end == -1 or end < start:
        return ""

    args = signature[start + 1 : end]
    args = args.replace("*, ", "").replace("*", "")
    args = re.sub(r"\s+", " ", args)
    args = re.sub(r": '([^']+)'", r": \1", args)
    args = re.sub(r': "([^"]+)"', r": \1", args)
    args = re.sub(r"\s*=\s*", "=", args)
    args = re.sub(r"\s*,\s*", ", ", args)
    return args.strip()


def _description_by_arg(detail: dict[str, Any]) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for raw in detail.get("args", []):
        if not isinstance(raw, str) or ":" not in raw:
            continue
        name, _, description = raw.partition(":")
        descriptions[name.strip()] = description.strip()
    return descriptions


def _short_description(description: Any) -> str:
    """Return the first non-empty line of a description."""
    for line in str(description or "").splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def _tool_inventory(
    *,
    include_tool_descriptions: bool,
    include_descriptions: bool,
) -> list[dict[str, Any]]:
    from ot.meta import pack_info, packs, tool_info

    pack_rows = packs(info="full")
    inventory: list[dict[str, Any]] = []

    for pack_row in pack_rows:
        if not isinstance(pack_row, dict):
            continue

        pack_name = str(pack_row["name"])
        details_info = "default" if include_tool_descriptions else "min"
        details = tool_info(pattern=f"{pack_name}.", info=details_info)
        detail_rows = [details] if isinstance(details, dict) else details

        tools: list[dict[str, Any]] = []
        for detail in detail_rows:
            name = str(detail["name"])
            args = _signature_args(str(detail.get("signature", "")))
            tool_row: dict[str, Any] = {
                "name": name,
                "short_name": name.removeprefix(f"{pack_name}."),
                "args": args,
            }
            if include_tool_descriptions:
                tool_row["description"] = _short_description(detail.get("description"))
            if include_descriptions:
                tool_row["arg_descriptions"] = _description_by_arg(detail)
            tools.append(tool_row)

        tools.sort(key=lambda item: str(item["name"]))
        pack_detail = pack_info(name=pack_name, info="min")
        inventory.append(
            {
                "pack": pack_name,
                "short": pack_row.get("short"),
                "source": pack_detail.get("source", pack_row.get("source", "")),
                "tools": tools,
            }
        )

    inventory.sort(key=lambda item: str(item["pack"]))
    return inventory


def _format_text(
    inventory: list[dict[str, Any]],
    *,
    include_tool_descriptions: bool,
    include_descriptions: bool,
) -> str:
    lines: list[str] = []
    pack_count = len(inventory)
    tool_count = sum(len(pack["tools"]) for pack in inventory)
    lines.append("# OneTool MCP Tool Index")
    lines.append("")
    lines.append(f"packs={pack_count} tools={tool_count}")

    for pack in inventory:
        tools = pack["tools"]
        heading = str(pack["pack"])
        if pack.get("short"):
            heading = f"{heading}, {pack['short']}"
        lines.append(f"\n## {heading}")
        lines.append("```python")
        for tool in tools:
            line = f"{tool['name']}({tool['args']})"
            if include_tool_descriptions and tool.get("description"):
                line = f"{line}  # {tool['description']}"
            lines.append(line)
            if include_descriptions:
                for arg, description in tool.get("arg_descriptions", {}).items():
                    lines.append(f"# {arg}: {description}")
        lines.append("```")

    return "\n".join(lines)


def main() -> int:
    from loguru import logger

    from ot.config.loader import get_config

    logger.remove()

    parser = argparse.ArgumentParser(
        description="Output OneTool packs, tools, and args as a compact Tool Index."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="OneTool config path. Defaults to .onetool/onetool.yaml if present.",
    )
    parser.add_argument(
        "--secrets",
        type=Path,
        default=None,
        help="Optional secrets file path to load with the config.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--tool-descriptions",
        action="store_true",
        help="Include one-line tool descriptions.",
    )
    parser.add_argument(
        "--descriptions",
        action="store_true",
        help="Include argument descriptions. More complete, less token efficient.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "reference" / "tools" / "tool-index.md",
        help="Output file path. Use '-' for stdout.",
    )
    args = parser.parse_args()

    config = args.config or _default_config()
    get_config(config, reload=True, secrets_path=args.secrets)

    inventory = _tool_inventory(
        include_tool_descriptions=args.tool_descriptions,
        include_descriptions=args.descriptions,
    )
    if args.format == "json":
        output = json.dumps(inventory, separators=(",", ":"), sort_keys=True)
    else:
        output = _format_text(
            inventory,
            include_tool_descriptions=args.tool_descriptions,
            include_descriptions=args.descriptions,
        )

    if str(args.output) == "-":
        print(output)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

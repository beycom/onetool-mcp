"""Parse and compile schema-v3 Markdown sequence documents."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import yaml

from .attachments import MAX_ATTACHMENT_BYTES, inspect_attachment
from .resolver import ENDPOINT_KINDS, timeline_view
from .validate import Finding
from .yamlio import source_location

if TYPE_CHECKING:
    from pathlib import Path

    from .model import Architecture

ID_PATTERN = re.compile(r"[A-Za-z0-9._-]+\Z")
DECLARATION = re.compile(r"^(participant|actor)\s+(\S+)(?:\s+as\s+(.+))?$")
ARROW = re.compile(r"^(<<|<)?(--|~|-)(>>|>|\)|x)?$")
MESSAGE = re.compile(r"^(\S+)\s+(\S+)\s+(\S+)(?:\s*:\s*(.*))?$")
RESERVED = re.compile(
    r"^(?:par|critical|break|box|autonumber|activate|deactivate|create|destroy|"
    r"rect|links?\b|note\s+between\b|state\s+over\b|text\s+(?:left|right)\b|"
    r"divider\b.*\bwith\s+height\b)",
    re.IGNORECASE,
)


@dataclass
class _ScenarioSource:
    name: str
    id: str
    line: int
    statements: list[tuple[int, str]] = field(default_factory=list)
    prose: list[str] = field(default_factory=list)


def _finding(
    path: Path, severity: str, code: str, line: int, message: str = ""
) -> Finding:
    return Finding(
        severity=severity,  # type: ignore[arg-type]
        code=code,
        message=message or code.replace("_", " "),
        file=str(path),
        line=line,
        column=1,
        path="sequence",
    )


def _frontmatter(
    path: Path, lines: list[str], findings: list[Finding]
) -> tuple[dict[str, Any], dict[str, int], int]:
    if not lines or lines[0].strip() != "---":
        findings.append(_finding(path, "error", "parse_error", 1))
        return {}, {}, 0
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        findings.append(_finding(path, "error", "parse_error", 1))
        return {}, {}, len(lines)
    key_lines = {
        match.group(1): index + 1
        for index, line in enumerate(lines[1:end], start=1)
        if (match := re.match(r"^([A-Za-z_][\w-]*):", line))
    }
    try:
        raw = yaml.safe_load("\n".join(lines[1:end])) or {}
    except yaml.YAMLError as exc:
        findings.append(_finding(path, "error", "parse_error", 1, str(exc)))
        return {}, key_lines, end + 1
    if not isinstance(raw, dict):
        findings.append(_finding(path, "error", "parse_error", 1))
        return {}, key_lines, end + 1
    for key in ("id", "name"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            findings.append(
                _finding(path, "error", "missing_required", key_lines.get(key, 1))
            )
    flow_id = raw.get("id")
    if isinstance(flow_id, str) and ID_PATTERN.fullmatch(flow_id.strip()) is None:
        findings.append(_finding(path, "error", "invalid_id", key_lines.get("id", 1)))
    return raw, key_lines, end + 1


def _document_parts(
    lines: list[str], start: int, path: Path, findings: list[Finding]
) -> tuple[list[tuple[int, str]], list[_ScenarioSource]]:
    prefix: list[tuple[int, str]] = []
    scenarios: list[_ScenarioSource] = []
    seen: set[str] = set()
    current: _ScenarioSource | None = None
    in_fence = False
    for index in range(start, len(lines)):
        raw = lines[index]
        stripped = raw.strip()
        line = index + 1
        if stripped.startswith("```"):
            in_fence = stripped == "```seq" if not in_fence else False
            continue
        if not in_fence and stripped.startswith("## "):
            name = stripped[3:].strip()
            scenario_id = re.sub(r"\s+", "-", name.lower())
            if ID_PATTERN.fullmatch(scenario_id) is None:
                findings.append(_finding(path, "error", "invalid_id", line))
            if scenario_id in seen:
                findings.append(_finding(path, "error", "duplicate_id", line))
            seen.add(scenario_id)
            current = _ScenarioSource(name, scenario_id, line)
            scenarios.append(current)
            continue
        if current is None:
            if in_fence or DECLARATION.fullmatch(stripped):
                prefix.append((line, stripped))
        elif in_fence:
            current.statements.append((line, stripped))
        elif stripped:
            current.prose.append(stripped)
    if not scenarios:
        scenarios.append(_ScenarioSource("Main", "main", 1, prefix))
        prefix = []
    return prefix, scenarios


class _Compiler:
    def __init__(self, architecture: Architecture, path: Path) -> None:
        self.path = path
        source, _mark = source_location(architecture, ())
        self.model_dir = source.parent if source is not None else path.parent
        self.findings: list[Finding] = []
        self.entities = {
            row.id.casefold(): (row.id, kind)
            for kind in ENDPOINT_KINDS
            for row in getattr(architecture, kind)
        }
        self.interfaces = {row.id.casefold(): row.id for row in architecture.interfaces}
        self.participants: dict[str, dict[str, Any]] = {}

    def issue(self, severity: str, code: str, line: int, message: str = "") -> None:
        self.findings.append(_finding(self.path, severity, code, line, message))

    def declare(self, line: int, text: str) -> None:
        match = DECLARATION.fullmatch(text)
        if match is None:
            return
        kind, authored_id, label = match.groups()
        key = authored_id.casefold()
        if key in self.participants:
            return
        if ID_PATTERN.fullmatch(authored_id) is None:
            self.issue(
                "error", "invalid_id", line, f"invalid participant {authored_id!r}"
            )
            return
        if label is not None:
            payload: dict[str, Any] = {"id": authored_id, "label": label.strip()}
            if kind == "actor":
                payload["actor"] = True
        elif key in self.entities:
            canonical, entity_kind = self.entities[key]
            payload = {"id": canonical, "ref": f"{entity_kind}:{canonical}"}
        else:
            self.issue("error", "unresolved_participant", line, authored_id)
            return
        self.participants[key] = payload

    def participant(self, token: str, line: int) -> str:
        key = token.casefold()
        if key in self.participants:
            return str(self.participants[key]["id"])
        if key in self.entities:
            canonical, kind = self.entities[key]
            payload = {"id": canonical, "ref": f"{kind}:{canonical}"}
        else:
            payload = {"id": token}
            self.issue("warning", "implicit_participant", line, token)
        self.participants[key] = payload
        return str(self.participants[key]["id"])

    def attachment(self, relative: str, line: int) -> bool:
        code, _text, size = inspect_attachment(self.model_dir, relative)
        if code is not None:
            self.issue("error", code, line, f"invalid attachment {relative!r}")
            return False
        if size > MAX_ATTACHMENT_BYTES:
            self.issue("warning", "large_attachment", line, relative)
        return True

    def parse_message(self, text: str, line: int) -> dict[str, Any] | None:
        interface: str | None = None
        if match := re.search(r"\s+\[([A-Za-z0-9._-]+)]\s*$", text):
            interface = match.group(1)
            text = text[: match.start()].rstrip()
        match = MESSAGE.fullmatch(text)
        if match is None:
            self.issue("error", "parse_error", line)
            return None
        left, arrow_text, right, label = match.groups()
        arrow = ARROW.fullmatch(arrow_text)
        if arrow is None:
            self.issue("error", "parse_error", line, f"invalid arrow {arrow_text!r}")
            return None
        left_head, line_style, right_head = arrow.groups()
        if (left_head is None and right_head is None) or (
            left_head and right_head == "x"
        ):
            self.issue("error", "parse_error", line, f"invalid arrow {arrow_text!r}")
            return None
        bidi = left_head is not None and right_head is not None
        left_marker, left = (
            (left[0], left[1:]) if left[:1] in {"+", "-"} else (None, left)
        )
        right_marker, right = (
            (right[0], right[1:]) if right[:1] in {"+", "-"} else (None, right)
        )
        source, target = (
            (right, left) if left_head and not right_head else (left, right)
        )
        source_marker, target_marker = (
            (right_marker, left_marker)
            if left_head and not right_head
            else (left_marker, right_marker)
        )
        if (
            (bidi and (left_marker or right_marker))
            or source_marker == "+"
            or target_marker == "-"
        ):
            self.issue("error", "parse_error", line)
            return None
        kind = (
            "lost"
            if right_head == "x"
            else "async"
            if right_head == ")" or line_style == "~"
            else "reply"
            if line_style == "--"
            else "sync"
        )
        item: dict[str, Any] = {"kind": kind}
        external = source in {"[", "]"} or target in {"[", "]"}
        deferred = source.startswith("...") or target.startswith("...")
        if external:
            edge_token = source if source in {"[", "]"} else target
            item["external"] = "in" if source in {"[", "]"} else "out"
            if edge_token == "]":
                item["edge"] = "right"
            if source not in {"[", "]"}:
                item["from"] = self.participant(source, line)
            if target not in {"[", "]"}:
                item["to"] = self.participant(target, line)
        elif deferred:
            defer_token = source if source.startswith("...") else target
            defer_id = defer_token[3:]
            if ID_PATTERN.fullmatch(defer_id) is None:
                self.issue("error", "invalid_id", line, defer_id)
                return None
            item["defer"] = defer_id
            if not source.startswith("..."):
                item["from"] = self.participant(source, line)
            if not target.startswith("..."):
                item["to"] = self.participant(target, line)
        else:
            item["from"] = self.participant(source, line)
            item["to"] = self.participant(target, line)
        if label:
            item["text"] = re.sub(r"\\n|<br\s*/?>", "\n", label, flags=re.IGNORECASE)
        if interface is not None:
            canonical = self.interfaces.get(interface.casefold())
            if canonical is None:
                self.issue("error", "unresolved_interface", line, interface)
                return None
            item["interface"] = canonical
        if bidi:
            item["bidi"] = True
        if line_style == "~":
            item["wavy"] = True
        if target_marker == "+":
            item["activate"] = True
        if source_marker == "-":
            item["deactivate"] = True
        return item

    def scenario(self, source: _ScenarioSource) -> dict[str, Any]:
        manual = any(
            (match := MESSAGE.fullmatch(text)) is not None
            and (match.group(1)[:1] in {"+", "-"} or match.group(3)[:1] in {"+", "-"})
            for _line, text in source.statements
        )
        result: dict[str, Any] = {"id": source.id, "name": source.name}
        if source.prose:
            result["description"] = "\n".join(source.prose)
        if manual:
            result["activation"] = "manual"
        items: list[dict[str, Any]] = []
        result["items"] = items
        stack: list[tuple[dict[str, Any], list[dict[str, Any]], int]] = []
        current = items
        last_message: dict[str, Any] | None = None
        deferred: dict[str, list[tuple[str, int]]] = {}
        active: set[str] = set()
        calls: dict[tuple[str, str], list[tuple[int, bool]]] = {}
        item_count = 0
        for line, text in source.statements:
            if not text or text.startswith(("%%", "#")) or DECLARATION.fullmatch(text):
                continue
            if RESERVED.match(text):
                self.issue("error", "reserved_keyword", line)
                continue
            if match := re.match(
                r"^(alt|if|opt|loop|repeat|group)\s+(.+)$", text, re.IGNORECASE
            ):
                authored, label = match.groups()
                frame_kind = {"if": "alt", "repeat": "loop"}.get(
                    authored.lower(), authored.lower()
                )
                frame = dict[str, Any](frame=frame_kind, label=label, items=[])
                current.append(frame)
                stack.append((frame, current, line))
                current = frame["items"]
                item_count += 1
                continue
            if match := re.match(r"^else(?:\s+if)?(?:\s+(.*))?$", text, re.IGNORECASE):
                if not stack or stack[-1][0]["frame"] != "alt":
                    self.issue("error", "parse_error", line)
                    continue
                frame = stack[-1][0]
                branch: dict[str, Any] = {"items": []}
                if match.group(1):
                    branch["label"] = match.group(1)
                frame.setdefault("else", []).append(branch)
                current = branch["items"]
                continue
            if text.lower() == "end":
                if not stack:
                    self.issue("error", "parse_error", line)
                    continue
                _frame, parent, _opening = stack.pop()
                current = parent
                continue
            if match := re.match(r"^attach(?:\s+(.*))?$", text, re.IGNORECASE):
                relative = (match.group(1) or "").strip()
                if last_message is None or not relative:
                    self.issue("error", "parse_error", line)
                elif self.attachment(relative, line):
                    last_message.setdefault("attachments", []).append(relative)
                continue
            if match := re.match(
                r"^divider(?:\s+(line|space|delay|tear))?\s*:\s*(.+)$",
                text,
                re.IGNORECASE,
            ):
                style, label = match.groups()
                item = {"divider": label}
                if style and style.lower() != "line":
                    item["style"] = style.lower()
                current.append(item)
                item_count += 1
                continue
            if match := re.match(
                r"^note\s+(over|left of|right of)\s+([^:]+):\s*(.*)$",
                text,
                re.IGNORECASE,
            ):
                placement, names, label = match.groups()
                at = [self.participant(name.strip(), line) for name in names.split(",")]
                if not 1 <= len(at) <= 2:
                    self.issue("error", "parse_error", line)
                    continue
                current.append(
                    {
                        "note": re.sub(
                            r"\\n|<br\s*/?>", "\n", label, flags=re.IGNORECASE
                        ),
                        "placement": {"left of": "left", "right of": "right"}.get(
                            placement.lower(), "over"
                        ),
                        "at": at,
                    }
                )
                item_count += 1
                continue
            message = self.parse_message(text, line)
            if message is None:
                continue
            current.append(message)
            last_message = message
            item_count += 1
            if defer_id := message.get("defer"):
                role = "send" if "from" in message else "completion"
                deferred.setdefault(defer_id, []).append((role, line))
            if manual:
                if message.get("deactivate"):
                    sender = message.get("from")
                    if sender not in active:
                        self.issue("warning", "unmatched_activation", line)
                    active.discard(sender)
                if message.get("activate") and isinstance(message.get("to"), str):
                    active.add(message["to"])
            elif "from" in message and "to" in message:
                pair = (message["from"], message["to"])
                if message["kind"] == "sync":
                    calls.setdefault(pair, []).append((line, False))
                elif message["kind"] == "reply":
                    reverse = (message["to"], message["from"])
                    open_calls = calls.get(reverse, [])
                    for index in range(len(open_calls) - 1, -1, -1):
                        if not open_calls[index][1]:
                            call_line, _closed = open_calls[index]
                            open_calls[index] = (call_line, True)
                            break
        for _frame, _parent, opening in stack:
            self.issue("error", "parse_error", opening)
        for entries in deferred.values():
            valid = (
                len(entries) == 2
                and entries[0][0] == "send"
                and entries[1][0] == "completion"
            )
            if not valid:
                for _role, line in entries:
                    self.issue("error", "unpaired_defer", line)
        if not manual:
            for call_entries in calls.values():
                closed_lines = [
                    call_line for call_line, closed in call_entries if closed
                ]
                for call_line, closed in call_entries:
                    if not closed and any(later > call_line for later in closed_lines):
                        self.issue("warning", "crossed_reply", call_line)
        if item_count > 300:
            self.issue("warning", "large_scenario", source.line)
        return result


def _intervals(
    architecture: Architecture,
    start_in: str | None,
    end_in: str | None,
) -> list[dict[str, Any]]:
    timelines = architecture.timelines or []
    views = [timeline_view(architecture, item.id) for item in timelines] or [
        timeline_view(architecture)
    ]
    result: list[dict[str, Any]] = []
    for view in views:
        if start_in in (None, "base"):
            start = 0
        elif start_in is not None and view.contains(start_in):
            start = view.position(start_in)
        else:
            result.append({"live": [], "clips": []})
            continue
        stop = (
            view.position(end_in)
            if end_in is not None and view.contains(end_in)
            else len(view.milestones)
        )
        live: list[list[int | None]] = []
        if start <= stop:
            live = [[start, None if stop == len(view.milestones) else stop]]
        result.append({"live": live, "clips": []})
    return result


def compile_sequence_file(
    path: Path, architecture: Architecture
) -> tuple[dict[str, Any] | None, list[Finding]]:
    """Parse and compile one Markdown flow document."""
    compiler = _Compiler(architecture, path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return None, [_finding(path, "error", "parse_error", 1, str(exc))]
    raw, key_lines, start = _frontmatter(path, lines, compiler.findings)
    prefix, scenarios = _document_parts(lines, start, path, compiler.findings)
    for line, text in [
        *prefix,
        *(item for scenario in scenarios for item in scenario.statements),
    ]:
        compiler.declare(line, text)
    compiled_scenarios = [compiler.scenario(item) for item in scenarios]
    milestone_ids = {item.id for item in architecture.milestones}
    referenced = [raw.get("start_in"), raw.get("end_in")]
    for key, value in zip(("start_in", "end_in"), referenced, strict=True):
        if value is not None and value != "base" and value not in milestone_ids:
            compiler.issue(
                "error", "unresolved_milestone", key_lines.get(key, 1), str(value)
            )
    orders = [item.milestones for item in architecture.timelines or []] or [
        [item.id for item in architecture.milestones]
    ]
    start_in, end_in = referenced
    if (
        start_in is not None
        and end_in is not None
        and any(
            start_in in ["base", *order]
            and end_in in ["base", *order]
            and ["base", *order].index(start_in) > ["base", *order].index(end_in)
            for order in orders
        )
    ):
        compiler.issue("error", "invalid_interval", key_lines.get("start_in", 1))
    on_timelines = {milestone for order in orders for milestone in order}
    for key, value in zip(("start_in", "end_in"), referenced, strict=True):
        if value in milestone_ids and value not in on_timelines:
            compiler.issue("warning", "dangling_interval", key_lines.get(key, 1))
    if len(compiler.participants) > 30:
        compiler.issue("warning", "large_scenario", 1)
    if any(item.severity == "error" for item in compiler.findings):
        return None, compiler.findings
    sequence: dict[str, Any] = {"id": raw["id"].strip(), "name": raw["name"].strip()}
    for key in ("description", "tags"):
        if raw.get(key):
            sequence[key] = raw[key]
    sequence["intervals"] = _intervals(architecture, start_in, end_in)
    sequence["participants"] = list(compiler.participants.values())
    sequence["scenarios"] = compiled_scenarios
    return sequence, compiler.findings


def compile_sequences(
    architecture: Architecture, directory: Path | None = None
) -> tuple[list[dict[str, Any]], list[Finding]]:
    """Discover, parse, and compile the model's sorted sequence documents."""
    if directory is None:
        source, _mark = source_location(architecture, ())
        directory = source.parent / "sequences" if source is not None else None
    if directory is None or not directory.is_dir():
        return [], []
    sequences: list[dict[str, Any]] = []
    findings: list[Finding] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("*.md")):
        sequence, document_findings = compile_sequence_file(path, architecture)
        findings.extend(document_findings)
        if sequence is None:
            continue
        if sequence["id"] in seen:
            id_line = next(
                (
                    i
                    for i, line in enumerate(path.read_text().splitlines(), 1)
                    if line.startswith("id:")
                ),
                1,
            )
            findings.append(_finding(path, "error", "duplicate_id", id_line))
            continue
        seen.add(sequence["id"])
        sequences.append(sequence)
    return sorted(sequences, key=lambda item: item["id"]), findings

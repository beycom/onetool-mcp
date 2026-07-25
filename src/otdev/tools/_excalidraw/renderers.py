"""Note renderers for the excalidraw tool.

Produces text output suitable for Code-font text elements.
"""

from __future__ import annotations

import csv
import io
import re

# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


def render_table(text: str) -> str:
    """Render CSV text as an ASCII grid table.

    First row is treated as the header.

    Example:
        render_table('''
            Task,in,out
            compare:base,33,273
            compare:mcp,3261,92
        ''')
    """
    try:
        from tabulate import tabulate
    except ImportError:
        return "Error: tabulate not installed (pip install tabulate)"

    normalised = re.sub(r";", "\n", text.strip())
    rows = list(csv.reader(io.StringIO(normalised)))
    if not rows:
        return ""
    return tabulate(rows[1:], headers=rows[0], tablefmt="grid")


# ---------------------------------------------------------------------------
# Tree
# ---------------------------------------------------------------------------


_RE_INDENT = re.compile(r"^([-._\s]+)")


def render_tree(text: str) -> str:
    """Render indented text as a tree with unicode connectors.

    Depth is indicated by leading indent characters: '-', '.', '_', or spaces.
    One character = one level (for space-indented trees, the smallest non-zero
    indent seen is used as the unit so 2-space or 4-space indents work naturally).

    Example:
        render_tree('''
            root/
            -src/
            --main.py
            --utils.py
            -tests/
        ''')

        render_tree('''
            root/
              src/
                main.py
              tests/
        ''')
    """
    raw_lines = re.split(r"[;\n]", text.strip())
    lines = [ln.rstrip() for ln in raw_lines if ln.strip()]
    if not lines:
        return ""

    # Parse (depth, label) pairs — accept -, ., _, or space as indent char
    items: list[tuple[int, str]] = []
    space_depths: list[int] = []
    for ln in lines:
        m = _RE_INDENT.match(ln)
        raw_indent = m.group(1) if m else ""
        if raw_indent:
            indent_char = raw_indent[0]
            depth = len(raw_indent)
            if indent_char == " ":
                space_depths.append(depth)
        else:
            depth = 0
        items.append((depth, ln[len(raw_indent) :].strip()))

    # Normalise space-indented depths by smallest non-zero indent (the "unit")
    if space_depths:
        unit = min(space_depths)
        items = [(d // unit if d > 0 else 0, lbl) for d, lbl in items]

    n = len(items)

    # Pre-compute has_next in O(n): does a same-depth sibling exist to the right
    # without an intervening shallower node?
    # Scan right-to-left: track which depths still have a right sibling visible.
    # The set is pruned at each node to remove depths deeper than the current one,
    # since a shallower node closes all deeper subtrees. Set size is bounded by
    # tree depth (not n), so pruning is cheap in practice.
    has_next_arr = [False] * n
    depths_with_right_sibling: set[int] = set()
    for idx in range(n - 1, -1, -1):
        depth = items[idx][0]
        has_next_arr[idx] = depth in depths_with_right_sibling
        depths_with_right_sibling.add(depth)
        depths_with_right_sibling -= {d for d in depths_with_right_sibling if d > depth}

    out: list[str] = []
    open_depths: set[int] = set()

    for idx, (depth, label) in enumerate(items):
        if depth == 0:
            out.append(label)
            continue

        prefix = ""
        for d in range(1, depth):
            prefix += "│   " if d in open_depths else "    "

        connector = "├── " if has_next_arr[idx] else "└── "
        out.append(prefix + connector + label)

        if has_next_arr[idx]:
            open_depths.add(depth)
        else:
            open_depths.discard(depth)

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Sequence diagram
# ---------------------------------------------------------------------------


def render_sequence(text: str) -> str:
    """Render a sequence diagram from simple arrow notation.

    Input format (one message per line):
        ActorA -> ActorB: message
        ActorB -> ActorA:

    Example:
        render_sequence('''
            Client -> Server: req
            Server -> DB: query
            DB -> Server: rows
            Server -> Client:
        ''')
    """
    actors: list[str] = []
    messages: list[tuple[str, str, str]] = []

    for line in re.split(r"[;\n]", text.strip()):
        line = line.strip()
        if "->" not in line:
            continue
        src, rest = line.split("->", 1)
        src = src.strip()
        dst, _, label = rest.partition(":")
        dst, label = dst.strip(), label.strip()
        for a in (src, dst):
            if a not in actors:
                actors.append(a)
        messages.append((src, dst, label))

    if not actors:
        return ""

    max_label = max((len(m[2]) for m in messages), default=0)
    bw = {a: len(a) + 4 for a in actors}  # box width: | name |
    gap = max(max_label - 6, 4)  # gap between box edges

    # Center x-position of each actor's vertical line
    cx: dict[str, int] = {}
    x = 0
    for a in actors:
        cx[a] = x + bw[a] // 2
        x += bw[a] + gap
    total_w = x - gap

    def make_row(chars: dict[int, str]) -> str:
        r = [" "] * total_w
        for p, c in chars.items():
            if 0 <= p < total_w:
                r[p] = c
        return "".join(r).rstrip()

    def draw_boxes() -> list[str]:
        top: dict[int, str] = {}
        mid: dict[int, str] = {}
        for a in actors:
            left = cx[a] - bw[a] // 2
            top[left] = top[left + bw[a] - 1] = "+"
            for i in range(1, bw[a] - 1):
                top[left + i] = "-"
            mid[left] = mid[left + bw[a] - 1] = "|"
            for i, c in enumerate(" " + a + " "):
                mid[left + 1 + i] = c
        return [make_row(top), make_row(mid), make_row(top)]

    def draw_vlines() -> str:
        return make_row(dict.fromkeys(cx.values(), "|"))

    def draw_arrow(src: str, dst: str, label: str) -> str:
        chars: dict[int, str] = dict.fromkeys(cx.values(), "|")
        lx, rx = sorted([cx[src], cx[dst]])
        going_right = cx[src] < cx[dst]
        inner = rx - lx - 1
        lbl = label[: inner - 2] if len(label) > inner - 2 else label
        dashes = inner - 1 - len(lbl)
        ld, rd = dashes // 2, dashes - dashes // 2
        if going_right:
            span = "-" * ld + lbl + "-" * rd + ">"
        else:
            span = "<" + "-" * ld + lbl + "-" * rd
        for i, c in enumerate(span):
            chars[lx + 1 + i] = c
        return make_row(chars)

    lines = draw_boxes()
    lines.append(draw_vlines())
    for src, dst, label in messages:
        lines.append(draw_arrow(src, dst, label))
        lines.append(draw_vlines())
    lines += draw_boxes()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Timeline / Gantt
# ---------------------------------------------------------------------------


def render_timeline(text: str) -> str:
    """Render a Gantt-style timeline bar chart.

    Input format: name,start,duration (one task per line, 1-indexed)

    Example:
        render_timeline('''
            Task A,1,8
            Task B,5,8
            Task C,9,8
        ''')
    """
    tasks: list[tuple[str, int, int]] = []

    for row_num, line in enumerate(re.split(r"[;\n]", text.strip()), 1):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            start = int(parts[1])
        except ValueError:
            return (
                f"Error: timeline row {row_num} '{line}' — "
                f"start must be an integer, got '{parts[1]}'. "
                f"Format: name,start,duration (integers, 1-indexed)"
            )
        try:
            dur = int(parts[2])
        except ValueError:
            return (
                f"Error: timeline row {row_num} '{line}' — "
                f"duration must be an integer, got '{parts[2]}'. "
                f"Format: name,start,duration (integers, 1-indexed)"
            )
        tasks.append((parts[0], start, dur))

    if not tasks:
        return ""

    t_min = min(t[1] for t in tasks)
    t_max = max(t[1] + t[2] for t in tasks)
    total = t_max - t_min
    name_w = max(len(t[0]) for t in tasks)

    lines = []
    for name, start, dur in tasks:
        offset = start - t_min
        bar = "." * offset + "#" * dur + "." * (total - offset - dur)
        lines.append(f"{name:<{name_w}}  [{bar}]")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Plain note (paragraph text)
# ---------------------------------------------------------------------------


def render_note(text: str, *, wrap: int = 60) -> str:
    """Render plain text, word-wrapping long lines.

    Args:
        text: Raw paragraph text.
        wrap: Maximum line width in characters.

    Example:
        render_note('Lorem ipsum dolor sit amet...')
    """
    import textwrap

    stripped = text.strip()
    if not stripped:
        return ""
    return "\n".join(
        line
        for para in stripped.split("\n\n")
        for line in textwrap.wrap(para.replace("\n", " "), width=wrap) or [""]
    )

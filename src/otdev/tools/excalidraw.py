"""Excalidraw tool pack — live diagram manipulation via pydoll.

Opens excalidraw.com via pydoll (Chrome CDP) and exposes tools to draw, save,
load, clear, scroll, and zoom diagrams using a Mermaid-compatible DSL.

Supports two usage modes:

- **Headed** (default): user interacts directly with the visible canvas while
  the agent assists — drawing, annotating, running layout, saving files.
- **Headless**: agent-controlled only — user cannot see the canvas, but all
  programmatic tools (draw, save, load, screenshot, layout, etc.) work fully.

Requires Chrome/Chromium to be installed on the host.
"""

from __future__ import annotations

# Pack declaration MUST be before other imports
pack = "whiteboard"
pack_aliases = ("wb",)

__all__ = [
    "align",
    "boards",
    "clear",
    "close",
    "draw",
    "embed_dsl",
    "erase",
    "fit",
    "hard_reset",
    "help",
    "layout",
    "load",
    "note",
    "open",
    "read_scene",
    "save",
    "screenshot",
    "scroll",
    "share",
    "style",
    "sync",
    "zoom",
]

import asyncio
import atexit
import contextlib
import json
import re
import textwrap
import threading
from importlib import resources
from typing import Any

from otdev.tools._excalidraw import session as _session
from otpack import LogSpan, resolve_cwd_path


def _edge_key(e: dict[str, Any]) -> tuple[str, str, str, str | None, str | None]:
    """Return the deduplication key for an edge."""
    return (e["src"], e["dst"], e["label"], e.get("startArrowhead"), e.get("endArrowhead"))


# ---------------------------------------------------------------------------
# JS asset loader
# ---------------------------------------------------------------------------

def _load_js(filename: str) -> str:
    """Load a bundled JavaScript file from disk."""
    return (
        resources.files("otdev.tools._excalidraw")
        .joinpath(filename)
        .read_text(encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# Pydoll browser driver
# ---------------------------------------------------------------------------

_browser: Any = None   # pydoll Chrome instance
_tab: Any = None       # pydoll Tab instance
_loop: asyncio.AbstractEventLoop | None = None



def _run(coro: Any) -> Any:
    """Run an async coroutine synchronously via a dedicated daemon event loop."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        threading.Thread(target=_loop.run_forever, daemon=True).start()
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result(timeout=60)


def _open_browser() -> None:
    """Launch pydoll browser, open tab, navigate to excalidraw.com."""
    global _browser, _tab
    try:
        from pydoll.browser import Chrome
        from pydoll.exceptions import NoValidTabFound
    except ImportError:
        raise ImportError(
            "pydoll-python is required for whiteboard. "
            "Install with: pip install 'onetool-mcp[whiteboard]'"
        ) from None

    async def _start() -> tuple[Any, Any]:
        # Chrome's initial page target may not be registered immediately after the
        # CDP endpoint comes up. Retry up to 3 times with a 1-second gap so the
        # race window doesn't permanently block the first cold start.
        last_exc: Exception = RuntimeError("browser start failed")
        for attempt in range(3):
            if attempt > 0:
                await asyncio.sleep(1)
            b = Chrome()
            try:
                t = await b.start()
                return b, t
            except NoValidTabFound as exc:
                last_exc = exc
                with contextlib.suppress(Exception):
                    await b.stop()  # type: ignore[no-untyped-call]
        raise last_exc

    b, t = _run(_start())
    _browser = b
    _tab = t
    _browser_navigate("https://excalidraw.com")


def _close_browser() -> None:
    """Close browser process. Tolerates already-closed state.

    Registered as an atexit handler at module load.  Must be fast and
    reliable even during interpreter shutdown when the daemon event loop
    thread may already be dead.

    Strategy:
    1. SIGKILL the Chrome subprocess immediately (< 1 ms, no waiting).
       Using kill() rather than terminate()+wait() because pydoll's
       stop_process() waits up to 15 s for a graceful SIGTERM and the
       atexit path needs to be instant.
    2. Close the WebSocket if the event loop is still alive (best-effort).
    3. Remove pydoll's temp directories synchronously.
    """
    global _browser, _tab
    b, _browser, _tab = _browser, None, None
    if b is None:
        return
    # 1. Kill Chrome subprocess immediately.
    with contextlib.suppress(Exception):
        pm = getattr(b, "_browser_process_manager", None)
        proc = getattr(pm, "_process", None) if pm else None
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)
    # 2. Close WebSocket connection (best-effort, needs live event loop).
    with contextlib.suppress(Exception):
        if _loop is not None and _loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                b._connection_handler.close(), _loop
            )
            future.result(timeout=3)
    # 3. Remove temp directories synchronously.
    with contextlib.suppress(Exception):
        tm = getattr(b, "_temp_directory_manager", None)
        if tm is not None:
            tm.cleanup()


atexit.register(_close_browser)


def _check_browser() -> str | None:
    """Return error string if browser not open, else None."""
    if _tab is None:
        return "Error: whiteboard browser not open. Call whiteboard.open() first."
    return None


def _browser_navigate(url: str) -> None:
    """Navigate the browser to the given URL."""
    _run(_tab.go_to(url=url))


def _extract_js_value(response: Any) -> Any:
    """Extract the Python value from an execute_script EvaluateResponse dict."""
    return response.get("result", {}).get("result", {}).get("value")


def _browser_evaluate(fn: str) -> str:
    """Evaluate a JS function string in the browser and return result as string."""
    response = _run(_tab.execute_script(
        f"({fn})()",
        return_by_value=True,
        await_promise=True,
    ))
    value = _extract_js_value(response)
    if value is None:
        return "null"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def _browser_evaluate_json(fn: str) -> Any:
    """Evaluate a JS function and return a Python-native result."""
    response = _run(_tab.execute_script(
        f"({fn})()",
        return_by_value=True,
        await_promise=True,
    ))
    value = _extract_js_value(response)
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value
    return value


# ---------------------------------------------------------------------------
# JS batch draw caller
# ---------------------------------------------------------------------------


def _js_batch_draw(
    *,
    shapes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    subgraphs: list[dict[str, Any]],
) -> None:
    """Send all shapes, edges, and subgraphs to the browser in one round-trip."""
    s_json = json.dumps(shapes)
    e_json = json.dumps(edges)
    f_json = json.dumps(subgraphs)
    _browser_evaluate(f"() => window._batch_draw({s_json}, {e_json}, {f_json})")


def _js_patch_elements(patches: list[dict[str, Any]]) -> None:
    """Patch existing elements (label and/or style) without changing position.

    JS returns the matched element count, but draw() callers don't need it.
    Use _js_style_elements when you need the count.
    """
    p_json = json.dumps(patches)
    _browser_evaluate(f"() => window._patch_elements({p_json})")


def _js_style_elements(ids: list[str], style_props: dict[str, Any]) -> int:
    """Apply style properties to elements by ID. Returns count of matched elements."""
    ids_json = json.dumps(ids)
    props_json = json.dumps(style_props)
    result = _browser_evaluate(f"() => window._style_elements({ids_json}, {props_json})")
    try:
        return int(result)
    except (ValueError, TypeError):
        return len(ids)


_DEFAULT_FONT_SIZE = 16
_SHAPE_CHAR_W_RATIO = 0.62  # approximate char width as fraction of font size
_SHAPE_PAD_X = 28
_SHAPE_PAD_Y = 22
_SHAPE_MIN_W = 160
_SHAPE_MIN_H = 60


def _auto_size(label: str, font_size: int = _DEFAULT_FONT_SIZE) -> tuple[int, int]:
    """Compute shape dimensions from label content."""
    lines = (label or "").split("\n")
    max_chars = max((len(line) for line in lines), default=1)
    w = max(_SHAPE_MIN_W, int(max_chars * font_size * _SHAPE_CHAR_W_RATIO + _SHAPE_PAD_X))
    h = max(_SHAPE_MIN_H, int(len(lines) * font_size * 1.25 + _SHAPE_PAD_Y))
    return w, h


def _shape_payload(
    id_: str,
    shape: dict[str, Any],
    x: float,
    y: float,
    style: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a shape payload dict for _js_batch_draw.

    Dimensions are auto-computed from the label unless explicit
    ``width``/``height`` keys are present in style.
    """
    style = dict(style or {})
    label = shape["label"] or ""
    font_size = int(style.get("fontSize", _DEFAULT_FONT_SIZE))
    aw, ah = _auto_size(label, font_size)
    final_w = style.pop("width", aw)
    final_h = style.pop("height", ah)
    final_x = style.pop("x", x)
    final_y = style.pop("y", y)
    return {
        "id": id_, "label": label,
        "x": final_x, "y": final_y, "w": final_w, "h": final_h,
        "shape": "rectangle", "styleProps": style,
    }


# ---------------------------------------------------------------------------
# Browser lifecycle
# ---------------------------------------------------------------------------



def _ensure_ready() -> str | None:
    """Ensure excalidraw.com is open and bootstrapped.

    Opens the browser if not already open. Handles: first call, closed tab,
    navigated-away page, page reload.
    """
    if _tab is None:
        try:
            _open_browser()
        except Exception as exc:
            return f"Error: failed to open browser — {exc}"
        if _tab is None:
            return "Error: failed to open browser"

    try:
        result = _browser_evaluate(
            "() => !!(window.__drawApi?.backend === 'excalidraw' "
            "&& location.hostname.includes('excalidraw.com'))"
        )
        ready = result.lower() == "true"
    except Exception:
        ready = False

    if not ready:
        _browser_navigate("https://excalidraw.com")
        # Wait for React to mount (10s timeout)
        try:
            _browser_evaluate(
                "() => new Promise((resolve, reject) => {"
                "  const tid = setTimeout(() => reject(new Error('timeout')), 10000);"
                "  const check = () => document.getElementById('root')?.children.length > 0"
                "    ? (clearTimeout(tid), resolve()) : setTimeout(check, 100);"
                "  check();"
                "})"
            )
        except Exception:
            return "Error: timed out waiting for excalidraw.com to load"
        bootstrap_result = _browser_evaluate(_load_js("bootstrap.js"))
        if bootstrap_result.strip().lower() == "false":
            return "Error: excalidraw bootstrap failed — React API not found on page"
        # Wait for __drawApi to be set — bootstrap may run before Excalidraw fully mounts (10s timeout)
        try:
            _browser_evaluate(
                "() => new Promise((resolve, reject) => {"
                "  const tid = setTimeout(() => reject(new Error('timeout')), 10000);"
                "  const check = () => typeof window.__drawApi !== 'undefined'"
                "    ? (clearTimeout(tid), resolve(true)) : setTimeout(check, 100);"
                "  check();"
                "})"
            )
        except Exception:
            return "Error: timed out waiting for __drawApi to initialise"

    # Always re-inject ops.js so in-place code changes take effect without a page reload
    _browser_evaluate(_load_js("ops.js"))

    # On fresh navigation: restore any saved session state into the canvas
    if not ready:
        saved = _session.load()
        if saved["shapes"] or saved["edges"]:
            with contextlib.suppress(Exception):
                _rerender_from_state(saved)

    return None


def _rerender_from_state(state: dict[str, Any]) -> None:
    """Re-render all content from session state.

    Shapes are placed in a flat grid (4 cols x N rows, 160x60, gap 40/20).
    Call ``wb.layout()`` afterwards to apply proper graph layout.
    """
    # Flat grid: 4 columns, fixed 160x60 nodes, 40px h-gap, 20px v-gap
    shape_ids = list(state["shapes"].keys())
    cols, node_w, node_h, gap_x, gap_y = 4, 160, 60, 40, 20
    shape_payloads = []
    for i, id_ in enumerate(shape_ids):
        shape = state["shapes"][id_]
        col = i % cols
        row = i // cols
        x = 100.0 + col * (node_w + gap_x)
        y = 100.0 + row * (node_h + gap_y)
        shape_payloads.append(_shape_payload(id_, shape, x, y))

    edge_payloads = [
        {"id": e["id"], "srcId": e["src"], "dstId": e["dst"],
         "label": e["label"], "startArrowhead": e.get("startArrowhead"),
         "endArrowhead": e.get("endArrowhead", "arrow"),
         "styleProps": e.get("styleProps", {})}
        for e in state["edges"]
    ]

    subgraph_payloads = [
        {"id": gid, "label": group["label"], "memberIds": group["members"], "savedBounds": None}
        for gid, group in state["groups"].items()
    ]

    _js_batch_draw(shapes=shape_payloads, edges=edge_payloads, subgraphs=subgraph_payloads)


def _get_canvas_max_y() -> float:
    """Return the maximum bottom edge (y + height) of all non-deleted, non-text elements.

    Returns 60.0 if the canvas is empty or the call fails.
    """
    result = _browser_evaluate_json(
        "() => {"
        "  const els = Array.from(window.__drawApi.read())"
        "    .filter(e => !e.isDeleted && e.type !== 'text');"
        "  return els.length ? Math.max(...els.map(e => e.y + (e.height || 0))) : 0;"
        "}"
    )
    try:
        return float(result)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# DSL parser
# ---------------------------------------------------------------------------

# Edge operator pattern used in ID pre-normalisation (longest first to avoid prefix clashes)
_EDGE_OP_RE = re.compile(r'(<-->|-\.->|-\.-|--[ox]|-->|---)')

_RE_HEADER   = re.compile(r"^(?:flowchart|graph)\s+\w+$")
_RE_SUBGRAPH = re.compile(r'^subgraph\s+([\w-]+)(?:\s+\[\s*"([^"]+)"\s*\])?$')

# Rectangle shape — trailing content after ] is parsed as inline style props
_RE_SHAPE_RECT    = re.compile(r'^([\w-]+)\s*\[\s*"?([^"\]]*)"?\s*\]\s*(.*)$')
# Hints for deprecated ellipse/diamond syntax (to provide a clear error)
_RE_SHAPE_ELLIPSE = re.compile(r'^[\w-]+\s*\(\s*\(')
_RE_SHAPE_DIAMOND = re.compile(r'^[\w-]+\s*\{')
# Bare id + inline style props:  a bc:green,sw:2
_RE_BARE_STYLE    = re.compile(r'^([\w-]+)\s+([a-z]+:.+)$')

# (pattern, id_suffix, has_label, start_arrowhead, end_arrowhead, directed, stroke_style)
_EDGE_PATTERNS: list[tuple[re.Pattern[str], str, bool, str | None, str | None, bool, str | None]] = [
    (re.compile(r"^([\w-]+)\s*<-->\s*(?:\|([^|]*)\|)?\s*([\w-]+)$"),    "-bidir",      True,  "arrow", "arrow", True,  None),
    (re.compile(r"^([\w-]+)\s*-\.->\s*(?:\|([^|]*)\|)?\s*([\w-]+)$"),   "-dashed",     True,  None,    "arrow", True,  "dashed"),
    (re.compile(r"^([\w-]+)\s*-\.-\s*([\w-]+)$"),                         "-dashed-und", False, None,    None,    False, "dashed"),
    (re.compile(r"^([\w-]+)\s*--o\s*(?:\|([^|]*)\|)?\s*([\w-]+)$"),     "-dot",        True,  None,    "dot",   True,  None),
    (re.compile(r"^([\w-]+)\s*--x\s*(?:\|([^|]*)\|)?\s*([\w-]+)$"),     "-bar",        True,  None,    "bar",   True,  None),
    (re.compile(r"^([\w-]+)\s*-->\s*(?:\|([^|]*)\|)?\s*([\w-]+)$"),     "",            True,  None,    "arrow", True,  None),
    (re.compile(r"^([\w-]+)\s*---\s*([\w-]+)$"),                          "-und",        False, None,    None,    False, None),
]


def _norm_id(raw: str) -> str:
    """Normalise a node ID: strip non-word chars (except underscore), lowercase."""
    return re.sub(r"[^\w]", "", raw).lower()


def _expand_combined_shape_edge(line: str) -> list[str]:
    """Expand a combined 'id["Label"] --> id["Label"]' line into separate declarations.

    Splits ``a["Hello"] --> b["World"]`` into
    ``['a["Hello"]', 'b["World"]', 'a-->b']`` so that shape labels are
    preserved and the edge uses bare IDs.  Lines without embedded labels are
    returned unchanged as a single-element list.
    """
    if "[" not in line:
        return [line]
    m = _EDGE_OP_RE.search(line)
    if not m:
        return [line]

    op_start, op_end = m.start(), m.end()
    src_raw = line[:op_start].strip()
    rest = line[op_end:]

    # Strip trailing inline style block {key:val,...}
    style_suffix = ""
    if sm := re.search(r"\s*(\{[^}]*\})\s*$", rest):
        style_suffix = " " + sm.group(1).strip()
        rest = rest[: sm.start()]

    # Labeled edge: -->|label|dst
    label_part = ""
    if lm := re.match(r"^\s*\|([^|]*)\|\s*(.*)", rest):
        label_part = "|" + lm[1] + "|"
        dst_raw = lm[2].strip()
    else:
        dst_raw = rest.strip()

    src_bracket = src_raw.find("[")
    dst_bracket = dst_raw.find("[")
    if src_bracket < 0 and dst_bracket < 0:
        return [line]  # No embedded labels; handle normally

    extra: list[str] = []
    if src_bracket > 0:
        extra.append(src_raw)           # e.g. 'a["Hello"]' → shape declaration
        src_part = src_raw[:src_bracket].strip()
    else:
        src_part = src_raw

    if dst_bracket > 0:
        extra.append(dst_raw)           # e.g. 'b["World"]' → shape declaration
        dst_part = dst_raw[:dst_bracket].strip()
    else:
        dst_part = dst_raw

    edge_line = src_part + m.group() + label_part + dst_part + style_suffix
    return [*extra, edge_line]


def _prenorm_line(line: str) -> str:
    """Pre-normalise ID tokens in one DSL line before main parsing.

    Handles IDs with spaces, hyphens, or other non-word chars by applying
    _norm_id to every ID position: before ``[``, before/after edge operators,
    after the ``subgraph`` keyword, and bare-ID tokens.

    Label content inside ``["..."]`` and ``|...|`` is never modified.
    """
    if not line:
        return line
    # Preserve comment and directive lines unchanged
    if line.startswith("#") or line.startswith("%%"):
        return line
    if re.match(r"^(?:flowchart|graph|classDef|class|end)(\s|$)", line):
        return line

    # subgraph <id> [optional "Label"]
    if line.startswith("subgraph "):
        m = re.match(r"^(subgraph\s+)(.*?)(\s*(?:\[.*)?$)", line)
        if m:
            raw_id = m[2].strip()
            return "subgraph " + _norm_id(raw_id) + (" " + m[3].strip() if m[3].strip() else "")
        return line

    # Edge line — find operator and normalise src and dst independently
    if m := _EDGE_OP_RE.search(line):
        op_start, op_end = m.start(), m.end()
        op = m.group()
        src_raw = line[:op_start].strip()
        rest = line[op_end:]
        # Strip trailing inline style block {key:val,...} before ID normalisation
        style_suffix = ""
        if sm := re.search(r"\s*(\{[^}]*\})\s*$", rest):
            style_suffix = " " + sm.group(1).strip()
            rest = rest[: sm.start()]
        # Labeled edge: -->|label|dst
        if lm := re.match(r"^\s*\|([^|]*)\|\s*(.*)", rest):
            dst_raw = lm[2].strip()
            return _norm_id(src_raw) + op + "|" + lm[1] + "|" + _norm_id(dst_raw) + style_suffix
        return _norm_id(src_raw) + op + _norm_id(rest.strip()) + style_suffix

    # Shape declaration: id["Label"] [optional inline style]
    bracket = line.find("[")
    if bracket > 0:
        return _norm_id(line[:bracket]) + line[bracket:]

    # Bare id + inline style props (id may be multi-word)
    if m := re.match(r"^([\w\s\-+]+?)\s+([a-z]+:.+)$", line):
        return _norm_id(m[1].strip()) + " " + m[2]

    # Bare id token (subgraph member or unknown) — normalise if non-canonical chars present
    if re.search(r"[\s\-+]", line) and re.match(r"^[\w\s\-+]+$", line):
        return _norm_id(line)

    return line


# ---------------------------------------------------------------------------
# Style property helpers (shared by whiteboard.draw, whiteboard.style, whiteboard.erase docstrings)
# ---------------------------------------------------------------------------

_STYLE_SHORTHANDS: dict[str, str] = {
    "bc":    "backgroundColor",
    "sc":    "strokeColor",
    "sw":    "strokeWidth",
    "ss":    "strokeStyle",
    "r":     "roughness",
    "o":     "opacity",
    "f":     "fontFamily",
    "fs":    "fontSize",
    "ta":    "textAlign",
    "va":    "verticalAlign",
    "fi":    "fillStyle",    # solid, hachure, cross-hatch, dots, zigzag, zigzag-line
    "cr":    "corners",      # shape-only: round (default) | sharp
    "at":    "arrowType",    # edge-only: curve (default) | sharp | elbow
    "shape": "shape",        # special — triggers delete+recreate in JS
    "x":     "x",
    "y":     "y",
    "w":     "width",
    "h":     "height",
}

_NAMED_COLORS: dict[str, str] = {
    "green":  "#bbf7d0",
    "blue":   "#bfdbfe",
    "red":    "#fecaca",
    "purple": "#e9d5ff",
    "yellow": "#fef08a",
    "orange": "#fed7aa",
    "pink":   "#fce7f3",
    "gray":   "#e5e7eb",
    "grey":   "#e5e7eb",
    "white":  "#ffffff",
    "black":  "#000000",
}

_FONT_FAMILY_MAP: dict[str, int] = {"hand": 1, "normal": 2, "mono": 3, "excalidraw": 5}
_STROKE_STYLE_VALUES = {"solid", "dashed", "dotted"}
_TEXT_ALIGN_VALUES   = {"left", "center", "right"}
_VERT_ALIGN_VALUES   = {"top", "middle", "bottom"}
_FILL_STYLE_VALUES   = {"solid", "hachure", "cross-hatch", "dots", "zigzag", "zigzag-line"}
_CORNER_VALUES       = {"round", "sharp"}
_ARROW_TYPE_VALUES   = {"curve", "sharp", "elbow"}
_SHAPE_MAP: dict[str, str] = {"r": "rectangle", "d": "diamond", "c": "ellipse"}


def _parse_style_props(s: str) -> dict[str, Any]:
    """Parse a comma-separated ``key:value`` style string, expanding shorthands.

    Shorthand keys are expanded to Excalidraw property names. Named colours
    (``green``, ``blue``, ``red``, ``purple``, ``yellow``, ``white``,
    ``black``, ``orange``, ``pink``, ``gray``) are resolved to hex values.
    Numeric props (``sw``, ``r``, ``o``, ``f``, ``fs``, ``x``, ``y``,
    ``w``, ``h``) are cast to int/float automatically.

    Args:
        s: Style string like ``"bc:#bbf7d0,sc:#16a34a,sw:2"``.

    Returns:
        Dict with Excalidraw property names as keys.
    """
    props: dict[str, Any] = {}
    for part in s.split(","):
        if ":" not in part:
            continue
        k, v = part.strip().split(":", 1)
        k, v = k.strip(), v.strip()
        if not k or not v:
            continue
        v_lower = v.lower()
        # Expand shorthand key
        prop = _STYLE_SHORTHANDS.get(k, k)
        # Resolve named colour (case-insensitive; hex pass-through unchanged)
        if prop in ("backgroundColor", "strokeColor") and v_lower in _NAMED_COLORS:
            v = _NAMED_COLORS[v_lower]
        # Map font-family shorthand (case-insensitive)
        if prop == "fontFamily" and v_lower in _FONT_FAMILY_MAP:
            props[prop] = _FONT_FAMILY_MAP[v_lower]
            continue
        # Map shape shorthand (r/d/c → excalidraw type names, case-insensitive)
        if prop == "shape" and v_lower in _SHAPE_MAP:
            props[prop] = _SHAPE_MAP[v_lower]
            continue
        # Numeric coercion
        if prop in ("strokeWidth", "roughness", "opacity", "fontSize", "x", "y", "width", "height"):
            try:
                props[prop] = float(v) if "." in v else int(v)
                continue
            except ValueError:
                pass
        # Enum string props: normalise to lowercase
        if prop in ("strokeStyle", "textAlign", "verticalAlign"):
            props[prop] = v_lower
            continue
        if prop == "fillStyle":
            if v_lower not in _FILL_STYLE_VALUES:
                raise ValueError(
                    f"Invalid fillStyle '{v}'. Must be one of: {sorted(_FILL_STYLE_VALUES)}"
                )
            props[prop] = v_lower
            continue
        if prop == "corners":
            if v_lower not in _CORNER_VALUES:
                raise ValueError(
                    f"Invalid corners '{v}'. Must be one of: {sorted(_CORNER_VALUES)}"
                )
            props[prop] = v_lower
            continue
        if prop == "arrowType":
            if v_lower not in _ARROW_TYPE_VALUES:
                raise ValueError(
                    f"Invalid arrowType '{v}'. Must be one of: {sorted(_ARROW_TYPE_VALUES)}"
                )
            props[prop] = v_lower
            continue
        props[prop] = v
    return props


def _try_shape(
    line: str,
    shapes: dict[str, Any],
    subgraph: dict[str, Any] | None,
    inline_styles: dict[str, Any] | None = None,
) -> bool:
    """Try to match line as a shape declaration. Mutates shapes. Returns True on match.

    Raises ValueError for deprecated ellipse ((...)) and diamond {...} syntax.
    Trailing style props after the closing ] are captured into inline_styles.
    """
    if _RE_SHAPE_ELLIPSE.match(line):
        nid = _norm_id(line.split("(")[0].strip())
        raise ValueError(
            f"Ellipse syntax '((...))' is not supported. "
            f"Draw a rectangle and use whiteboard.style(ids=['{nid}'], style='shape:c') to change shape."
        )
    if _RE_SHAPE_DIAMOND.match(line):
        nid = _norm_id(line.split("{")[0].strip())
        raise ValueError(
            f"Diamond syntax '{{...}}' is not supported. "
            f"Draw a rectangle and use whiteboard.style(ids=['{nid}'], style='shape:d') to change shape."
        )
    if m := _RE_SHAPE_RECT.match(line):
        nid = _norm_id(m[1])
        shape: dict[str, Any] = {"label": m[2].replace("\\n", "\n"), "classes": []}
        shapes[nid] = shape
        if subgraph is not None:
            subgraph["members"].append(nid)
        trailing = m[3].strip()
        if inline_styles is not None and trailing:
            inline_styles[nid] = _parse_style_props(trailing)
        return True
    return False


def _try_edge(line: str, edges: list[dict[str, Any]]) -> bool:
    """Try to match line as an edge. Appends to edges. Returns True on match."""
    # Strip trailing inline style block {key:val,...} before pattern matching
    style_props: dict[str, Any] = {}
    bare_line = line
    if sm := re.search(r"\s*\{([^}]*)\}\s*$", line):
        style_str = sm.group(1)
        bare_line = line[: sm.start()]
        style_props = _parse_style_props(style_str)
    for pat, id_sfx, has_label, s_head, e_head, directed, stroke in _EDGE_PATTERNS:
        if m := pat.match(bare_line):
            if has_label:
                src, lbl, dst = _norm_id(m[1]), m[2] or "", _norm_id(m[3])
            else:
                src, dst, lbl = _norm_id(m[1]), _norm_id(m[2]), ""
            edge_id = f"edge-{src}-{dst}{id_sfx}" + (f"-{lbl}" if lbl else "")
            edge: dict[str, Any] = {
                "id": edge_id, "src": src, "dst": dst, "label": lbl,
                "directed": directed,
                "startArrowhead": s_head, "endArrowhead": e_head,
            }
            if stroke:
                edge["strokeStyle"] = stroke
            if style_props:
                edge["styleProps"] = style_props
            edges.append(edge)
            return True
    return False


def _expand_edge_chains(raw: str) -> list[str]:
    """Expand chained edge syntax into individual edge strings.

    ``"A --> B --> C"`` → ``["A --> B", "B --> C"]``

    Returns ``[raw]`` unchanged if there are fewer than two edge operators or
    if any token between operators contains a label delimiter (``|``).
    """
    ops = list(_EDGE_OP_RE.finditer(raw))
    if len(ops) < 2:
        return [raw]
    tokens: list[str] = []
    op_strs: list[str] = []
    prev_end = 0
    for m in ops:
        tokens.append(raw[prev_end : m.start()].strip())
        op_strs.append(m.group())
        prev_end = m.end()
    tokens.append(raw[prev_end:].strip())
    # Don't expand if labels are involved — let the existing parser handle it
    if any("|" in t for t in tokens):
        return [raw]
    return [f"{tokens[i]}{op_strs[i]}{tokens[i + 1]}" for i in range(len(op_strs))]


def parse_dsl(spec: str) -> dict[str, Any]:
    """Parse a Mermaid-compatible DSL string into a structured dict.

    Supported syntax:
        id["Label"]             rectangle (the only supported shape)
        id["Label"] bc:green    rectangle with inline style props
        id bc:green             style-only update (label unchanged)
        id1-->id2               directed edge
        id1-->|label|id2        labeled edge
        id1---id2               undirected edge
        id1<-->id2              bidirectional edge
        id1--o id2              dot arrowhead
        id1--x id2              bar arrowhead
        id1-.->id2              dashed directed edge
        id1-.-id2               dashed undirected edge
        subgraph name ["Label"] bounding group
          id1
        end

    Note: classDef/class and ellipse/diamond syntax are not supported.
    Use ``whiteboard.style`` to change colours and shapes after drawing.

    Args:
        spec: DSL string. Statements may be separated by newlines or semicolons.

    Returns:
        Dict with keys: ``shapes``, ``edges``, ``groups``, ``inline_styles``.
        ``inline_styles`` maps node IDs to parsed style prop dicts.
        Shape dicts have a ``label`` key (``None`` means "keep existing label").
    """
    shapes: dict[str, Any] = {}
    edges: list[dict[str, Any]] = []
    groups: dict[str, Any] = {}
    inline_styles: dict[str, Any] = {}
    current_subgraph: dict[str, Any] | None = None

    # Normalize real newlines inside quoted labels to the \n escape so they
    # survive line-splitting. Both `\n` (literal) and actual newlines work.
    spec = re.sub(r'"[^"]*"', lambda m: m.group(0).replace("\n", "\\n"), spec)

    raw_lines: list[str] = []
    for raw in re.split(r"[;\n]", spec):
        for chain_line in _expand_edge_chains(raw.strip()):
            raw_lines.extend(_expand_combined_shape_edge(chain_line))

    for raw in raw_lines:
        line = _prenorm_line(raw.strip())
        if not line or line.startswith("#") or line.startswith("%%"):
            continue
        if _RE_HEADER.match(line):
            continue

        if m := _RE_SUBGRAPH.match(line):
            current_subgraph = {"id": _norm_id(m[1]), "label": m[2] or m[1], "members": []}
            continue

        if line == "end" and current_subgraph is not None:
            groups[current_subgraph["id"]] = {
                "label": current_subgraph["label"],
                "members": current_subgraph["members"],
            }
            current_subgraph = None
            continue

        # Shape declaration (handles subgraph membership in one pass)
        if _try_shape(line, shapes, current_subgraph, inline_styles):
            continue

        # classDef / class — no longer supported
        if re.match(r"^(?:classDef|class)\s", line):
            raise ValueError(
                "classDef/class syntax is not supported. "
                "Use whiteboard.style() to apply colours and shapes after drawing."
            )

        # Bare node ID inside a subgraph — membership only
        if current_subgraph is not None and re.match(r"^[\w-]+$", line):
            current_subgraph["members"].append(_norm_id(line))
            continue

        # Edges
        if _try_edge(line, edges):
            continue

        # Bare id + inline style props (no bracket declaration):  a bc:green,sw:2
        if m := _RE_BARE_STYLE.match(line):
            nid = _norm_id(m[1])
            inline_styles[nid] = _parse_style_props(m[2])
            # Mark as style-only update (label=None means "keep existing label")
            if nid not in shapes:
                shapes[nid] = {"label": None, "classes": []}
            continue

        # Bare node ID fallback — create shape with label = node ID
        shapes[line] = {"label": line, "classes": []}

    return {"shapes": shapes, "edges": edges, "groups": groups, "inline_styles": inline_styles}


# ---------------------------------------------------------------------------
# DSL builder
# ---------------------------------------------------------------------------


def _build_dsl(state: dict[str, Any]) -> str:
    """Reconstruct DSL text from accumulated Python state.

    Emits shapes as rectangles only. Styling is not encoded in the DSL —
    it lives in the Excalidraw scene elements.
    """
    lines: list[str] = []
    for id_, shape in state["shapes"].items():
        label = shape["label"]
        if label is None:
            label = id_
        lines.append(f'{id_}["{label.replace(chr(10), "\\n")}"]')
    for edge in state["edges"]:
        src, dst = edge["src"], edge["dst"]
        lbl = f'|{edge["label"]}|' if edge["label"] else ""
        sh = edge.get("startArrowhead")
        eh = edge.get("endArrowhead", "arrow")
        dashed = edge.get("strokeStyle") == "dashed"
        if dashed and not edge.get("directed", True):
            lines.append(f"{src}-.-{dst}")
        elif dashed:
            lines.append(f"{src}-.->{lbl}{dst}")
        elif not edge.get("directed", True):
            lines.append(f"{src}---{dst}")
        elif sh == "arrow" and eh == "arrow":
            lines.append(f"{src}<-->{lbl}{dst}")
        elif eh == "dot":
            lines.append(f"{src} --o{lbl} {dst}")
        elif eh == "bar":
            lines.append(f"{src} --x{lbl} {dst}")
        else:
            lines.append(f"{src}-->{lbl}{dst}")
    for gid, group in state["groups"].items():
        lines.append(f'subgraph {gid} ["{group["label"]}"]')
        for mid in group["members"]:
            lines.append(f"  {mid}")
        lines.append("end")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DSL canvas element helpers
# ---------------------------------------------------------------------------


def _read_dsl_from_canvas() -> str:
    """Read the __otDSL text element from the canvas. Returns empty string if absent."""
    result = _browser_evaluate_json(
        "() => {"
        "  const el = Array.from(window.__drawApi.read()).find(e => e.id === '__otDSL');"
        "  return el ? el.text : '';"
        "}"
    )
    return result if isinstance(result, str) else ""


def _write_dsl_to_canvas(dsl_str: str) -> None:
    """Upsert the __otDSL text element on the canvas with current DSL content."""
    _browser_evaluate(f"() => window._upsert_dsl_element({json.dumps(dsl_str)})")


def _parse_dsl_to_state(dsl_str: str) -> dict[str, Any]:
    """Parse DSL string and return a session-compatible state dict."""
    parsed = parse_dsl(dsl_str)
    edge_keys = {_edge_key(e) for e in parsed["edges"]}
    return {
        "shapes": parsed["shapes"],
        "edges": parsed["edges"],
        "groups": parsed["groups"],
        "edge_keys": edge_keys,
        "canvas_max_y": 60.0,
    }


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------


def draw(*, input: str, board: str | None = None) -> str:
    """Add or update diagram elements from DSL. Always additive — never clears.

    **New nodes** get auto-layout positions. **Existing nodes** are upserted:
    only the properties explicitly passed are changed; position, size, and
    other styles on the live canvas are preserved.

    Semicolons are preferred as statement separators for agent calls (compact,
    no multi-line strings needed). Newlines are also accepted.

    Shapes:
        id["Label"]                           rectangle (only supported shape)
        id["Label"] bc:green,sw:2            rectangle with inline style props
        id bc:green                           style-only update (label unchanged)

    Inline style shorthands (comma-separated ``key:value``):
        bc  backgroundColor    sc  strokeColor     sw  strokeWidth
        ss  strokeStyle        r   roughness        o   opacity
        f   fontFamily         fs  fontSize         ta  textAlign
        va  verticalAlign      shape  shape type     x/y  position
        w/h width/height

    Named colours: green, blue, red, purple, yellow, orange, pink, gray, white, black

    Edges:
        a-->b                                 directed arrow
        a-->|label|b                          directed arrow with label
        a---b                                 undirected, no arrowheads
        a<-->b                                arrows at both ends
        a --o b                               dot/circle arrowhead at end
        a --x b                               bar/cross arrowhead at end
        a-.->b                                dashed directed arrow
        a-.->|label|b                         dashed directed arrow with label
        a-.-b                                 dashed undirected

    Subgraphs:
        subgraph name ["Label"]               bounding rect around members
          id1
          id2
        end

    Headers (ignored):
        flowchart TD
        graph LR

    Args:
        input: DSL string. Semicolons or newlines separate statements.
        board: Named board to draw on. Defaults to a CWD-keyed board.

    Returns:
        Summary like "+2 shapes, +1 edge(s): edge-a-b".

    Example:
        whiteboard.draw(input='a["Service A"];b["DB"];a-->b')
    """
    with LogSpan(span="excalidraw.draw") as s:
        # Load session state — no browser needed for draw
        state = _session.load(board)
        shapes = state["shapes"]
        edges = state["edges"]
        groups = state["groups"]
        edge_keys: set[tuple[str, str, str, str | None, str | None]] = state["edge_keys"]

        parsed = parse_dsl(input)
        inline_styles = parsed.get("inline_styles", {})

        # Auto-create nodes referenced in edges but not declared as shapes
        for edge in parsed["edges"]:
            for nid in (edge["src"], edge["dst"]):
                if nid not in parsed["shapes"] and nid not in shapes:
                    parsed["shapes"][nid] = {"label": nid, "classes": []}

        # Separate new shapes from existing shapes in one pass
        new_shapes: dict[str, Any] = {}
        existing_shape_updates: dict[str, Any] = {}
        for id_, sh in parsed["shapes"].items():
            if id_ in shapes:
                existing_shape_updates[id_] = sh
            else:
                new_shapes[id_] = sh
        new_groups = {gid for gid in parsed["groups"] if gid not in groups}

        new_edges_to_commit: list[tuple[tuple[str, str, str, str | None, str | None], dict[str, Any]]] = []
        for e in parsed["edges"]:
            key = _edge_key(e)
            if key not in edge_keys:
                new_edges_to_commit.append((key, e))

        # Update state: shapes (upsert)
        for id_, shape in parsed["shapes"].items():
            if shape.get("label") is not None:
                shapes[id_] = shape
            elif id_ not in shapes:
                shapes[id_] = {"label": id_, "classes": []}

        # Update state: groups
        groups.update(parsed["groups"])

        # Update state: edges
        for key, e in new_edges_to_commit:
            edges.append(e)
            edge_keys.add(key)

        # Track canvas_max_y for additive positioning (used by next draw call)
        base_y = state.get("canvas_max_y", 60.0) + 40 if new_shapes else state.get("canvas_max_y", 60.0)
        col_y: dict[str | None, float] = {}
        if new_shapes:
            subgraph_of: dict[str, str | None] = dict.fromkeys(new_shapes, None)
            for gid, group in parsed["groups"].items():
                for mid in group["members"]:
                    if mid in new_shapes:
                        subgraph_of[mid] = gid
            next_x = 100.0
            col_x: dict[str | None, float] = {}
            for id_ in new_shapes:
                sg = subgraph_of[id_]
                if sg not in col_x:
                    col_x[sg] = next_x
                    col_y[sg] = base_y
                    next_x += 300.0
            for id_ in new_shapes:
                sg = subgraph_of[id_]
                col_y[sg] += 100.0

        new_canvas_max_y = max(col_y.values()) if col_y else state.get("canvas_max_y", 60.0)

        # Count updated shapes for summary (one per shape, not per attribute)
        patch_count = sum(
            1
            for id_, shape in existing_shape_updates.items()
            if (
                shape.get("label") is not None
                and shape["label"] != shapes.get(id_, {}).get("label", "")
            ) or inline_styles.get(id_)
        )

        # Save updated state to session file
        _session.save({
            "shapes": shapes,
            "edges": edges,
            "groups": groups,
            "edge_keys": edge_keys,
            "canvas_max_y": new_canvas_max_y,
        }, board)

        # Push incremental update to browser if connected
        if _tab is not None:
            with contextlib.suppress(Exception):
                _rerender_from_state({"shapes": shapes, "edges": edges, "groups": groups})

        new_edge_ids = [e["id"] for _, e in new_edges_to_commit]
        edge_msg = f", +{len(new_edge_ids)} edge(s): {', '.join(new_edge_ids)}" if new_edge_ids else ""
        updated_msg = f", {patch_count} updated" if patch_count else ""
        group_msg = f", +{len(new_groups)} group(s)" if new_groups else ""

        s.add("newShapes", len(new_shapes))
        s.add("board", board or "cwd")
        return f"+{len(new_shapes)} shapes{updated_msg}{edge_msg}{group_msg}"


# ---------------------------------------------------------------------------
# Note DSL parser
# ---------------------------------------------------------------------------

_RE_NOTE_BLOCK = re.compile(
    r"^\s*(\w+)\[(\w+):[ \t]*\n(.*?)\]$", re.DOTALL | re.MULTILINE
)

_NOTE_RENDERERS: dict[str, Any] = {}


def _get_note_renderers() -> dict[str, Any]:
    if not _NOTE_RENDERERS:
        from otdev.tools._excalidraw.renderers import (
            render_note,
            render_sequence,
            render_table,
            render_timeline,
            render_tree,
        )
        _NOTE_RENDERERS.update({
            "table": render_table,
            "tree": render_tree,
            "seq": render_sequence,
            "timeline": render_timeline,
            "note": render_note,
        })
    return _NOTE_RENDERERS


def _parse_note_blocks(spec: str) -> list[dict[str, Any]]:
    """Parse id[type:\\n content] blocks from a note DSL string."""
    # Normalize: CRLF → LF, dedent common indentation (handles indented triple-quoted
    # strings), strip trailing whitespace per line (handles spaces before closing ]).
    spec = spec.replace("\r\n", "\n")
    spec = textwrap.dedent(spec)
    spec = "\n".join(line.rstrip() for line in spec.splitlines())
    blocks = []
    for m in _RE_NOTE_BLOCK.finditer(spec):
        blocks.append({"id": m[1], "type": m[2], "content": m[3]})
    return blocks


# ---------------------------------------------------------------------------
# Note tool constants
# ---------------------------------------------------------------------------

_NOTE_CHAR_W = 8.4
_NOTE_LINE_H = 18
_NOTE_FONT_SIZE = 14
_NOTE_PADDING = 20
_NOTE_DEFAULT_BG = "#f5f5dc"


def note(*, input: str, background: str = _NOTE_DEFAULT_BG) -> str:
    """Insert ASCII-rendered text annotations onto the canvas.

    Parses tagged blocks and renders each as a code-font rectangle below
    any existing diagram content.

    Each block uses the syntax:
        id[type:
        content...
        ]

    Block types:

    table — CSV grid, first row is the header:
        t[table:
        Name,Role
        Alice,Dev
        Bob,QA
        ]

    tree — hierarchy with '-' depth prefix (one char = one level):
        tr[tree:
        root/
        -src/
        --main.py
        -tests/
        ]

    seq — sequence diagram, one message per line:
        s[seq:
        Client -> Server: request
        Server -> DB: query
        DB -> Server: rows
        Server -> Client:
        ]

    timeline — Gantt bars, one task per line as 'name,start,duration':
        g[timeline:
        Design,1,4
        Build,3,8
        Test,9,4
        ]

    note — plain word-wrapped paragraph text:
        n[note:
        This is a plain text annotation.
        ]

    Args:
        input: Note DSL string with one or more blocks.
        background: Background color for note boxes (default beige #f5f5dc).

    Returns:
        Summary of notes inserted.

    Example:
        whiteboard.note(input='''
        t[table:
        Name,Role
        Alice,Dev
        Bob,QA
        ]
        ''')
    """
    with LogSpan(span="excalidraw.note") as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        blocks = _parse_note_blocks(input)
        if not blocks:
            return "Error: no valid note blocks found (expected id[type:\\ncontent\\n])"

        renderers = _get_note_renderers()

        # Place notes below existing canvas content
        base_y = _get_canvas_max_y() + 100

        shape_payloads = []
        y_cursor = base_y
        for block in blocks:
            renderer = renderers.get(block["type"])
            if renderer is None:
                supported = ", ".join(renderers.keys())
                return f"Error: unknown note type '{block['type']}'. Supported: {supported}"
            rendered = renderer(block["content"])
            if not rendered:
                continue
            if rendered.startswith("Error:"):
                return f"Error in block '{block['id']}': {rendered}"

            lines = rendered.splitlines()
            w = max(len(line) for line in lines) * _NOTE_CHAR_W + _NOTE_PADDING * 2
            h = len(lines) * _NOTE_LINE_H + _NOTE_PADDING * 2
            style = {
                "backgroundColor": background,
                "strokeColor": "#aaaaaa",
                "strokeWidth": 1,
                "fontFamily": 3,
                "fontSize": _NOTE_FONT_SIZE,
                "textAlign": "left",
                "verticalAlign": "top",
                "color": "#1e1e1e",
            }
            shape_payloads.append(
                {"id": block["id"], "label": rendered,
                 "x": 500.0, "y": y_cursor, "w": w, "h": h,
                 "shape": "rectangle", "styleProps": style}
            )
            y_cursor += h + 20

        inserted = len(shape_payloads)
        if inserted:
            state = _session.load()
            shapes = state["shapes"]
            max_y = float(state.get("canvas_max_y", 60.0))
            for payload in shape_payloads:
                shapes[payload["id"]] = {
                    "label": payload["label"],
                    "classes": [],
                    "shape": payload["shape"],
                    "style": payload["styleProps"],
                }
                max_y = max(max_y, float(payload["y"]) + float(payload["h"]))
            _session.save({
                "shapes": shapes,
                "edges": state["edges"],
                "groups": state["groups"],
                "edge_keys": state["edge_keys"],
                "canvas_max_y": max_y,
            })

        for payload in shape_payloads:
            _js_batch_draw(shapes=[payload], edges=[], subgraphs=[])

        s.add("inserted", inserted)
        return f"inserted {inserted} note(s)"


def embed_dsl() -> str:
    """Embed the current DSL as a note element on the canvas.

    Inserts a grey code-font box with id ``dsl`` containing the full DSL
    text. Calling again overwrites the previous embed (idempotent). The element
    is excluded from save() snapshots.

    Returns:
        Summary such as "embedded DSL (12 lines)".

    Example:
        excalidraw.embed_dsl()
    """
    with LogSpan(span="excalidraw.embed_dsl") as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        dsl_text = _build_dsl(_session.load())
        if not dsl_text.strip():
            return "nothing to embed — canvas is empty"

        lines = dsl_text.splitlines()
        w = max(len(line) for line in lines) * _NOTE_CHAR_W + _NOTE_PADDING * 2
        h = len(lines) * _NOTE_LINE_H + _NOTE_PADDING * 2
        style = {
            "backgroundColor": "#e8e8e8",
            "strokeColor": "#aaaaaa",
            "strokeWidth": 1,
            "fontFamily": 3,
            "fontSize": _NOTE_FONT_SIZE,
            "textAlign": "left",
            "verticalAlign": "top",
            "color": "#555555",
        }
        payload = {
            "id": "dsl", "label": dsl_text,
            "x": 500.0, "y": _get_canvas_max_y() + 100,
            "w": w, "h": h, "shape": "rectangle", "styleProps": style,
        }
        _js_batch_draw(shapes=[payload], edges=[], subgraphs=[])

        n = len(lines)
        s.add("lines", n)
        return f"embedded DSL ({n} lines)"


def erase(*, ids: list[str], board: str | None = None) -> str:
    """Remove individual elements from the canvas and Python state.

    Bound children (shape text, arrow labels) are removed automatically.
    Silently ignores IDs that are not currently rendered.

    **Edge ID format:** ``edge-{src}-{dst}[-{type-suffix}][-{label}]``

    Type suffixes: ``-bidir`` (↔), ``-und`` (undirected ---),
    ``-dashed`` (-.->), ``-dashed-und`` (-.-), ``-dot`` (--o), ``-bar`` (--x).

    Examples::

        a-->b               →  "edge-a-b"
        a-->|send|b         →  "edge-a-b-send"
        a<-->b              →  "edge-a-b-bidir"
        a---b               →  "edge-a-b-und"
        a-.->b              →  "edge-a-b-dashed"
        a-.->|Metrics|b     →  "edge-a-b-dashed-Metrics"

    Use ``whiteboard.draw`` output to see the generated edge IDs after drawing.

    Args:
        ids: List of element IDs to remove.
        board: Named board to operate on. Defaults to the CWD-keyed board.

    Returns:
        Summary such as "erased 2 element(s)".

    Example:
        excalidraw.erase(ids=["a", "edge-a-b"])
    """
    with LogSpan(span="excalidraw.erase", ids=ids) as s:
        # Load session state — no browser needed for erase
        state = _session.load(board)
        shapes = state["shapes"]
        edges = state["edges"]
        edge_keys: set[tuple[str, str, str, str | None, str | None]] = state["edge_keys"]

        id_set = set(ids)
        edge_ids = {e["id"] for e in edges}

        # Only erase IDs present in session state
        to_erase = [id_ for id_ in ids if id_ in shapes or id_ in edge_ids]
        shape_ids_to_erase = [id_ for id_ in ids if id_ in shapes]
        if not to_erase:
            return "erased 0 element(s)"

        # Find edges that become dangling (src or dst is being erased)
        orphaned_edge_ids = [
            e["id"] for e in edges
            if e["src"] in id_set or e["dst"] in id_set
        ]

        # Remove shapes
        for id_ in shape_ids_to_erase:
            shapes.pop(id_, None)

        # Remove edges by ID or dangling src/dst
        keys_to_remove = {
            _edge_key(e)
            for e in edges
            if e["id"] in id_set or e["src"] in id_set or e["dst"] in id_set
        }
        edges[:] = [
            e for e in edges
            if e["id"] not in id_set
            and e["src"] not in id_set
            and e["dst"] not in id_set
        ]
        edge_keys.difference_update(keys_to_remove)

        _session.save({
            "shapes": shapes,
            "edges": edges,
            "groups": state["groups"],
            "edge_keys": edge_keys,
            "canvas_max_y": state.get("canvas_max_y", 60.0),
        }, board)

        # Delete erased elements from browser canvas if connected
        if _tab is not None:
            all_erase_ids = to_erase + [eid for eid in orphaned_edge_ids if eid not in to_erase]
            if all_erase_ids:
                with contextlib.suppress(Exception):
                    _browser_evaluate(f"() => window._batch_erase({json.dumps(all_erase_ids)})")

        n = len(to_erase)
        dangling = len(orphaned_edge_ids)
        s.add("erased", n)
        s.add("danglingEdges", dangling)
        if dangling:
            return f"erased {n} element(s), {dangling} dangling edge(s) removed"
        return f"erased {n} element(s)"


def save(*, file: str) -> str:
    """Save current diagram to a native ``.excalidraw`` JSON file.

    Writes the full Excalidraw scene (including user-added elements and
    live positions) plus a ``__otDSL`` text element that stores the
    logical DSL for future ``whiteboard.load`` / ``whiteboard.sync`` calls.

    The saved file can be opened directly in excalidraw.com.

    Args:
        file: Output file path (relative to project root). Conventionally
              uses the ``.excalidraw`` extension.

    Returns:
        Summary of elements saved.

    Example:
        excalidraw.save(file="diagrams/arch.excalidraw")
    """
    with LogSpan(span="excalidraw.save", file=file) as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        # Write current DSL as __otDSL element so load() can restore Python state
        dsl_str = _build_dsl(_session.load())
        if dsl_str.strip():
            _write_dsl_to_canvas(dsl_str)

        elements = _browser_evaluate_json(
            "() => Array.from(window.__drawApi.read())"
        )
        if not isinstance(elements, list):
            return f"Error: could not read scene elements: {elements}"

        native = {
            "type": "excalidraw",
            "version": 2,
            "source": "https://excalidraw.com",
            "elements": elements,
            "appState": {"viewBackgroundColor": "#ffffff"},
            "files": {},
        }

        out_path = resolve_cwd_path(file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(native, indent=2), encoding="utf-8")

        n = len([e for e in elements if not e.get("isDeleted", False)])
        s.add("elementCount", n)
        return f"saved {n} elements to {file}"


def load(*, file: str) -> str:
    """Restore diagram from a native ``.excalidraw`` file.

    Loads the full Excalidraw scene and restores Python DSL state from the
    embedded ``__otDSL`` element (written by ``whiteboard.save``). If the file was
    not created by ``whiteboard.save`` and lacks a ``__otDSL`` element, Python state
    will be empty (call ``whiteboard.sync`` after manually adding a DSL element).

    Args:
        file: Path to a ``.excalidraw`` file.

    Returns:
        Summary of elements loaded.

    Example:
        excalidraw.load(file="diagrams/arch.excalidraw")
    """
    with LogSpan(span="excalidraw.load", file=file) as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        src_path = resolve_cwd_path(file)
        if not src_path.exists():
            return f"Error: file not found: {file}"

        raw = src_path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return f"Error: invalid JSON in {file}: {exc}"

        if not isinstance(data, dict) or data.get("type") != "excalidraw":
            return (
                "Error: not a valid .excalidraw file - "
                "expected {\"type\": \"excalidraw\", ...}"
            )

        elements = data.get("elements", [])
        elements_json = json.dumps(elements)

        # Restore canvas
        _browser_evaluate(
            f"() => {{"
            f"  window.__drawElements = {{}};"
            f"  for (const el of {elements_json}) window.__drawElements[el.id] = el;"
            f"  window.__drawApi._raw.updateScene({{ elements: {elements_json} }});"
            f"}}"
        )

        # Sync Python state from __otDSL element and save to session file
        dsl_str = _read_dsl_from_canvas()
        if dsl_str:
            new_state = _parse_dsl_to_state(dsl_str)
            _session.save(new_state)
            warning = ""
        else:
            new_state = {"shapes": {}, "edges": [], "groups": {}, "edge_keys": set(), "canvas_max_y": 60.0}
            _session.save(new_state)
            warning = " [warning: no __otDSL element — Python state is empty; call whiteboard.sync() after adding one]"

        n_shapes = len(new_state["shapes"])
        n_edges = len(new_state["edges"])
        n_elements = len(elements)
        s.add("shapes", n_shapes)
        s.add("edges", n_edges)
        if warning:
            s.add("warning", "no __otDSL element")
            return f"loaded {n_elements} element(s){warning}"
        return f"loaded {n_shapes} shapes, {n_edges} edges"


def sync() -> str:
    """Sync Python DSL state from the ``__otDSL`` canvas element.

    Reads the ``__otDSL`` text element from the current Excalidraw canvas
    and updates Python state. Use this after:

    - Loading a file directly in the Excalidraw UI (File → Open)
    - Drag-and-dropping an ``.excalidraw`` file onto the canvas
    - Any operation that bypasses ``whiteboard.load``

    Returns:
        Summary like ``"synced: 4 shapes, 3 edges"``.

    Example:
        excalidraw.sync()
    """
    with LogSpan(span="excalidraw.sync") as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        dsl_str = _read_dsl_from_canvas()
        if not dsl_str:
            return (
                "sync: no __otDSL element found on canvas. "
                "Canvas may have been created outside whiteboard, or whiteboard.save() was not used."
            )

        new_state = _parse_dsl_to_state(dsl_str)
        _session.save(new_state)

        n_shapes = len(new_state["shapes"])
        n_edges = len(new_state["edges"])
        s.add("shapes", n_shapes)
        s.add("edges", n_edges)
        return f"synced: {n_shapes} shapes, {n_edges} edges"


def help() -> str:
    """Return the full DSL and style reference. Call this before using whiteboard.draw or whiteboard.style.

    Returns the complete whiteboard DSL syntax and style shorthand reference as plain text.
    No browser interaction needed.

    Returns:
        Full DSL and style reference as a plain-text string.

    Example:
        excalidraw.help()
    """
    return _load_js("dsl-reference.md")


def style(*, ids: list[str], style: str) -> str:
    """Apply visual style properties to existing canvas elements in bulk.

    Applies Excalidraw style properties to the named elements. Never touches
    ``_dsl_state`` — styling is a purely visual operation.

    Style string is comma-separated ``key:value`` pairs using the shorthand
    table shared with ``whiteboard.draw`` inline styles:

    +---------+----------------------+------------------------------------------+
    | Key     | Excalidraw property  | Notes                                    |
    +=========+======================+==========================================+
    | ``bc``  | backgroundColor      | hex or named colour                      |
    | ``sc``  | strokeColor          | hex or named colour                      |
    | ``sw``  | strokeWidth          | number                                   |
    | ``ss``  | strokeStyle          | ``solid``, ``dashed``, ``dotted``        |
    | ``r``   | roughness            | 0-2                                      |
    | ``o``   | opacity              | 0-100                                    |
    | ``f``   | fontFamily           | ``hand``, ``normal``, ``mono``           |
    | ``fs``  | fontSize             | number                                   |
    | ``ta``  | textAlign            | ``left``, ``center``, ``right``          |
    | ``va``  | verticalAlign        | ``top``, ``middle``, ``bottom``          |
    | ``shape``| element type        | ``r``=rect, ``d``=diamond, ``c``=circle  |
    | ``x``/``y`` | position         | pixels                                   |
    | ``w``/``h`` | width/height     | pixels                                   |
    +---------+----------------------+------------------------------------------+

    Shape changes (``shape:d``, ``shape:c``) use delete+recreate with the same
    ID so arrow connections survive.

    Named colours: ``green``, ``blue``, ``red``, ``purple``, ``yellow``,
    ``orange``, ``pink``, ``gray``, ``white``, ``black``.

    Args:
        ids:   List of node IDs to style.
        style: Style string, e.g. ``"bc:#bbf7d0,sc:#16a34a,sw:2"``.

    Returns:
        Summary like ``"styled 3 element(s)"``.

    Example:
        excalidraw.style(ids=["a", "b"], style="bc:green,sc:#16a34a")
        excalidraw.style(ids=["c"], style="shape:d")
    """
    with LogSpan(span="excalidraw.style", ids=ids, style=style) as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        if not style.strip():
            return "Error: style string is empty"

        style_props = _parse_style_props(style)
        if not style_props:
            return "Error: no valid style properties parsed from style string"

        matched = _js_style_elements(ids, style_props)

        s.add("count", matched)
        return f"styled {matched} element(s)"


_VALID_READ_SCENE_LEVELS = {"min", "default", "full", "debug"}


def read_scene(*, info: str = "default") -> str:
    """Return a structured text summary of all canvas elements.

    Inspects the live Excalidraw canvas and returns a report listing every
    shape and edge with their properties. Use this to verify ``draw()``,
    ``style()``, and ``erase()`` results without taking a screenshot.

    Detail levels:

    - ``info="min"`` — One-line summary: ``"Scene: N shapes, M edges"``
    - ``info="default"`` — Per-element listing with id, type, label, bc, sc,
      text-sc, groupIds. Edges show arrowheads and stroke style.
    - ``info="full"`` — All of default plus sw, ss, roughness, opacity,
      fillStyle, corners, fontSize, fontFamily, textAlign, verticalAlign,
      x, y, w, h. Edges additionally show sc, sw, opacity, arrowType,
      position, and dimensions.

    A ``⚠ TEXT=BG`` warning appears when a shape's text strokeColor matches
    its backgroundColor, which makes the label invisible.

    Args:
        info: Detail level — ``"min"``, ``"default"``, ``"full"``, or ``"debug"``.

    Returns:
        Text summary of the scene at the requested detail level.

    Example:
        whiteboard.read_scene()
        whiteboard.read_scene(info="full")
        whiteboard.read_scene(info="min")
        whiteboard.read_scene(info="debug")
    """
    if info not in _VALID_READ_SCENE_LEVELS:
        raise ValueError(
            f"info={info!r} is not valid. Use 'min', 'default', 'full', or 'debug'."
        )

    with LogSpan(span="excalidraw.read_scene", info=info) as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        result = _browser_evaluate_json(
            f"() => window._read_scene({json.dumps(info)})"
        )
        if not isinstance(result, str):
            result = str(result)
        s.add("result_length", len(result) if result else 0)
        return result


def share(*, board: str | None = None) -> str:
    """Generate a shareable Excalidraw link for the current canvas.

    Encrypts the full scene client-side (AES-GCM, 128-bit) and uploads it
    to Excalidraw's storage, returning a URL that anyone can open in a browser.

    The encryption and upload use the same protocol as Excalidraw's own
    "Export to Link" feature — end-to-end encrypted, key never sent to server.

    Returns:
        Shareable URL like ``https://excalidraw.com/#json={id},{key}``.

    Example:
        excalidraw.share()
    """
    with LogSpan(span="excalidraw.share") as s:
        # Load session state and render to browser
        state = _session.load(board)
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err
        _rerender_from_state(state)

        # Read scene elements
        elements = _browser_evaluate_json(
            "() => Array.from(window.__drawApi.read())"
        )
        if not isinstance(elements, list):
            return f"Error: could not read scene elements: {elements}"

        # Build native excalidraw payload
        payload_obj = {
            "type": "excalidraw",
            "version": 2,
            "source": "https://excalidraw.com",
            "elements": elements,
            "appState": {"viewBackgroundColor": "#ffffff"},
            "files": {},
        }
        payload_json_str = json.dumps(payload_obj)

        # Encrypt client-side via Web Crypto API (AES-GCM, 128-bit key)
        # Return object directly (not JSON.stringify) so _browser_evaluate_json
        # can parse it without double-encoding issues.
        encrypt_js = (
            "async () => {"
            "  const data = " + json.dumps(payload_json_str) + ";"
            "  const enc = new TextEncoder().encode(data);"
            "  const key = await crypto.subtle.generateKey("
            "    {name: 'AES-GCM', length: 128}, true, ['encrypt']);"
            "  const iv = crypto.getRandomValues(new Uint8Array(12));"
            "  const ct = await crypto.subtle.encrypt({name: 'AES-GCM', iv}, key, enc);"
            "  const exportedKey = await crypto.subtle.exportKey('raw', key);"
            "  const combined = new Uint8Array(iv.byteLength + ct.byteLength);"
            "  combined.set(iv);"
            "  combined.set(new Uint8Array(ct), iv.byteLength);"
            "  const b64 = buf => btoa(String.fromCharCode(...new Uint8Array(buf)));"
            "  const keyB64 = b64(exportedKey)"
            "    .replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=/g,'');"
            "  return {data: b64(combined), key: keyB64};"
            "}"
        )

        enc_data = _browser_evaluate_json(encrypt_js)
        if not isinstance(enc_data, dict) or "data" not in enc_data or "key" not in enc_data:
            return f"Error: unexpected encryption result: {enc_data}"

        # Upload to Excalidraw storage using Python urllib (bypasses CORS)
        import urllib.error
        import urllib.request

        req_body = json.dumps({"data": enc_data["data"]}).encode("utf-8")
        req = urllib.request.Request(
            "https://json.excalidraw.com/api/v2/post/",
            data=req_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            return f"Error: upload failed — {exc}"
        except (json.JSONDecodeError, ValueError) as exc:
            return f"Error: unexpected response from Excalidraw storage — {exc}"

        share_id = resp_data.get("id", "")
        if not share_id:
            return f"Error: no ID in upload response: {resp_data}"

        key = enc_data["key"]
        url = f"https://excalidraw.com/#json={share_id},{key}"
        s.add("url", url)
        return url


def clear(*, board: str | None = None) -> str:
    """Delete the session file for the given board and optionally clear the canvas.

    When called without a ``board`` argument, clears the CWD-keyed board.
    If a named board is given, only that board's session file is deleted (no browser action).

    Returns:
        Confirmation message.

    Example:
        excalidraw.clear()
        excalidraw.clear(board='arch')
    """
    with LogSpan(span="excalidraw.clear") as s:
        _session.clear_board(board)
        s.add("board", board or "cwd")

        # Also clear the live canvas when using the default CWD board and browser is open
        if board is None and _tab is not None:
            with contextlib.suppress(Exception):
                _browser_evaluate("() => window.__drawApi.clear()")

        return "canvas cleared"


def scroll(*, dx: int = 0, dy: int = 0) -> str:
    """Pan the canvas by (dx, dy) pixels.

    Args:
        dx: Horizontal scroll offset in pixels (positive = right).
        dy: Vertical scroll offset in pixels (positive = down).

    Returns:
        Confirmation message.

    Example:
        excalidraw.scroll(dx=200, dy=0)
    """
    with LogSpan(span="excalidraw.scroll", dx=dx, dy=dy) as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        _browser_evaluate(f"() => window.__drawApi.scroll({dx}, {dy})")
        return f"scrolled dx={dx}, dy={dy}"


def zoom(*, level: float) -> str:
    """Set zoom level. Pass 0 to fit all elements in view.

    Args:
        level: Zoom level (1.0 = 100%, 0.5 = 50%). Pass 0 to fit all.

    Returns:
        Confirmation message.

    Example:
        excalidraw.zoom(level=0.5)
        excalidraw.zoom(level=0)   # fit all
    """
    if level < 0:
        return "Error: zoom level must be >= 0 (use 0 to fit all)"

    with LogSpan(span="excalidraw.zoom", zoom=level) as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        _browser_evaluate(f"() => window.__drawApi.zoom({level})")
        if level == 0:
            return "zoomed to fit all elements"
        return f"zoom set to {level}"


def fit() -> str:
    """Fit all elements in view.

    Returns:
        Confirmation message.

    Example:
        excalidraw.fit()
    """
    return zoom(level=0)


_ELK_CDN = "https://unpkg.com/elkjs@0.11.0/lib/elk.bundled.js"
_ELK_DIRECTIONS = {"RIGHT", "LEFT", "DOWN", "UP"}
_ELK_ALGORITHMS = {"layered", "stress", "mrtree", "radial", "force"}
_ELK_NODE_PLACEMENTS = {"BRANDES_KOEPF", "NETWORK_SIMPLEX", "LINEAR_SEGMENTS", "SIMPLE"}
_ELK_CROSSING_MINS = {"LAYER_SWEEP", "MEDIAN_LAYER_SWEEP", "NONE"}
_ELK_CYCLE_BREAKINGS = {"GREEDY", "DEPTH_FIRST", "MODEL_ORDER"}


def layout(
    *,
    direction: str = "DOWN",
    gap_layer: int = 80,
    gap_node: int = 40,
    algorithm: str = "layered",
    node_placement: str = "NETWORK_SIMPLEX",
    crossing_min: str = "LAYER_SWEEP",
    cycle_breaking: str = "GREEDY",
    arrow_type: str | None = None,
    elk_options: dict[str, str] | None = None,
    board: str | None = None,
) -> str:
    """Apply ELK.js graph layout to the current whiteboard.

    Loads ELK.js from CDN (once), runs the chosen layout algorithm in the
    browser, patches every shape's position, recomputes subgraph bounding
    boxes, and calls ``wb.fit()`` to zoom-to-fit.

    Args:
        direction:      Layout direction — ``RIGHT``, ``LEFT``, ``DOWN`` (default), ``UP``.
        gap_layer:      Gap between layers in pixels (layered only).
        gap_node:       Gap between nodes in the same layer in pixels.
        algorithm:      ELK algorithm:

                        - ``layered`` (default) — best for DAGs and pipelines; ranks
                          nodes into layers, minimises edge crossings.
                        - ``stress`` — spring-based; good for undirected/exploratory
                          graphs. Can overlap nodes on dense directed graphs; increase
                          ``gap_node`` to spread them out.
                        - ``mrtree`` — minimal-spanning-tree layout; good for trees
                          with a clear single root.
                        - ``radial`` — radial tree layout centred on one node.
                        - ``force`` — force-directed; good for clustered undirected
                          graphs.

        node_placement: Node placement strategy (layered only) —
                        ``NETWORK_SIMPLEX`` (default), ``BRANDES_KOEPF``,
                        ``LINEAR_SEGMENTS``, ``SIMPLE``.
        crossing_min:   Crossing minimisation (layered only) —
                        ``LAYER_SWEEP`` (default), ``MEDIAN_LAYER_SWEEP``, ``NONE``.
        cycle_breaking: Cycle breaking (layered only) —
                        ``GREEDY`` (default), ``DEPTH_FIRST``, ``MODEL_ORDER``.
        arrow_type:     After layout, patch all positioned arrows to the given type:
                        ``None`` (default, leave per-edge style unchanged),
                        ``"curve"``, ``"sharp"``, or ``"elbow"``.
        elk_options:    Dict of raw ELK key→value pairs merged last (overrides
                        all named params).

    Returns:
        Summary string, e.g. ``"layout applied to 12 nodes"``.

    Example:
        wb.layout()
        wb.layout(direction="RIGHT", gap_layer=120, gap_node=60)
        wb.layout(algorithm="stress")
    """
    direction = direction.upper()
    algorithm = algorithm.lower()
    node_placement = node_placement.upper()
    crossing_min = crossing_min.upper()
    cycle_breaking = cycle_breaking.upper()

    if direction not in _ELK_DIRECTIONS:
        return f"Error: direction must be one of {sorted(_ELK_DIRECTIONS)}"
    if algorithm not in _ELK_ALGORITHMS:
        return f"Error: algorithm must be one of {sorted(_ELK_ALGORITHMS)}"
    if node_placement not in _ELK_NODE_PLACEMENTS:
        return f"Error: node_placement must be one of {sorted(_ELK_NODE_PLACEMENTS)}"
    if crossing_min not in _ELK_CROSSING_MINS:
        return f"Error: crossing_min must be one of {sorted(_ELK_CROSSING_MINS)}"
    if cycle_breaking not in _ELK_CYCLE_BREAKINGS:
        return f"Error: cycle_breaking must be one of {sorted(_ELK_CYCLE_BREAKINGS)}"
    if arrow_type is not None and arrow_type not in _ARROW_TYPE_VALUES:
        return f"Error: arrow_type must be None or one of {sorted(_ARROW_TYPE_VALUES)}"

    with LogSpan(span="excalidraw.layout", direction=direction, algorithm=algorithm) as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        # Load session state for shape labels and group membership
        layout_state = _session.load(board)

        # Read the live scene: nodes, edges, selection, and group membership
        scene_js = _browser_evaluate_json("""() => {
  const elements = window.__drawApi ? window.__drawApi.read() : Object.values(window.__drawElements || {});
  const raw = window.__drawApi ? window.__drawApi._raw : null;
  const appState = raw ? (raw.state || (raw.getAppState ? raw.getAppState() : {})) : {};
  const selectedIds = Object.keys(appState.selectedElementIds || {});
  const nodes = [];
  const edges = [];
  for (const el of elements) {
    if (el.isDeleted) continue;
    if (el.type === 'text') continue;
    if (el.type === 'arrow') {
      if (el.startBinding && el.endBinding) {
        edges.push({
          id: el.id,
          src: el.startBinding.elementId,
          dst: el.endBinding.elementId,
        });
      }
    } else {
      nodes.push({id: el.id, w: el.width || 160, h: el.height || 60, groupIds: el.groupIds || [], x: el.x || 0, y: el.y || 0});
    }
  }
  return {nodes, edges, selectedIds};
}""")
        if not isinstance(scene_js, dict):
            return "Error: could not read live scene"

        scene_nodes: list[dict[str, Any]] = scene_js.get("nodes", [])
        scene_edges: list[dict[str, Any]] = scene_js.get("edges", [])
        selected_ids: list[str] = scene_js.get("selectedIds", [])

        # Determine scope: selection or all
        use_selection = len(selected_ids) > 0
        # Save full node map before selection filter (needed to look up positions of
        # non-selected nodes when fixing boundary arrows later).
        all_node_map: dict[str, dict[str, Any]] = {n["id"]: n for n in scene_nodes}
        if use_selection:
            selected_set = set(selected_ids)
            scene_nodes = [n for n in scene_nodes if n["id"] in selected_set]

        if not scene_nodes:
            return "nothing to layout — canvas has no eligible shapes"

        # ELK layout offset: for a selection layout anchor to the selection's top-left
        # so nodes stay roughly in place; for a full layout use the standard canvas padding.
        if use_selection and scene_nodes:
            layout_offset_x = float(min(n.get("x", 0) for n in scene_nodes))
            layout_offset_y = float(min(n.get("y", 0) for n in scene_nodes))
        else:
            layout_offset_x = 60.0
            layout_offset_y = 60.0

        # Collapse Excalidraw groups into atomic ELK nodes
        # Elements sharing a groupId are treated as a single node (bounding box of members)
        group_to_members: dict[str, list[dict[str, Any]]] = {}
        ungrouped: list[dict[str, Any]] = []
        for n in scene_nodes:
            gids = n.get("groupIds") or []
            if gids:
                gid = gids[0]  # primary group
                group_to_members.setdefault(gid, []).append(n)
            else:
                ungrouped.append(n)

        # Map each element id → ELK node id (for edge lookup)
        elem_to_elk: dict[str, str] = {}
        elk_nodes = []
        node_dims: dict[str, tuple[int, int]] = {}

        for n in ungrouped:
            eid = n["id"]
            w, h = int(n["w"]), int(n["h"])
            elk_nodes.append({"id": eid, "width": w, "height": h})
            node_dims[eid] = (w, h)
            elem_to_elk[eid] = eid

        for gid, members in group_to_members.items():
            min_x = min_y = float("inf")
            max_x = max_y = float("-inf")
            for m in members:
                min_x = min(min_x, 0.0)  # positions unknown here, use sizes
                max_x = max(max_x, float(m["w"]))
                min_y = min(min_y, 0.0)
                max_y = max(max_y, float(m["h"]))
                elem_to_elk[m["id"]] = gid
            w, h = int(max_x - min_x) or 160, int(max_y - min_y) or 60
            elk_nodes.append({"id": gid, "width": w, "height": h})
            node_dims[gid] = (w, h)

        # Build ELK edge list from live scene arrows (both endpoints in node set)
        elk_node_set = {n["id"] for n in elk_nodes}
        elk_edges = []
        seen_edge_ids: set[str] = set()
        scene_edge_map: dict[str, dict[str, str]] = {}  # eid → {src, dst} for STRAIGHT recompute
        # Boundary edges: exactly one endpoint is in the selection / elk_node_set.
        # After layout we update the selected-side endpoint to its new position.
        boundary_edges: list[dict[str, Any]] = []
        for edge in scene_edges:
            eid = edge["id"]
            if eid in seen_edge_ids:
                continue
            src_elk = elem_to_elk.get(edge["src"])
            dst_elk = elem_to_elk.get(edge["dst"])
            src_in = src_elk is not None and src_elk in elk_node_set
            dst_in = dst_elk is not None and dst_elk in elk_node_set
            if src_in and dst_in:
                assert src_elk is not None
                assert dst_elk is not None
                seen_edge_ids.add(eid)
                elk_edges.append({"id": eid, "sources": [src_elk], "targets": [dst_elk]})
                scene_edge_map[eid] = {"src": src_elk, "dst": dst_elk}
            elif src_in != dst_in:
                # One endpoint is in the layout scope; track for post-layout fixup
                boundary_edges.append({
                    "id": eid,
                    "src": edge["src"],
                    "dst": edge["dst"],
                    "src_elk": src_elk,
                    "dst_elk": dst_elk,
                    "src_in": src_in,
                })

        scope_label = "selection" if use_selection else None

        layered_only = algorithm == "layered"
        layout_opts: dict[str, str] = {
            "elk.algorithm": algorithm,
            "elk.direction": direction,
            "elk.spacing.nodeNode": str(gap_node),
            "elk.padding": "[top=60,left=60,bottom=60,right=60]",
        }
        if layered_only:
            layout_opts.update({
                "elk.layered.spacing.nodeNodeBetweenLayers": str(gap_layer),
                "elk.layered.spacing.edgeNodeBetweenLayers": str(gap_layer // 2),
                "elk.layered.spacing.edgeEdgeBetweenLayers": "10",
                "elk.layered.nodePlacement.strategy": node_placement,
                "elk.layered.crossingMinimization.strategy": crossing_min,
                "elk.layered.cycleBreaking.strategy": cycle_breaking,
            })
        if algorithm == "stress":
            layout_opts["elk.stress.desiredEdgeLength"] = str(gap_node * 3)
        if elk_options:
            layout_opts.update(elk_options)

        graph = {
            "id": "root",
            "layoutOptions": layout_opts,
            "children": elk_nodes,
            "edges": elk_edges,
        }
        graph_json = json.dumps(graph)
        cdn = _ELK_CDN

        js = f"""
async () => {{
  if (typeof ELK === 'undefined') {{
    await new Promise((resolve, reject) => {{
      const sc = document.createElement('script');
      sc.src = '{cdn}';
      sc.onload = resolve;
      sc.onerror = () => reject(new Error('Failed to load ELK from CDN'));
      document.head.appendChild(sc);
    }});
  }}
  const elk = new ELK();
  const graph = {graph_json};
  const result = await elk.layout(graph);
  const offsetX = {layout_offset_x}, offsetY = {layout_offset_y};
  const nodes = result.children.map(n => ({{id: n.id, x: n.x + offsetX, y: n.y + offsetY}}));
  return {{nodes, edges: []}};
}}
"""
        elk_result = _browser_evaluate_json(js)
        if not isinstance(elk_result, dict):
            return f"Error: ELK returned unexpected result: {elk_result!r}"

        positions_list: list[dict[str, Any]] = elk_result.get("nodes", [])

        # Patch node positions in the browser
        patches: list[dict[str, Any]] = []
        for pos in positions_list:
            id_ = pos["id"]
            x, y = float(pos["x"]), float(pos["y"])
            w, h = node_dims.get(id_, (160, 60))
            patches.append({"id": id_, "x": x, "y": y})
            # Also reposition the DSL-drawn text element if present
            dsl_shape = layout_state["shapes"].get(id_)
            if dsl_shape is not None:
                font_size = _DEFAULT_FONT_SIZE
                line_count = len((dsl_shape.get("label") or "").split("\n"))
                text_h = line_count * font_size * 1.25
                patches.append({"id": id_ + "-text", "x": x + 8, "y": y + (h - text_h) / 2})

        # Recompute each arrow's endpoints from the new node positions — ELK does not
        # return waypoints; arrows stay bound via startBinding.
        pos_map: dict[str, tuple[float, float]] = {
            pos["id"]: (float(pos["x"]), float(pos["y"])) for pos in positions_list
        }
        for eid, einfo in scene_edge_map.items():
            src_id, dst_id = einfo["src"], einfo["dst"]
            if src_id not in pos_map or dst_id not in pos_map:
                continue
            sx, sy = pos_map[src_id]
            ex, ey = pos_map[dst_id]
            sw, sh = float(node_dims.get(src_id, (160, 60))[0]), float(node_dims.get(src_id, (160, 60))[1])
            dw, dh = float(node_dims.get(dst_id, (160, 60))[0]), float(node_dims.get(dst_id, (160, 60))[1])
            if direction == "RIGHT":
                start: list[float] = [sx + sw, sy + sh / 2]
                end: list[float] = [ex, ey + dh / 2]
            elif direction == "LEFT":
                start = [sx, sy + sh / 2]
                end = [ex + dw, ey + dh / 2]
            elif direction == "DOWN":
                start = [sx + sw / 2, sy + sh]
                end = [ex + dw / 2, ey]
            else:  # UP
                start = [sx + sw / 2, sy]
                end = [ex + dw / 2, ey + dh]
            patches.append({"id": eid, "points": [start, end]})

        # Fix boundary arrows: one endpoint inside the selection, one outside.
        # Move the inside endpoint to track its node's new position; outside stays put.
        # The connection side depends on whether the anchored node is the arrow's
        # source (arrow leaves → use the exit side) or destination (arrow arrives →
        # use the entry side), which is the *opposite* side from the layout direction.
        for bedge in boundary_edges:
            eid = bedge["id"]
            src_inside: bool = bedge["src_in"]
            anchored_elk = bedge["src_elk"] if src_inside else bedge["dst_elk"]
            free_id = bedge["dst"] if src_inside else bedge["src"]
            if anchored_elk not in pos_map:
                continue
            anc_x, anc_y = pos_map[anchored_elk]
            anc_w, anc_h = float(node_dims.get(anchored_elk, (160, 60))[0]), float(node_dims.get(anchored_elk, (160, 60))[1])
            free_node = all_node_map.get(free_id) or {}
            free_x = float(free_node.get("x", 0))
            free_y = float(free_node.get("y", 0))
            free_w = float(free_node.get("w", 160))
            free_h = float(free_node.get("h", 60))

            # Determine connection points: the anchored node uses the side
            # appropriate for its role (source=exit side, dest=entry side).
            # For RIGHT layout: source exits right, dest enters left.
            if direction == "RIGHT":
                if src_in:
                    anc_pt: list[float] = [anc_x + anc_w, anc_y + anc_h / 2]
                    free_pt: list[float] = [free_x, free_y + free_h / 2]
                else:
                    anc_pt = [anc_x, anc_y + anc_h / 2]
                    free_pt = [free_x + free_w, free_y + free_h / 2]
            elif direction == "LEFT":
                if src_in:
                    anc_pt = [anc_x, anc_y + anc_h / 2]
                    free_pt = [free_x + free_w, free_y + free_h / 2]
                else:
                    anc_pt = [anc_x + anc_w, anc_y + anc_h / 2]
                    free_pt = [free_x, free_y + free_h / 2]
            elif direction == "DOWN":
                if src_in:
                    anc_pt = [anc_x + anc_w / 2, anc_y + anc_h]
                    free_pt = [free_x + free_w / 2, free_y]
                else:
                    anc_pt = [anc_x + anc_w / 2, anc_y]
                    free_pt = [free_x + free_w / 2, free_y + free_h]
            else:  # UP
                if src_in:
                    anc_pt = [anc_x + anc_w / 2, anc_y]
                    free_pt = [free_x + free_w / 2, free_y + free_h]
                else:
                    anc_pt = [anc_x + anc_w / 2, anc_y + anc_h]
                    free_pt = [free_x + free_w / 2, free_y]
            start_pt, end_pt = (anc_pt, free_pt) if src_in else (free_pt, anc_pt)
            patches.append({"id": eid, "points": [start_pt, end_pt]})

        patches_json = json.dumps(patches)
        _browser_evaluate(f"""() => {{
  const now = Date.now();
  const rng = () => Math.floor(Math.random() * 9999999);
  const patches = {patches_json};
  for (const p of patches) {{
    const el = window.__drawElements[p.id];
    if (!el) continue;
    if (p.points) {{
      const pts = p.points.map(pt => [pt[0] - p.points[0][0], pt[1] - p.points[0][1]]);
      const xs = pts.map(pt => pt[0]), ys = pts.map(pt => pt[1]);
      window.__drawElements[p.id] = {{ ...el,
        x: p.points[0][0], y: p.points[0][1],
        points: pts,
        width: Math.max(...xs) - Math.min(...xs) || 1,
        height: Math.max(...ys) - Math.min(...ys) || 1,
        roughness: 0,
        version: (el.version || 1) + 1, versionNonce: rng(), updated: now }};
    }} else {{
      window.__drawElements[p.id] = {{ ...el, x: p.x, y: p.y,
        version: (el.version || 1) + 1, versionNonce: rng(), updated: now }};
    }}
  }}
  window.__drawApi._raw.updateScene({{ elements: Object.values(window.__drawElements) }});
}}""")

        # Patch arrow_type on all layout-affected arrows if requested
        if arrow_type is not None:
            affected_edge_ids = list(scene_edge_map.keys())
            if affected_edge_ids:
                edge_ids_json = json.dumps(affected_edge_ids)
                at_roundness = "null" if arrow_type in ("sharp", "elbow") else "{ type: 2 }"
                at_elbowed = "true" if arrow_type == "elbow" else "false"
                _browser_evaluate(f"""() => {{
  const now = Date.now();
  const rng = () => Math.floor(Math.random() * 9999999);
  for (const eid of {edge_ids_json}) {{
    const el = window.__drawElements[eid];
    if (!el) continue;
    window.__drawElements[eid] = {{ ...el,
      roundness: {at_roundness},
      elbowed: {at_elbowed},
      version: (el.version || 1) + 1, versionNonce: rng(), updated: now }};
  }}
  window.__drawApi._raw.updateScene({{ elements: Object.values(window.__drawElements) }});
}}""")

        # Recompute subgraph bounding boxes using updated node positions
        if layout_state["groups"]:
            subgraph_payloads = [
                {"id": gid, "label": group["label"],
                 "memberIds": group["members"], "savedBounds": None}
                for gid, group in layout_state["groups"].items()
            ]
            sg_json = json.dumps(subgraph_payloads)
            _browser_evaluate(f"() => window._batch_draw([], [], {sg_json})")

        fit()

        n_nodes = len(positions_list)
        s.add("nodes", n_nodes)
        scope_suffix = " (selection)" if scope_label else ""
        return f"layout applied to {n_nodes} nodes{scope_suffix}"


_ALIGN_ACTIONS: dict[str, str] = {
    "left":        "alignLeft",
    "hcenter":     "alignHorizontallyCentered",
    "right":       "alignRight",
    "top":         "alignTop",
    "vcenter":     "alignVerticallyCentered",
    "bottom":      "alignBottom",
    "hdistribute": "distributeHorizontally",
    "vdistribute": "distributeVertically",
}


def align(*, ids: list[str], axis: str) -> str:
    """Align or distribute a set of shapes using Excalidraw's built-in actions.

    Args:
        ids:  List of element IDs to align.
        axis: Alignment axis — one of:
              ``left``, ``hcenter``, ``right`` (snap left/centre/right edges),
              ``top``, ``vcenter``, ``bottom`` (snap top/centre/bottom edges),
              ``hdistribute``, ``vdistribute`` (even horizontal/vertical spacing).

    Returns:
        Summary like ``"aligned 3 element(s) (left)"``.

    Example:
        wb.align(ids=["a", "b", "c"], axis="top")
        wb.align(ids=["a", "b", "c"], axis="hdistribute")
    """
    axis = axis.lower()
    if axis not in _ALIGN_ACTIONS:
        return f"Error: axis must be one of {sorted(_ALIGN_ACTIONS)}"

    with LogSpan(span="excalidraw.align", axis=axis) as s:
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err

        action_name = _ALIGN_ACTIONS[axis]
        ids_json = json.dumps(ids)
        # Use action.perform() directly with a synthetic appState so selection is
        # visible synchronously — api.setAppState() schedules an async React update
        # and the immediately following executeAction() would read stale state.
        _browser_evaluate(
            f"() => {{"
            f"  const api = window.__drawApi._raw;"
            f"  const elements = api.getSceneElements();"
            f"  const base = api.state || (api.getAppState ? api.getAppState() : {{}});"
            f"  const appState = {{ ...base, selectedElementIds: Object.fromEntries({ids_json}.map(id => [id, true])) }};"
            f"  const action = api.actionManager.actions['{action_name}'];"
            f"  const result = action.perform(elements, appState, null, api);"
            f"  if (result && result.elements) api.updateScene({{ elements: result.elements }});"
            f"  if (result && result.appState) api.updateScene({{ appState: result.appState }});"
            f"}}"
        )

        s.add("count", len(ids))
        return f"aligned {len(ids)} element(s) ({axis})"


def screenshot(*, file: str | None = None, board: str | None = None) -> Any:
    """Take a screenshot of the current canvas as PNG.

    Returns image content for inline display. Optionally saves to disk.

    Args:
        file: Optional path to save the screenshot (PNG).
        board: Named board to render. Defaults to the CWD-keyed board.

    Returns:
        Screenshot image content, or confirmation message when file is given.

    Example:
        excalidraw.screenshot()
        excalidraw.screenshot(file="diagrams/canvas.png")
    """
    with LogSpan(span="excalidraw.screenshot") as s:
        # Load session state and render to browser
        state = _session.load(board)
        err = _ensure_ready()
        if err:
            s.add("error", err)
            return err
        _rerender_from_state(state)

        if file is None:
            return _run(_tab.take_screenshot(as_base64=True))

        out_path = resolve_cwd_path(file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _run(_tab.take_screenshot(path=str(out_path)))
        return f"screenshot saved to {file}"


def hard_reset() -> str:
    """Reset Python DSL state unconditionally; attempt canvas clear if browser is available.

    Use this to recover from a broken Chrome state where normal
    tools fail. Python state is always reset. Browser clear is attempted
    opportunistically — if the browser is down it is silently skipped.

    Returns:
        "hard reset: state cleared, canvas cleared" or
        "hard reset: state cleared (browser unavailable)"

    Example:
        excalidraw.hard_reset()
    """
    _session.clear_board(None)

    browser_ok = False
    if _check_browser() is None:
        try:
            _browser_evaluate("() => window.__drawApi.clear()")
            browser_ok = True
        except Exception:
            pass

    if browser_ok:
        return "hard reset: state cleared, canvas cleared"
    return "hard reset: state cleared (browser unavailable)"


def boards() -> str:
    """List all active whiteboard session boards.

    Scans ``.onetool/state/whiteboard/`` and returns each board's name,
    last-modified time, and shape count.

    Returns:
        Human-readable list of boards or "no boards found".

    Example:
        whiteboard.boards()
    """
    board_list = _session.list_boards()
    if not board_list:
        return "no boards found"
    import datetime
    lines = []
    for b in board_list:
        mtime_str = datetime.datetime.fromtimestamp(b["mtime"]).strftime("%Y-%m-%d %H:%M")
        lines.append(f"  {b['name']}  ({b['shape_count']} shapes, modified {mtime_str})")
    return "boards:\n" + "\n".join(lines)


def open() -> str:
    """Open excalidraw.com and start with a clean canvas.

    Navigates to excalidraw.com and initialises the drawing API if not
    already ready, then clears the canvas and resets all Python state.

    **Warning:** any shapes the user has drawn directly in the browser that
    were not saved via ``whiteboard.save()`` will be lost. Call
    ``whiteboard.save()`` first to preserve them.

    To restore previously saved content after opening, call whiteboard.load().

    Returns:
        "whiteboard ready" on success, or an error string.

    Example:
        excalidraw.open()
    """
    with LogSpan(span="excalidraw.open") as s:
        err = _ensure_ready()
        # Untracked content warning is non-fatal — open() always starts fresh
        if err and not err.startswith("Warning:"):
            s.add("error", err)
            return err
        # Always start fresh: clear session file and canvas
        _session.clear_board(None)
        with contextlib.suppress(Exception):
            _browser_evaluate("() => window.__drawApi.clear()")
        return "whiteboard ready"


def close() -> str:
    """Close the excalidraw browser and reset all Python state.

    Resets DSL state unconditionally, then terminates the browser process.
    On the next whiteboard tool call a fresh excalidraw.com tab will be
    opened automatically.

    Returns:
        Confirmation message.

    Example:
        excalidraw.close()
    """
    global _browser, _tab
    _session.clear_board(None)
    b, _browser, _tab = _browser, None, None
    if b is not None:
        # Graceful shutdown via pydoll's stop() — sends Browser.close CDP
        # command, terminates process, cleans temp dirs, closes WebSocket.
        with contextlib.suppress(Exception):
            _run(b.stop())
        # Fallback: kill process if stop() didn't terminate it.
        with contextlib.suppress(Exception):
            pm = getattr(b, "_browser_process_manager", None)
            proc = getattr(pm, "_process", None) if pm else None
            if proc is not None and proc.poll() is None:
                proc.kill()
    return "whiteboard closed"

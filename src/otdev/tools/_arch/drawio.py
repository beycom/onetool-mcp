"""draw.io editable-SVG emitter for the arch pack (Phase A: pure functions).

Three pure functions, per `openspec/changes/arch-drawio-editable-svg/design.md`
(decisions D2-D7):

- `extract_geometry(svg_text)` -- decode the base64 `<g class="...">` names
  emitted by `d2` into D2 object paths (e.g. `sys_a.app_a.cmp_a`) and read
  each node's absolute bounding box from its rendered shape (D6).
- `build_mxfile(...)` -- render-context nodes/nesting/edges + the extracted
  geometry map -> an uncompressed `<mxfile host="onetool-arch">` XML string
  (D3, D4). Falls back to deterministic grid placement for any node missing
  from the geometry map (D7).
- `inject_content(svg_text, mxfile_xml)` -- set the escaped `content`
  attribute on the root `<svg>` element via `ElementTree` (never string
  concatenation), producing draw.io's "Include a copy of my diagram" format.

Verified against the installed `d2` 0.7.1: every node shape is a `<g>` whose
`class` attribute is `"<base64(d2 object path)> <D2 class name(s)>"`
(space-separated; only the first token is the base64 path). Edge groups
decode to a `(<edge key>)[<index>]` form (e.g. `(a -&gt; b)[0]`) and are
skipped. `<g>` elements are flat siblings -- container membership is purely
by decoded-path prefix and absolute position, never by SVG nesting -- and a
linked node is individually wrapped as `<a href="..."><g class="...">`, so
geometry extraction matches `<g>` elements anywhere in the tree.
"""

from __future__ import annotations

import base64
import binascii
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from otpack import LogSpan

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

Box = tuple[float, float, float, float]

# ---------------------------------------------------------------------------
# 1.1 extract_geometry
# ---------------------------------------------------------------------------

_SHAPE_TAGS = {"rect", "ellipse", "circle"}
# Edge groups decode to a bracketed-index form, e.g. "(a -&gt; b)[0]"
# regardless of operator (->, <-, <->, --); verified against d2 0.7.1.
_EDGE_PATH_RE = re.compile(r"^\(.*\)\[\d+\]$")


def _local_name(tag: str) -> str:
    """Strip an XML namespace prefix (`{uri}tag` -> `tag`)."""
    return tag.rsplit("}", 1)[-1]


def _decode_d2_class_token(class_attr: str) -> str | None:
    """Base64-decode the first whitespace-separated token of a `<g class="...">`
    value into a D2 object path. Returns `None` (never raises) for anything
    that is not valid base64/UTF-8 -- covers d2's own non-path group classes
    (`shape`, `appendix-icon`, `text fill-N1`, ...)."""
    tokens = class_attr.split()
    if not tokens:
        return None
    token = tokens[0]
    padded = token + "=" * (-len(token) % 4)
    try:
        decoded = base64.b64decode(padded, validate=True)
    except (binascii.Error, ValueError):
        return None
    try:
        return decoded.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _shape_box(shape: ET.Element) -> Box | None:
    """Read an absolute bounding box from a `<rect>`/`<ellipse>`/`<circle>`
    element. Returns `None` (never raises) on missing/malformed attributes."""
    tag = _local_name(shape.tag)
    try:
        if tag == "rect":
            x = float(shape.get("x", "0"))
            y = float(shape.get("y", "0"))
            w = float(shape.get("width", "0"))
            h = float(shape.get("height", "0"))
        elif tag == "circle":
            cx = float(shape.get("cx", "0"))
            cy = float(shape.get("cy", "0"))
            r = float(shape.get("r", "0"))
            x, y, w, h = cx - r, cy - r, 2 * r, 2 * r
        elif tag == "ellipse":
            cx = float(shape.get("cx", "0"))
            cy = float(shape.get("cy", "0"))
            rx = float(shape.get("rx", "0"))
            ry = float(shape.get("ry", "0"))
            x, y, w, h = cx - rx, cy - ry, 2 * rx, 2 * ry
        else:  # pragma: no cover - guarded by _SHAPE_TAGS membership
            return None
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return (x, y, w, h)


def extract_geometry(svg_text: str) -> dict[str, Box]:
    """Decode every base64-class `<g>` in `svg_text` into `{d2_path: (x, y, w, h)}`.

    Matches `<g>` elements anywhere in the tree (never assumes they are
    direct children of the root), so link-wrapped nodes
    (`<a href="..."><g class="...">`, design D6) are still found. Edge
    groups and unrecognized group classes are skipped. Never raises --
    unparseable SVG or a group without a usable shape simply contributes
    no entry.
    """
    geometry: dict[str, Box] = {}
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return geometry

    for group in root.iter():
        if _local_name(group.tag) != "g":
            continue
        class_attr = group.get("class")
        if not class_attr:
            continue
        decoded = _decode_d2_class_token(class_attr)
        if not decoded or _EDGE_PATH_RE.match(decoded):
            continue

        box: Box | None = None
        for shape in group.iter():
            if _local_name(shape.tag) in _SHAPE_TAGS:
                box = _shape_box(shape)
                if box is not None:
                    break
        if box is None:
            continue
        # First match wins; d2 does not reuse an object path across <g>s.
        geometry.setdefault(decoded, box)

    return geometry


# ---------------------------------------------------------------------------
# 1.3 Style mapping
# ---------------------------------------------------------------------------

# D2 base node class -> mxCell style string, approximating the fill/stroke
# colors in arch-templates/d2/styles.d2 (D5). Keyed by *base* class only
# (Person/External/System/App/component classes); callers ignore classes
# they don't recognize rather than failing (D6) -- component classes not in
# this table fall back to the generic "Cmp" style.
STYLE_MAP: dict[str, str] = {
    "Person": "shape=mxgraph.basic.actor;html=1;fillColor=#E8E8E8;strokeColor=#333333;fontColor=#333333;",
    "External": (
        "rounded=1;whiteSpace=wrap;html=1;arcSize=10;"
        "fillColor=#999999;strokeColor=none;fontColor=#FFFFFF;"
    ),
    "System": (
        "rounded=1;whiteSpace=wrap;html=1;arcSize=10;"
        "fillColor=#D5DFF2;strokeColor=#2D6CB5;strokeWidth=2;fontColor=#213754;"
    ),
    "App": (
        "rounded=1;whiteSpace=wrap;html=1;arcSize=10;"
        "fillColor=#C6DBFA;strokeColor=#9FBEEC;fontColor=#1D324C;"
    ),
    "Web": (
        "rounded=1;whiteSpace=wrap;html=1;arcSize=8;"
        "fillColor=#F6CDC4;strokeColor=#D9AAA1;fontColor=#452D2A;"
    ),
    "DB": (
        "rounded=1;whiteSpace=wrap;html=1;arcSize=8;"
        "fillColor=#DCCEF0;strokeColor=#B9A2DC;fontColor=#392B4B;"
    ),
    "File": (
        "rounded=1;whiteSpace=wrap;html=1;arcSize=8;"
        "fillColor=#CBE9DC;strokeColor=#9FCCB8;fontColor=#264838;"
    ),
    "API": (
        "rounded=1;whiteSpace=wrap;html=1;arcSize=8;"
        "fillColor=#F6DDC0;strokeColor=#DFC09F;fontColor=#53371E;"
    ),
    "Batch": (
        "rounded=1;whiteSpace=wrap;html=1;arcSize=8;"
        "fillColor=#CDE4E8;strokeColor=#ADCCD3;fontColor=#244B53;"
    ),
    "Queue": (
        "rounded=1;whiteSpace=wrap;html=1;arcSize=8;"
        "fillColor=#F1CECE;strokeColor=#DAB0B0;fontColor=#532C2C;"
    ),
    "Cmp": (
        "rounded=1;whiteSpace=wrap;html=1;arcSize=8;"
        "fillColor=#DEDFE2;strokeColor=#C4C5C9;fontColor=#2E2E2E;"
    ),
}

EDGE_STYLE = "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;"


def _component_style(class_name: str) -> str:
    """Base component class -> style string, defaulting to the generic
    "Cmp" style for unrecognized values (D6)."""
    return STYLE_MAP.get(class_name, STYLE_MAP["Cmp"])


# ---------------------------------------------------------------------------
# 1.4 Deterministic grid-placement fallback
# ---------------------------------------------------------------------------

_GRID_COLS = 4
_GRID_CELL_W = 200.0
_GRID_CELL_H = 100.0
_GRID_GAP_X = 40.0
_GRID_GAP_Y = 40.0


def _grid_fallback_box(index: int) -> Box:
    """Deterministic non-overlapping placeholder box for a node whose
    geometry could not be extracted from the rendered SVG (design D7)."""
    col = index % _GRID_COLS
    row = index // _GRID_COLS
    x = col * (_GRID_CELL_W + _GRID_GAP_X)
    y = row * (_GRID_CELL_H + _GRID_GAP_Y)
    return (x, y, _GRID_CELL_W, _GRID_CELL_H)


class _GeometryResolver:
    """Resolves a node's absolute `(x, y, w, h)` box from the extracted SVG
    geometry map, falling back to a deterministic grid slot (D7) when the
    node is missing. Tracks which ids fell back so the caller can log the
    degradation via `LogSpan` without failing generation."""

    def __init__(self, geometry: Mapping[str, Box]) -> None:
        self._geometry = geometry
        self._next_fallback_index = 0
        self.fallback_ids: list[str] = []

    def resolve(self, path_id: str) -> Box:
        box = self._geometry.get(path_id)
        if box is not None:
            return box
        box = _grid_fallback_box(self._next_fallback_index)
        self._next_fallback_index += 1
        self.fallback_ids.append(path_id)
        return box


def _relative_box(box: Box, parent_box: Box | None) -> Box:
    """Convert an absolute box to parent-relative coordinates (D4); returns
    the box unchanged for root-level (unparented) nodes."""
    if parent_box is None:
        return box
    px, py, _pw, _ph = parent_box
    x, y, w, h = box
    return (x - px, y - py, w, h)


def _decode_d2_label(value: str) -> str:
    """Undo the D2-source quoting/escaping applied to label text by
    `system_model.py` (`_quote_d2`/`_wrap_label`: `"escaped \\"text\\""`,
    possibly with literal `\\n` line breaks) so the mxCell `value` shows the
    plain node/interface label rather than D2 syntax."""
    text = value.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    return text.replace('\\"', '"').replace("\\n", "\n")


# ---------------------------------------------------------------------------
# 1.2 build_mxfile
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _Vertex:
    id: str
    label: str
    style: str
    parent: str
    container: bool
    box: Box


@dataclass(slots=True)
class _Edge:
    id: str
    source: str
    target: str
    label: str


_MX_GRAPH_MODEL_ATTRS: dict[str, str] = {
    "dx": "800",
    "dy": "600",
    "grid": "1",
    "gridSize": "10",
    "guides": "1",
    "tooltips": "1",
    "connect": "1",
    "arrows": "1",
    "fold": "1",
    "page": "1",
    "pageScale": "1",
    "pageWidth": "850",
    "pageHeight": "1100",
    "math": "0",
    "shadow": "0",
}


def _leaf_vertex(
    node: Mapping[str, Any],
    *,
    style: str,
    resolver: _GeometryResolver,
) -> _Vertex:
    """Root-level (unparented) vertex for a `user_nodes`/`external_nodes`
    entry: id/path is the node's own id, geometry is root-relative (== absolute)."""
    node_id = str(node["id"])
    box = resolver.resolve(node_id)
    return _Vertex(
        id=node_id,
        label=_decode_d2_label(str(node.get("label", node_id))),
        style=style,
        parent="1",
        container=False,
        box=box,
    )


def _system_block_vertices(
    block: Mapping[str, Any], resolver: _GeometryResolver
) -> list[_Vertex]:
    """Vertices for one `system_blocks` entry: the system itself, its direct
    components, its apps, and each app's components -- with ids built by
    dot-joining the same segment ids the D2 templates nest under (matching
    d2's object-path/base64-class convention) and geometry made
    parent-relative (D4)."""
    vertices: list[_Vertex] = []

    sys_id = str(block["id"])
    sys_box = resolver.resolve(sys_id)
    direct_components = block.get("direct_components") or []
    apps = block.get("apps") or []
    vertices.append(
        _Vertex(
            id=sys_id,
            label=_decode_d2_label(str(block.get("label", sys_id))),
            style=STYLE_MAP["System"],
            parent="1",
            container=bool(direct_components or apps),
            box=sys_box,
        )
    )

    for direct in direct_components:
        cmp_id = str(direct["id"])
        path_id = f"{sys_id}.{cmp_id}"
        cmp_box = resolver.resolve(path_id)
        vertices.append(
            _Vertex(
                id=path_id,
                label=_decode_d2_label(str(direct.get("label", cmp_id))),
                style=_component_style(str(direct.get("class", "Cmp"))),
                parent=sys_id,
                container=False,
                box=_relative_box(cmp_box, sys_box),
            )
        )

    for app in apps:
        app_id = str(app["id"])
        app_path = f"{sys_id}.{app_id}"
        app_box = resolver.resolve(app_path)
        components = app.get("components") or []
        vertices.append(
            _Vertex(
                id=app_path,
                label=_decode_d2_label(str(app.get("label", app_id))),
                style=STYLE_MAP["App"],
                parent=sys_id,
                container=bool(components),
                box=_relative_box(app_box, sys_box),
            )
        )
        for cmp in components:
            cmp_id = str(cmp["id"])
            cmp_path = f"{app_path}.{cmp_id}"
            cmp_box = resolver.resolve(cmp_path)
            vertices.append(
                _Vertex(
                    id=cmp_path,
                    label=_decode_d2_label(str(cmp.get("label", cmp_id))),
                    style=_component_style(str(cmp.get("class", "Cmp"))),
                    parent=app_path,
                    container=False,
                    box=_relative_box(cmp_box, app_box),
                )
            )

    return vertices


def _build_edge(edge: Mapping[str, Any], index: int) -> _Edge:
    """`interface_edges` entry -> `_Edge`. `start_path`/`end_path` are D2
    quoted-dotted path strings (e.g. `"sys_a"."app_a"`); stripping the `"`
    characters yields the same dotted id used for vertex ids."""
    source = str(edge.get("start_path", "")).replace('"', "")
    target = str(edge.get("end_path", "")).replace('"', "")
    label = _decode_d2_label(str(edge.get("label", "")))
    return _Edge(id=f"edge-{index}", source=source, target=target, label=label)


def _fmt_num(value: float) -> str:
    return f"{value:g}"


def _serialize_mxfile(vertices: Sequence[_Vertex], edges: Sequence[_Edge]) -> str:
    mxfile = ET.Element("mxfile", {"host": "onetool-arch"})
    diagram = ET.SubElement(
        mxfile, "diagram", {"id": "onetool-arch-diagram", "name": "Page-1"}
    )
    model = ET.SubElement(diagram, "mxGraphModel", dict(_MX_GRAPH_MODEL_ATTRS))
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    for vertex in vertices:
        cell_attrs: dict[str, str] = {
            "id": vertex.id,
            "value": vertex.label,
            "style": vertex.style,
            "vertex": "1",
            "parent": vertex.parent,
        }
        if vertex.container:
            cell_attrs["container"] = "1"
        cell = ET.SubElement(root, "mxCell", cell_attrs)
        x, y, w, h = vertex.box
        ET.SubElement(
            cell,
            "mxGeometry",
            {
                "x": _fmt_num(x),
                "y": _fmt_num(y),
                "width": _fmt_num(w),
                "height": _fmt_num(h),
                "as": "geometry",
            },
        )

    for edge in edges:
        cell_attrs = {
            "id": edge.id,
            "value": edge.label,
            "style": EDGE_STYLE,
            "edge": "1",
            "parent": "1",
            "source": edge.source,
            "target": edge.target,
        }
        cell = ET.SubElement(root, "mxCell", cell_attrs)
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})

    return ET.tostring(mxfile, encoding="unicode")


def build_mxfile(
    *,
    user_nodes: Sequence[Mapping[str, Any]],
    external_nodes: Sequence[Mapping[str, Any]],
    system_blocks: Sequence[Mapping[str, Any]],
    interface_edges: Sequence[Mapping[str, Any]],
    geometry: Mapping[str, Box],
) -> str:
    """Build an uncompressed `<mxfile host="onetool-arch">` XML string from
    the same render-context shape `system_model.py` uses to template D2
    source (`user_nodes`, `external_nodes`, `system_blocks`,
    `interface_edges` -- i.e. `model.system_view.*`/`model.project_view.*`
    minus the title/label-only fields) plus the geometry map produced by
    `extract_geometry` (design D2, D3, D4).

    One vertex `mxCell` per node (id = the node's dotted D2 object path,
    value = its plain label); systems/apps with children become
    `container="1"` cells with child geometry made parent-relative. One edge
    `mxCell` per `interface_edges` entry, bound by `source`/`target` to the
    endpoint path ids. Nodes missing from `geometry` receive a deterministic
    grid-fallback box (D7); the fallback count/ids are logged via `LogSpan`
    but never raise -- generation always succeeds.
    """
    with LogSpan(
        span="arch.drawio.build_mxfile",
        userNodeCount=len(user_nodes),
        externalNodeCount=len(external_nodes),
        systemBlockCount=len(system_blocks),
        edgeCount=len(interface_edges),
    ) as span:
        resolver = _GeometryResolver(geometry)

        vertices: list[_Vertex] = []
        for user in user_nodes:
            vertices.append(
                _leaf_vertex(user, style=STYLE_MAP["Person"], resolver=resolver)
            )
        for ext in external_nodes:
            vertices.append(
                _leaf_vertex(ext, style=STYLE_MAP["External"], resolver=resolver)
            )
        for block in system_blocks:
            vertices.extend(_system_block_vertices(block, resolver))

        edges = [_build_edge(edge, index) for index, edge in enumerate(interface_edges)]

        mxfile_xml = _serialize_mxfile(vertices, edges)

        span.add(vertexCount=len(vertices), edgeCellCount=len(edges))
        if resolver.fallback_ids:
            span.add(
                geometryFallbackCount=len(resolver.fallback_ids),
                geometryFallbackIds=list(resolver.fallback_ids),
            )
        return mxfile_xml


# ---------------------------------------------------------------------------
# 1.5 inject_content
# ---------------------------------------------------------------------------

_SVG_NS = "http://www.w3.org/2000/svg"
_XLINK_NS = "http://www.w3.org/1999/xlink"
_XML_DECL_RE = re.compile(r"^\s*<\?xml[^>]*\?>\s*")


def inject_content(svg_text: str, mxfile_xml: str) -> str:
    """Set the escaped `content` attribute on the root `<svg>` element to
    `mxfile_xml` (draw.io's "Export As SVG > Include a copy of my diagram"
    format, design D2/D9). Uses `ElementTree` attribute setting -- never
    string concatenation -- so the serializer handles escaping; the
    resulting attribute value round-trips through an XML parser back to the
    original `mxfile_xml` text. Preserves the SVG's existing namespaces
    (default `svg` namespace, `xlink` prefix) and any leading XML
    declaration.
    """
    decl_match = _XML_DECL_RE.match(svg_text)
    prolog = decl_match.group(0) if decl_match else ""

    # register_namespace mutates process-global ElementTree state; ET offers no
    # per-call alternative for controlling serialized prefixes. The registered
    # mappings are the W3C-standard ones, so other ET users can only be
    # affected if they serialize SVG/xlink under non-standard prefixes.
    ET.register_namespace("", _SVG_NS)
    ET.register_namespace("xlink", _XLINK_NS)
    root = ET.fromstring(svg_text)
    root.set("content", mxfile_xml)
    return prolog + ET.tostring(root, encoding="unicode")

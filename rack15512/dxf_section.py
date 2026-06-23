"""Import a DXF cross-section drawing and build a CUFSM node/element mesh.

Speeds up CUFSM model creation: draw (or export) the section **midline** in CAD
as lines / polylines / arcs, then this converts it to the node + element mesh
CUFSM needs - merging coincident endpoints into shared nodes and assigning a
thickness per element (uniform, or per CAD layer so a reinforced upright with
mixed plate thicknesses comes through correctly).

A small, dependency-free ASCII-DXF reader handles the entities a section
drawing uses: ``LINE``, ``LWPOLYLINE`` (incl. bulge arcs), ``POLYLINE``/
``VERTEX``, ``ARC`` and ``CIRCLE``.  Explode splines / ellipses to polylines in
CAD first.  Curves are discretised to straight strips (the finite-strip model
is piecewise-linear anyway).

Output is the same labelled ``[nodes]`` / ``[elements]`` text
:func:`rack15512.cufsm.parse_cufsm_model` reads, so the result feeds straight
into the property / validation tools.  An option recentres the mesh on its
**thickness-weighted CG** (see :func:`rack15512.section_props.recenter_to_centroid`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import section_props

__all__ = ["DxfMesh", "parse_dxf_entities", "entity_polylines",
           "polylines_to_mesh", "mesh_to_cufsm_text", "dxf_to_mesh"]

Point = Tuple[float, float]


# --------------------------------------------------------------- DXF reading
def _read_pairs(text: str) -> List[Tuple[int, str]]:
    """ASCII-DXF (group code, value) pairs."""
    lines = text.splitlines()
    pairs: List[Tuple[int, str]] = []
    i, n = 0, len(lines)
    while i + 1 < n:
        code_s = lines[i].strip()
        val = lines[i + 1].strip()
        i += 2
        try:
            pairs.append((int(code_s), val))
        except ValueError:
            i -= 1                             # resync on a stray line
    return pairs


def parse_dxf_entities(text: str) -> List[Dict]:
    """Split a DXF into entity dicts ``{'type', 'pairs': [(code, value)...]}``.
    Entities start at group code 0; only the geometry types are kept later."""
    ents: List[Dict] = []
    cur: Optional[Dict] = None
    for code, val in _read_pairs(text):
        if code == 0:
            if cur is not None:
                ents.append(cur)
            cur = {"type": val.upper(), "pairs": []}
        elif cur is not None:
            cur["pairs"].append((code, val))
    if cur is not None:
        ents.append(cur)
    return ents


def _first(ent: Dict, code: int, default: Optional[float] = None
           ) -> Optional[float]:
    for c, v in ent["pairs"]:
        if c == code:
            try:
                return float(v)
            except ValueError:
                return default
    return default


def _layer(ent: Dict) -> str:
    for c, v in ent["pairs"]:
        if c == 8:
            return v
    return "0"


def _arc_points(cx: float, cy: float, r: float, a0: float, a1: float,
                seg_angle: float) -> List[Point]:
    """Points along an arc (angles in radians, swept a0 -> a1 in that sense)."""
    sweep = a1 - a0
    n = max(1, int(math.ceil(abs(sweep) / math.radians(max(seg_angle, 1.0)))))
    return [(cx + r * math.cos(a0 + sweep * k / n),
             cy + r * math.sin(a0 + sweep * k / n)) for k in range(n + 1)]


def _bulge_points(p0: Point, p1: Point, bulge: float,
                  seg_angle: float) -> List[Point]:
    """Discretise a polyline bulge segment (bulge = tan(theta/4))."""
    if abs(bulge) < 1e-12:
        return [p0, p1]
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    chord = math.hypot(dx, dy)
    if chord < 1e-12:
        return [p0, p1]
    theta = 4.0 * math.atan(bulge)             # signed included angle
    r = chord / (2.0 * math.sin(theta / 2.0))
    mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    d = (chord / 2.0) / math.tan(theta / 2.0)  # midpoint -> centre (signed)
    ux, uy = -dy / chord, dx / chord           # left normal of the chord
    cx, cy = mx + ux * d, my + uy * d
    a0 = math.atan2(y0 - cy, x0 - cx)
    pts = _arc_points(cx, cy, abs(r), a0, a0 + theta, seg_angle)
    pts[0], pts[-1] = p0, p1                    # snap exact endpoints
    return pts


def entity_polylines(entities: Sequence[Dict], seg_angle: float = 12.0
                     ) -> List[Tuple[List[Point], str, bool]]:
    """Convert geometry entities to ``(points, layer, closed)`` polylines."""
    out: List[Tuple[List[Point], str, bool]] = []
    poly: Optional[Dict] = None                # open old-style POLYLINE context
    poly_verts: List[Tuple[Point, float]] = []
    for ent in entities:
        et = ent["type"]
        if et == "LINE":
            out.append(([(_first(ent, 10, 0.0), _first(ent, 20, 0.0)),
                         (_first(ent, 11, 0.0), _first(ent, 21, 0.0))],
                        _layer(ent), False))
        elif et == "ARC":
            cx, cy = _first(ent, 10, 0.0), _first(ent, 20, 0.0)
            r = _first(ent, 40, 0.0) or 0.0
            a0 = math.radians(_first(ent, 50, 0.0) or 0.0)
            a1 = math.radians(_first(ent, 51, 360.0) or 0.0)
            if a1 <= a0:
                a1 += 2.0 * math.pi
            out.append((_arc_points(cx, cy, r, a0, a1, seg_angle),
                        _layer(ent), False))
        elif et == "CIRCLE":
            cx, cy = _first(ent, 10, 0.0), _first(ent, 20, 0.0)
            r = _first(ent, 40, 0.0) or 0.0
            out.append((_arc_points(cx, cy, r, 0.0, 2.0 * math.pi, seg_angle),
                        _layer(ent), True))
        elif et == "LWPOLYLINE":
            out.append(_lwpolyline(ent, seg_angle))
        elif et == "POLYLINE":
            poly = ent
            poly_verts = []
        elif et == "VERTEX" and poly is not None:
            poly_verts.append(((_first(ent, 10, 0.0), _first(ent, 20, 0.0)),
                               _first(ent, 42, 0.0) or 0.0))
        elif et == "SEQEND" and poly is not None:
            out.append(_assemble_polyline(poly_verts, _layer(poly),
                                          bool(int(_first(poly, 70, 0) or 0) & 1),
                                          seg_angle))
            poly, poly_verts = None, []
    return out


def _lwpolyline(ent: Dict, seg_angle: float) -> Tuple[List[Point], str, bool]:
    verts: List[Tuple[Point, float]] = []
    x = y = None
    bulge = 0.0
    for c, v in ent["pairs"]:
        if c == 10:
            if x is not None:
                verts.append(((x, y), bulge))
                bulge = 0.0
            x = float(v)
        elif c == 20:
            y = float(v)
        elif c == 42:
            bulge = float(v)
    if x is not None:
        verts.append(((x, y), bulge))
    closed = bool(int(_first(ent, 70, 0) or 0) & 1)
    return _assemble_polyline(verts, _layer(ent), closed, seg_angle)


def _assemble_polyline(verts: List[Tuple[Point, float]], layer: str,
                       closed: bool, seg_angle: float
                       ) -> Tuple[List[Point], str, bool]:
    pts: List[Point] = []
    seq = list(verts)
    if closed and len(seq) >= 2:
        seq = seq + [seq[0]]
    for (p0, b0), (p1, _b1) in zip(seq[:-1], seq[1:]):
        seg = _bulge_points(p0, p1, b0, seg_angle)
        pts.extend(seg if not pts else seg[1:])
    return pts, layer, closed


# --------------------------------------------------------------- mesh build
@dataclass
class DxfMesh:
    nodes: Dict[int, Point]
    elems: List[Tuple[int, int, float]]
    layers: Dict[str, int] = field(default_factory=dict)   # layer -> elem count
    centroid_removed: Optional[Point] = None               # CG, if recentred


def polylines_to_mesh(polylines: Sequence[Tuple[List[Point], str, bool]],
                      default_t: float,
                      layer_thickness: Optional[Dict[str, float]] = None,
                      merge_tol: float = 1e-3) -> DxfMesh:
    """Merge polyline points into shared nodes and emit thickness-tagged
    elements.  ``layer_thickness`` overrides ``default_t`` per CAD layer."""
    layer_thickness = layer_thickness or {}
    nodes: Dict[int, Point] = {}
    index: Dict[Tuple[int, int], int] = {}
    elems: List[Tuple[int, int, float]] = []
    seen = set()
    layers: Dict[str, int] = {}

    def node_id(p: Point) -> int:
        key = (round(p[0] / merge_tol), round(p[1] / merge_tol))
        if key in index:
            return index[key]
        nid = len(nodes) + 1
        nodes[nid] = (round(p[0], 6), round(p[1], 6))
        index[key] = nid
        return nid

    for pts, layer, _closed in polylines:
        t = layer_thickness.get(layer, default_t)
        ids = [node_id(p) for p in pts]
        for a, b in zip(ids[:-1], ids[1:]):
            if a == b:
                continue
            key = (min(a, b), max(a, b))
            if key in seen:
                continue                       # de-duplicate shared edges
            seen.add(key)
            elems.append((a, b, t))
            layers[layer] = layers.get(layer, 0) + 1
    if not elems:
        raise ValueError("no usable geometry in the DXF (need LINE / "
                         "LWPOLYLINE / POLYLINE / ARC / CIRCLE entities)")
    return DxfMesh(nodes=nodes, elems=elems, layers=layers)


def mesh_to_cufsm_text(mesh: DxfMesh) -> str:
    """Labelled ``[nodes]`` / ``[elements]`` text (read by
    :func:`rack15512.cufsm.parse_cufsm_model`)."""
    lines = ["# CUFSM model generated from DXF (units as drawn)",
             "[nodes]   # id, x, y"]
    for nid in sorted(mesh.nodes):
        x, y = mesh.nodes[nid]
        lines.append(f"{nid}, {x:g}, {y:g}")
    lines.append("[elements]   # id, node_i, node_j, thickness")
    for k, (i, j, t) in enumerate(mesh.elems, 1):
        lines.append(f"{k}, {i}, {j}, {t:g}")
    return "\n".join(lines) + "\n"


def dxf_to_mesh(text: str, default_t: float,
                layer_thickness: Optional[Dict[str, float]] = None,
                seg_angle: float = 12.0, merge_tol: float = 1e-3,
                recenter: bool = False) -> DxfMesh:
    """DXF text -> :class:`DxfMesh`.  With ``recenter`` the nodes are translated
    so the thickness-weighted CG is at the origin."""
    polys = entity_polylines(parse_dxf_entities(text), seg_angle=seg_angle)
    mesh = polylines_to_mesh(polys, default_t, layer_thickness, merge_tol)
    if recenter:
        mesh.nodes, mesh.centroid_removed = \
            section_props.recenter_to_centroid(mesh.nodes, mesh.elems)
    return mesh

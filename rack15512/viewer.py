"""Matplotlib 3D visualisation: model geometry, deformed shape, member
force diagrams and check-utilization plots.  All functions return the
Figure (and save to PNG when `path` is given) so they work in scripts and
in Streamlit."""

from __future__ import annotations

import math
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .checks.en15512 import CheckResult
from .model import RackModel
from .results import CaseResult

_SET_COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#8c564b", "#e377c2"]


def _member_color(model: RackModel) -> Dict[str, str]:
    sets = sorted({m.member_set for m in model.members.values()})
    return {s: _SET_COLORS[i % len(_SET_COLORS)] for i, s in enumerate(sets)}


def _ax3d(title: str):
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(projection="3d")
    ax.set_title(title)
    ax.set_xlabel("X down-aisle [mm]")
    ax.set_ylabel("Y cross-aisle [mm]")
    ax.set_zlabel("Z [mm]")
    return fig, ax


def _equal_aspect(ax, model: RackModel) -> None:
    xs = [n.x for n in model.nodes.values()]
    ys = [n.y for n in model.nodes.values()]
    zs = [n.z for n in model.nodes.values()]
    cx, cy, cz = ((max(v) + min(v)) / 2 for v in (xs, ys, zs))
    r = max(max(v) - min(v) for v in (xs, ys, zs)) / 2 or 1.0
    ax.set_xlim(cx - r, cx + r)
    ax.set_ylim(cy - r, cy + r)
    ax.set_zlim(cz - r, cz + r)


def plot_model(model: RackModel, path: Optional[str] = None):
    fig, ax = _ax3d(f"{model.name} - geometry")
    colors = _member_color(model)
    seen = set()
    for m in model.members.values():
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        label = m.member_set if m.member_set not in seen else None
        seen.add(m.member_set)
        ls = "--" if m.mtype == "truss" else "-"
        ax.plot([ni.x, nj.x], [ni.y, nj.y], [ni.z, nj.z], ls,
                color=colors[m.member_set], lw=1.8, label=label)
    for s in model.supports:
        n = model.nodes[s.node]
        ax.scatter([n.x], [n.y], [n.z], marker="^", color="k", s=60)
    ax.legend(loc="upper right", fontsize=8)
    _equal_aspect(ax, model)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=140)
        plt.close(fig)
    return fig


def plot_deformed(model: RackModel, case: CaseResult, scale: float = 0.0,
                  path: Optional[str] = None):
    if scale <= 0:        # auto-scale: max displacement -> 5% of height
        dmax = max((math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
                    for d in case.displacements.values()), default=1.0)
        scale = 0.05 * model.height() / dmax if dmax > 1e-9 else 1.0
    fig, ax = _ax3d(f"{case.name} - deformed (x{scale:.0f}), "
                    f"max sway {case.max_sway:.1f} mm")
    for m in model.members.values():
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        ax.plot([ni.x, nj.x], [ni.y, nj.y], [ni.z, nj.z],
                color="lightgray", lw=0.8)
        xs, ys, zs = _deformed_curve(model, case, m, scale)
        ax.plot(xs, ys, zs, color="#d62728", lw=1.5)
    _equal_aspect(ax, model)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=140)
        plt.close(fig)
    return fig


def _deformed_curve(model, case, m, scale):
    """The deflected curve of a member: end-node displacements plus the
    member's transverse station deflections (so beams show their true sag,
    not a straight chord)."""
    ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
    di = case.displacements[m.node_i]
    dj = case.displacements[m.node_j]
    xh, yh, zh = model.member_axes(m)
    L = model.member_length(m)
    mr = case.members.get(m.id)
    xs, ys, zs = [], [], []
    stations = mr.stations if mr else []
    for s in stations:
        t = s.x / L if L else 0.0
        # chord displacement (linear between end nodes) + transverse defl
        dx = di[0] + (dj[0] - di[0]) * t + (yh[0] * s.defl_y + zh[0] * s.defl_z)
        dy = di[1] + (dj[1] - di[1]) * t + (yh[1] * s.defl_y + zh[1] * s.defl_z)
        dz = di[2] + (dj[2] - di[2]) * t + (yh[2] * s.defl_y + zh[2] * s.defl_z)
        xs.append(ni.x + xh[0] * s.x + scale * dx)
        ys.append(ni.y + xh[1] * s.x + scale * dy)
        zs.append(ni.z + xh[2] * s.x + scale * dz)
    if not xs:                      # truss / no stations: straight chord
        xs = [ni.x + scale * di[0], nj.x + scale * dj[0]]
        ys = [ni.y + scale * di[1], nj.y + scale * dj[1]]
        zs = [ni.z + scale * di[2], nj.z + scale * dj[2]]
    return xs, ys, zs


def plot_diagram(model: RackModel, case: CaseResult, kind: str = "Mz",
                 path: Optional[str] = None):
    """Member force diagram, kind in {'Mz', 'My', 'N', 'Vy', 'Vz', 'T'}.
    Bending moments are drawn on the TENSION side (sagging beams bulge
    downward), the usual structural convention."""
    fig, ax = _ax3d("")
    vmax = 0.0
    for mr in case.members.values():
        vmax = max(vmax, max(abs(getattr(s, kind)) for s in mr.stations))
    if vmax < 1e-9:
        vmax = 1.0
    h = 0.06 * model.height() / vmax
    for m in model.members.values():
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        xh, yh, zh = model.member_axes(m)
        off = zh if kind in ("My", "Vz") else yh
        # draw bending moments on the tension side (flip sign): a sagging
        # (+Mz) beam then bulges downward, the conventional BMD orientation
        sign = -1.0 if kind in ("My", "Mz") else 1.0
        ax.plot([ni.x, nj.x], [ni.y, nj.y], [ni.z, nj.z], color="k", lw=0.8)
        mr = case.members[m.id]
        pts = [(ni.x, ni.y, ni.z)]
        for s in mr.stations:
            v = sign * getattr(s, kind) * h
            pts.append((ni.x + xh[0] * s.x + off[0] * v,
                        ni.y + xh[1] * s.x + off[1] * v,
                        ni.z + xh[2] * s.x + off[2] * v))
        pts.append((nj.x, nj.y, nj.z))
        ax.plot(*zip(*pts), color="#1f77b4", lw=1.0)
    unit = "kNm" if kind in ("My", "Mz", "T") else "kN"
    div = 1e6 if unit == "kNm" else 1e3
    ax.set_title(f"{case.name} - {kind} diagram (max {vmax/div:.2f} {unit})")
    _equal_aspect(ax, model)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=140)
        plt.close(fig)
    return fig


def plot_frame_elevation(model: RackModel, x: float = 0.0,
                         path: Optional[str] = None):
    """Cross-aisle (Y-Z) elevation of the upright frame at down-aisle
    position x - for comparing the bracing arrangement with the drawing."""
    fig, ax = plt.subplots(figsize=(4, 10))
    colors = _member_color(model)
    tol = 1.0
    for m in model.members.values():
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        if abs(ni.x - x) > tol or abs(nj.x - x) > tol:
            continue
        ls = "--" if m.mtype == "truss" else "-"
        lw = 2.5 if m.member_set == "uprights" else 1.5
        ax.plot([ni.y, nj.y], [ni.z, nj.z], ls,
                color=colors[m.member_set], lw=lw)
    for s in model.supports:
        n = model.nodes[s.node]
        if abs(n.x - x) <= tol:
            ax.plot(n.y, n.z, "^", color="k", ms=10)
    ax.set_title(f"frame elevation at x={x:.0f} mm")
    ax.set_aspect("equal")
    ax.set_xlabel("Y [mm]")
    ax.set_ylabel("Z [mm]")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=140)
        plt.close(fig)
    return fig


def plot_utilization(model: RackModel, checks: List[CheckResult],
                     path: Optional[str] = None):
    """Worst utilization per member (all non-informative checks)."""
    worst: Dict[int, float] = {}
    for c in checks:
        if c.target.startswith("member") and not c.informative:
            mid = int(c.target.split()[1])
            worst[mid] = max(worst.get(mid, 0.0), c.utilization)
    fig, ax = _ax3d(f"{model.name} - governing member utilization (EN 15512)")
    cmap = plt.get_cmap("RdYlGn_r")
    for m in model.members.values():
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        u = worst.get(m.id, 0.0)
        ax.plot([ni.x, nj.x], [ni.y, nj.y], [ni.z, nj.z],
                color=cmap(min(u, 1.2) / 1.2), lw=2.5)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=0, vmax=1.2))
    fig.colorbar(sm, ax=ax, label="utilization (>1 fails)", shrink=0.7)
    _equal_aspect(ax, model)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=140)
        plt.close(fig)
    return fig


# --------------------------------------------------------- dimensioned views
def _dim_line(ax, p0, p1, text, offset=0.0, axis="x"):
    """Draw a double-headed dimension line p0->p1 with a label."""
    import numpy as np
    x0, y0 = p0
    x1, y1 = p1
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="<->", color="#444", lw=0.8))
    ax.text((x0 + x1) / 2, (y0 + y1) / 2, text, fontsize=7, color="#444",
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none",
                      alpha=0.8))


def _projection(model, a, b):
    """Members projected onto two global axes a,b in {'x','y','z'}."""
    idx = {"x": 0, "y": 1, "z": 2}
    ai, bi = idx[a], idx[b]
    out = []
    colors = _member_color(model)
    for m in model.members.values():
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        pi = (ni.x, ni.y, ni.z)
        pj = (nj.x, nj.y, nj.z)
        out.append(((pi[ai], pi[bi]), (pj[ai], pj[bi]),
                    colors[m.member_set], m.member_set, m.mtype))
    return out


def _elevation(model, a, b, title, alabel, blabel, dims_a, dims_b,
               path=None):
    fig, ax = plt.subplots(figsize=(9, 6))
    seen = set()
    for (p0, p1, col, mset, mtype) in _projection(model, a, b):
        lbl = mset if mset not in seen else None
        seen.add(mset)
        ls = "--" if mtype == "truss" else "-"
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], ls, color=col, lw=1.3,
                label=lbl)
    idx = {"x": 0, "y": 1, "z": 2}
    avals = sorted({(n.x, n.y, n.z)[idx[a]] for n in model.nodes.values()})
    bvals = sorted({(n.x, n.y, n.z)[idx[b]] for n in model.nodes.values()})
    a0, a1 = avals[0], avals[-1]
    b0, b1 = bvals[0], bvals[-1]
    span_a = (a1 - a0) or 1.0
    span_b = (b1 - b0) or 1.0
    # dimension chain along a (below) and b (left)
    off_b = b0 - 0.08 * span_b
    if dims_a:
        for x0, x1, txt in dims_a:
            _dim_line(ax, (x0, off_b), (x1, off_b), txt)
    off_a = a0 - 0.10 * span_a
    if dims_b:
        for y0, y1, txt in dims_b:
            _dim_line(ax, (off_a, y0), (off_a, y1), txt)
    ax.set_title(title)
    ax.set_xlabel(alabel)
    ax.set_ylabel(blabel)
    ax.set_aspect("equal")
    ax.legend(loc="upper right", fontsize=7)
    ax.margins(0.12)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=140)
        plt.close(fig)
    return fig


def _consecutive_dims(vals):
    vals = sorted(set(round(v, 1) for v in vals))
    out = [(vals[i], vals[i + 1], f"{vals[i+1]-vals[i]:.0f}")
           for i in range(len(vals) - 1)]
    if len(vals) > 2:
        out.append((vals[0], vals[-1], f"total {vals[-1]-vals[0]:.0f}"))
    return out


def _level_dims(model):
    """Curated vertical dimension chain: floor, each beam level, frame top
    (omits the many intermediate bracing nodes)."""
    beam_z = {model.nodes[m.node_i].z for m in model.members.values()
              if m.member_set == "pallet beams"}
    zs = [n.z for n in model.nodes.values()]
    levels = sorted({min(zs), max(zs)} | beam_z)
    return _consecutive_dims(levels)


def plot_front_elevation(model: RackModel, path: Optional[str] = None):
    """Down-aisle (X-Z) front elevation with bay-width and level dimensions."""
    xs = [n.x for n in model.nodes.values()]
    return _elevation(model, "x", "z",
                      "FRONT elevation (down-aisle, X-Z) [mm]",
                      "X down-aisle [mm]", "Z [mm]",
                      _consecutive_dims(xs), _level_dims(model), path)


def plot_side_elevation(model: RackModel, path: Optional[str] = None):
    """Cross-aisle (Y-Z) side / frame elevation with depth and level dims."""
    ys = [n.y for n in model.nodes.values()]
    return _elevation(model, "y", "z",
                      "SIDE elevation (cross-aisle, Y-Z) [mm]",
                      "Y cross-aisle [mm]", "Z [mm]",
                      _consecutive_dims(ys), _level_dims(model), path)


def plot_plan(model: RackModel, path: Optional[str] = None):
    """Top (X-Y) plan view with length and depth dimensions."""
    xs = [n.x for n in model.nodes.values()]
    ys = [n.y for n in model.nodes.values()]
    return _elevation(model, "x", "y",
                      "PLAN (top, X-Y) [mm]",
                      "X down-aisle [mm]", "Y cross-aisle [mm]",
                      _consecutive_dims(xs), _consecutive_dims(ys), path)


def anchor_layout(bp):
    """Anchor (x, y) positions [mm] in the plate plane for the diagram, plus
    the dimensioning spacings (sy along depth, sx across width, edge e)."""
    b = bp.b or 150.0
    d = bp.d or 150.0
    e = bp.anchor_edge or 25.0
    n = max(int(bp.n_anchors), 1)
    cols = 1 if n <= 2 else 2
    rows = -(-n // cols)
    sx = (b - 2 * e) if cols > 1 else 0.0
    sy = bp.anchor_spacing or max(d - 2 * e, 0.5 * d)
    xs = [-sx / 2.0, sx / 2.0] if cols > 1 else [0.0]
    ys = ([-sy / 2.0 + i * sy / (rows - 1) for i in range(rows)]
          if rows > 1 else [0.0])
    pts = [(x, y) for y in ys for x in xs][:n]
    return pts, sx, sy, e


def plot_footplate(bp, sec=None, path: Optional[str] = None):
    """Profis-style footplate / anchor layout: dimensioned plan + section with
    the input values, so the geometry can be checked at a glance."""
    b = bp.b or 150.0
    d = bp.d or 150.0
    t = bp.t or 4.0
    hef = bp.anchor_hef
    pts, sx, sy, e = anchor_layout(bp)
    r = max(bp.anchor_d / 2.0, 4.0)

    fig, (axp, axs) = plt.subplots(1, 2, figsize=(10, 4.6),
                                   gridspec_kw={"width_ratios": [1.3, 1]})

    # ---- plan view ----
    axp.add_patch(plt.Rectangle((-b / 2, -d / 2), b, d, fill=False,
                                edgecolor="#0C8490", lw=2))
    if sec is not None:                       # upright footprint
        uw = (sec.width_b or 80.0)
        uh = (sec.depth_h or 80.0)
        axp.add_patch(plt.Rectangle((-uw / 2, -uh / 2), uw, uh, fill=True,
                                    facecolor="#0C849022", edgecolor="#545454",
                                    hatch="///", lw=1))
    for (x, y) in pts:
        axp.add_patch(plt.Circle((x, y), r, color="#d62728", zorder=5))
        axp.add_patch(plt.Circle((x, y), r * 0.45, color="white", zorder=6))
    m = max(b, d) * 0.62
    axp.set_xlim(-m, m)
    axp.set_ylim(-m, m)
    axp.set_aspect("equal")
    axp.set_title("Footplate plan (mm)", fontsize=10, color="#0C8490")
    # dimension labels
    axp.annotate(f"b = {b:.0f}", (0, -d / 2 - m * 0.12), ha="center",
                 fontsize=9)
    axp.annotate(f"d = {d:.0f}", (-b / 2 - m * 0.14, 0), va="center",
                 rotation=90, fontsize=9)
    if sy:
        axp.annotate("", (pts[0][0], -sy / 2), (pts[0][0], sy / 2),
                     arrowprops=dict(arrowstyle="<->", color="#545454"))
        axp.text(pts[0][0] + m * 0.04, 0, f"s = {sy:.0f}", fontsize=8,
                 color="#545454")
    if sx:
        axp.annotate("", (-sx / 2, pts[0][1]), (sx / 2, pts[0][1]),
                     arrowprops=dict(arrowstyle="<->", color="#545454"))
        axp.text(0, pts[0][1] + m * 0.04, f"{sx:.0f}", fontsize=8,
                 ha="center", color="#545454")
    axp.axis("off")

    # ---- section view ----
    axs.add_patch(plt.Rectangle((-b / 2, 0), b, t, facecolor="#545454",
                                edgecolor="black"))         # plate
    axs.add_patch(plt.Rectangle((-b / 2, -hef), b, hef, facecolor="#EAEAEA",
                                edgecolor="#999", hatch="..."))  # concrete
    for (x, _y) in pts:
        axs.plot([x, x], [t, -hef], color="#d62728", lw=2)
        axs.plot([x - 6, x + 6], [-hef, -hef], color="#d62728", lw=2)
    axs.annotate(f"t = {t:.0f}", (b / 2 + 8, t / 2), fontsize=8, va="center")
    axs.annotate(f"hef = {hef:.0f}", (b / 2 + 8, -hef / 2), fontsize=8,
                 va="center")
    axs.set_xlim(-b / 2 - 30, b / 2 + 60)
    axs.set_ylim(-hef - 20, t + 30)
    axs.set_aspect("equal")
    axs.set_title("Section (mm)", fontsize=10, color="#0C8490")
    axs.axis("off")

    txt = (f"{bp.n_anchors} x M{bp.anchor_d:.0f} grade {bp.anchor_grade}\n"
           f"hef = {hef:.0f} mm,  edge e = {e:.0f} mm\n"
           f"plate {b:.0f} x {d:.0f} x {t:.0f},  f_ck = {bp.f_ck:.0f} MPa")
    fig.text(0.5, -0.02, txt, ha="center", fontsize=8.5, color="#333")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=130, bbox_inches="tight")
    return fig

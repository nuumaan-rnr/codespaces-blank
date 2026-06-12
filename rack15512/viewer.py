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
        di = case.displacements[m.node_i]
        dj = case.displacements[m.node_j]
        ax.plot([ni.x + scale * di[0], nj.x + scale * dj[0]],
                [ni.y + scale * di[1], nj.y + scale * dj[1]],
                [ni.z + scale * di[2], nj.z + scale * dj[2]],
                color="#d62728", lw=1.5)
    _equal_aspect(ax, model)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=140)
        plt.close(fig)
    return fig


def plot_diagram(model: RackModel, case: CaseResult, kind: str = "Mz",
                 path: Optional[str] = None):
    """Member force diagram, kind in {'Mz', 'My', 'N', 'Vy', 'Vz', 'T'}.
    Bending/shear values are drawn offset along the matching local axis
    (Mz, Vy along local y; My, Vz along local z; N, T along local y)."""
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
        ax.plot([ni.x, nj.x], [ni.y, nj.y], [ni.z, nj.z], color="k", lw=0.8)
        mr = case.members[m.id]
        pts = [(ni.x, ni.y, ni.z)]
        for s in mr.stations:
            v = getattr(s, kind) * h
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

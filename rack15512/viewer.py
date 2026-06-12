"""Matplotlib visualisation: model geometry, deformed shape, internal force
diagrams and check-utilization plots.  All functions return the Figure (and
save to PNG when `path` is given) so they work in scripts and in Streamlit."""

from __future__ import annotations

import math
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .checks.en15512 import CheckResult
from .model import RackModel
from .results import CaseResult

_SET_COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#8c564b", "#e377c2"]


def _member_color(model: RackModel) -> Dict[str, str]:
    sets = sorted({m.member_set for m in model.members.values()})
    return {s: _SET_COLORS[i % len(_SET_COLORS)] for i, s in enumerate(sets)}


def plot_model(model: RackModel, path: Optional[str] = None,
               labels: bool = False):
    fig, ax = plt.subplots(figsize=(9, 7))
    colors = _member_color(model)
    seen = set()
    for m in model.members.values():
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        label = m.member_set if m.member_set not in seen else None
        seen.add(m.member_set)
        ls = "--" if m.mtype == "truss" else "-"
        ax.plot([ni.x, nj.x], [ni.y, nj.y], ls, color=colors[m.member_set],
                lw=2, label=label)
        if m.hinge_i or m.hinge_j:
            for nd, h in ((ni, m.hinge_i), (nj, m.hinge_j)):
                if h:
                    t = 0.08
                    px = nd.x + (nj.x - ni.x) * (t if nd is ni else -t)
                    py = nd.y + (nj.y - ni.y) * (t if nd is ni else -t)
                    ax.plot(px, py, "o", mfc="white", mec="k", ms=5, zorder=5)
        if labels:
            ax.annotate(str(m.id), ((ni.x + nj.x) / 2, (ni.y + nj.y) / 2),
                        fontsize=7, color="gray")
    for s in model.supports:
        n = model.nodes[s.node]
        marker = "s" if s.rz is True else "^"
        ax.plot(n.x, n.y, marker, color="k", ms=10, zorder=5)
        if not isinstance(s.rz, bool):
            ax.annotate("k", (n.x, n.y - 0.04 * model.height()),
                        ha="center", fontsize=8)
    ax.set_title(f"{model.name} - geometry "
                 "(o = semi-rigid connector, ^ = support, k = spring base)")
    ax.set_aspect("equal")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=140)
        plt.close(fig)
    return fig


def plot_deformed(model: RackModel, case: CaseResult, scale: float = 0.0,
                  path: Optional[str] = None):
    fig, ax = plt.subplots(figsize=(9, 7))
    if scale <= 0:        # auto-scale: max displacement -> 5% of height
        dmax = max((math.hypot(d[0], d[1])
                    for d in case.displacements.values()), default=1.0)
        scale = 0.05 * model.height() / dmax if dmax > 1e-9 else 1.0
    for m in model.members.values():
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        ax.plot([ni.x, nj.x], [ni.y, nj.y], color="lightgray", lw=1)
        di = case.displacements[m.node_i]
        dj = case.displacements[m.node_j]
        ax.plot([ni.x + scale * di[0], nj.x + scale * dj[0]],
                [ni.y + scale * di[1], nj.y + scale * dj[1]],
                color="#d62728", lw=1.8)
    ax.set_title(f"{case.name} - deformed shape (x{scale:.0f}), "
                 f"max sway {case.max_sway:.1f} mm")
    ax.set_aspect("equal")
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=140)
        plt.close(fig)
    return fig


def plot_diagram(model: RackModel, case: CaseResult, kind: str = "M",
                 path: Optional[str] = None):
    """Internal force diagram, kind in {'M', 'V', 'N'}."""
    fig, ax = plt.subplots(figsize=(9, 7))
    vmax = 0.0
    for mr in case.members.values():
        vmax = max(vmax, max(abs(getattr(s, kind)) for s in mr.stations))
    if vmax < 1e-9:
        vmax = 1.0
    h = 0.06 * model.height() / vmax
    for m in model.members.values():
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        L = math.hypot(nj.x - ni.x, nj.y - ni.y)
        cx, cy = (nj.x - ni.x) / L, (nj.y - ni.y) / L
        nx, ny = -cy, cx                      # local y (normal)
        ax.plot([ni.x, nj.x], [ni.y, nj.y], color="k", lw=1)
        mr = case.members[m.id]
        xs = [ni.x + cx * s.x + nx * h * getattr(s, kind) for s in mr.stations]
        ys = [ni.y + cy * s.x + ny * h * getattr(s, kind) for s in mr.stations]
        ax.plot([ni.x] + xs + [nj.x], [ni.y] + ys + [nj.y],
                color="#1f77b4", lw=1.2)
        ax.fill([ni.x] + xs + [nj.x], [ni.y] + ys + [nj.y],
                color="#1f77b4", alpha=0.15)
    unit = {"M": "kNm", "V": "kN", "N": "kN"}[kind]
    div = 1e6 if kind == "M" else 1e3
    ax.set_title(f"{case.name} - {kind} diagram (max {vmax/div:.2f} {unit})")
    ax.set_aspect("equal")
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=140)
        plt.close(fig)
    return fig


def plot_utilization(model: RackModel, checks: List[CheckResult],
                     path: Optional[str] = None):
    """Worst utilization per member (all ULS checks), colour-coded."""
    worst: Dict[int, float] = {}
    for c in checks:
        if c.target.startswith("member") and not c.informative:
            mid = int(c.target.split()[1])
            worst[mid] = max(worst.get(mid, 0.0), c.utilization)
    fig, ax = plt.subplots(figsize=(9, 7))
    cmap = plt.get_cmap("RdYlGn_r")
    for m in model.members.values():
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        u = worst.get(m.id, 0.0)
        color = cmap(min(u, 1.2) / 1.2)
        ax.plot([ni.x, nj.x], [ni.y, nj.y], color=color, lw=3)
        ax.annotate(f"{u:.2f}", ((ni.x + nj.x) / 2, (ni.y + nj.y) / 2),
                    fontsize=7, ha="center",
                    color="red" if u > 1.0 else "black")
    sm = plt.cm.ScalarMappable(cmap=cmap,
                               norm=plt.Normalize(vmin=0, vmax=1.2))
    fig.colorbar(sm, ax=ax, label="utilization (>1 fails)", shrink=0.8)
    ax.set_title(f"{model.name} - governing member utilization (EN 15512)")
    ax.set_aspect("equal")
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=140)
        plt.close(fig)
    return fig

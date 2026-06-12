"""Matplotlib visualisation: model geometry, deformed shape, utilization."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

from .checks import CheckReport
from .model import RackModel
from .results import ComboResult


def plot_model(model: RackModel, ax=None):
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 6))
    for m in model.members.values():
        xi, zi = model.node_coords(m.node_i)
        xj, zj = model.node_coords(m.node_j)
        color = "tab:blue" if m.kind == "upright" else "tab:orange"
        ax.plot([xi, xj], [zi, zj], color=color, lw=2.2 if m.kind == "upright" else 1.8)
    for sup in model.supports:
        x, z = model.node_coords(sup.node)
        ax.plot(x, z, marker="^", color="k", ms=10)
    ax.set_aspect("equal")
    ax.set_xlabel("down-aisle X [m]")
    ax.set_ylabel("Z [m]")
    ax.set_title(f"{model.name} - model")
    ax.grid(alpha=0.3)
    return ax.figure


def plot_deformed(model: RackModel, combo: ComboResult, scale: float = 0.0, ax=None):
    """Deformed shape; scale=0 picks an automatic scale (~5% of height)."""
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 6))
    u_max = max((abs(n.ux) for n in combo.nodes.values()), default=0.0)
    u_max = max(u_max, max((abs(n.uz) for n in combo.nodes.values()), default=0.0))
    if scale <= 0.0:
        scale = 0.05 * model.total_height / u_max if u_max > 0 else 1.0
    for m in model.members.values():
        xi, zi = model.node_coords(m.node_i)
        xj, zj = model.node_coords(m.node_j)
        ax.plot([xi, xj], [zi, zj], color="lightgray", lw=1.0)
        ni, nj = combo.nodes.get(m.node_i), combo.nodes.get(m.node_j)
        if ni and nj:
            ax.plot([xi + scale * ni.ux, xj + scale * nj.ux],
                    [zi + scale * ni.uz, zj + scale * nj.uz],
                    color="tab:red", lw=1.8)
    ax.set_aspect("equal")
    ax.set_title(f"Deformed shape - {combo.combo_id} "
                 f"(x{scale:.0f}, max u = {u_max*1e3:.1f} mm)")
    ax.set_xlabel("down-aisle X [m]")
    ax.set_ylabel("Z [m]")
    ax.grid(alpha=0.3)
    return ax.figure


def plot_utilization(model: RackModel, report: CheckReport,
                     checks: tuple[str, ...] = ("cross_section", "buckling"), ax=None):
    """Members coloured by their worst ULS utilization."""
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 6))
    util: dict[int, float] = {}
    for r in report.results:
        if r.check not in checks or "#" not in r.target:
            continue
        mid = int(r.target.split("#")[1].rstrip(")"))
        util[mid] = max(util.get(mid, 0.0), r.ratio)
    norm = Normalize(vmin=0.0, vmax=max(1.0, max(util.values(), default=1.0)))
    cmap = plt.get_cmap("RdYlGn_r")
    for m in model.members.values():
        xi, zi = model.node_coords(m.node_i)
        xj, zj = model.node_coords(m.node_j)
        ratio = util.get(m.id)
        color = cmap(norm(ratio)) if ratio is not None else "lightgray"
        ax.plot([xi, xj], [zi, zj], color=color, lw=3.0)
    sm = ScalarMappable(norm=norm, cmap=cmap)
    ax.figure.colorbar(sm, ax=ax, label="utilization")
    ax.set_aspect("equal")
    ax.set_title("ULS utilization (cross-section / buckling)")
    ax.set_xlabel("down-aisle X [m]")
    ax.set_ylabel("Z [m]")
    ax.grid(alpha=0.3)
    return ax.figure

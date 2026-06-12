"""Matplotlib 3D visualisation: model geometry, deformed shape, utilization."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

from .checks import CheckReport
from .model import RackModel
from .results import ComboResult

KIND_STYLE = {
    "upright": ("tab:blue", 2.0),
    "beam": ("tab:orange", 1.6),
    "brace": ("tab:green", 1.0),
}


def _axes3d(title: str):
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(projection="3d")
    ax.set_xlabel("X down-aisle [m]")
    ax.set_ylabel("Y cross-aisle [m]")
    ax.set_zlabel("Z [m]")
    ax.set_title(title)
    return fig, ax


def _set_equal(ax, model: RackModel):
    xs = [n.x for n in model.nodes.values()]
    ys = [n.y for n in model.nodes.values()]
    zs = [n.z for n in model.nodes.values()]
    cx, cy, cz = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, (max(zs) + min(zs)) / 2
    r = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) / 2 or 1.0
    ax.set_xlim(cx - r, cx + r)
    ax.set_ylim(cy - r, cy + r)
    ax.set_zlim(0, cz + r)


def plot_model(model: RackModel):
    fig, ax = _axes3d(f"{model.name} - model")
    for m in model.members.values():
        xi, yi, zi = model.node_coords(m.node_i)
        xj, yj, zj = model.node_coords(m.node_j)
        color, lw = KIND_STYLE.get(m.kind, ("gray", 1.0))
        ax.plot([xi, xj], [yi, yj], [zi, zj], color=color, lw=lw)
    for sup in model.supports:
        x, y, z = model.node_coords(sup.node)
        ax.plot([x], [y], [z], marker="^", color="k", ms=8)
    _set_equal(ax, model)
    return fig


def plot_deformed(model: RackModel, combo: ComboResult, scale: float = 0.0):
    """Deformed shape; scale=0 picks an automatic scale (~5% of height)."""
    u_max = max((max(abs(n.ux), abs(n.uy), abs(n.uz))
                 for n in combo.nodes.values()), default=0.0)
    if scale <= 0.0:
        scale = 0.05 * model.total_height / u_max if u_max > 0 else 1.0
    fig, ax = _axes3d(f"Deformed shape - {combo.combo_id} "
                      f"(x{scale:.0f}, max u = {u_max*1e3:.1f} mm)")
    for m in model.members.values():
        xi, yi, zi = model.node_coords(m.node_i)
        xj, yj, zj = model.node_coords(m.node_j)
        ax.plot([xi, xj], [yi, yj], [zi, zj], color="lightgray", lw=0.8)
        ni, nj = combo.nodes.get(m.node_i), combo.nodes.get(m.node_j)
        if ni and nj:
            ax.plot([xi + scale * ni.ux, xj + scale * nj.ux],
                    [yi + scale * ni.uy, yj + scale * nj.uy],
                    [zi + scale * ni.uz, zj + scale * nj.uz],
                    color="tab:red", lw=1.6)
    _set_equal(ax, model)
    return fig


def plot_utilization(model: RackModel, report: CheckReport,
                     checks: tuple[str, ...] = ("cross_section", "buckling",
                                                "brace")):
    """Members coloured by their worst ULS utilization."""
    util: dict[int, float] = {}
    for r in report.results:
        if r.check not in checks or "#" not in r.target:
            continue
        mid = int(r.target.split("#")[1].rstrip(")"))
        util[mid] = max(util.get(mid, 0.0), r.ratio)
    norm = Normalize(vmin=0.0, vmax=max(1.0, max(util.values(), default=1.0)))
    cmap = plt.get_cmap("RdYlGn_r")
    fig, ax = _axes3d("ULS utilization (cross-section / buckling / brace)")
    for m in model.members.values():
        xi, yi, zi = model.node_coords(m.node_i)
        xj, yj, zj = model.node_coords(m.node_j)
        ratio = util.get(m.id)
        color = cmap(norm(ratio)) if ratio is not None else "lightgray"
        ax.plot([xi, xj], [yi, yj], [zi, zj], color=color, lw=2.5)
    fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=ax, shrink=0.7,
                 label="utilization")
    _set_equal(ax, model)
    return fig

"""Interactive Plotly 3D viewer with hover tooltips.

Hovering a member shows its id, set and forces (N, My, Mz, V); hovering a
support node shows its reaction components. The deformation scale is a
parameter so the UI can offer a slider.  Works for a single analysis case
or for an envelope (enveloped member forces / reactions).
"""

from __future__ import annotations

from typing import Dict, Optional

import plotly.graph_objects as go

from .viewer import _deformed_curve


def _core_figure(model, deformed_case, member_vals, node_reactions, util,
                 scale, title):
    fig = go.Figure()
    # undeformed wireframe (one trace, None-separated)
    ux, uy, uz = [], [], []
    for m in model.members.values():
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        ux += [ni.x, nj.x, None]
        uy += [ni.y, nj.y, None]
        uz += [ni.z, nj.z, None]
    fig.add_trace(go.Scatter3d(x=ux, y=uy, z=uz, mode="lines",
                               line=dict(color="lightgray", width=2),
                               hoverinfo="skip", name="undeformed"))

    # deformed members + per-member hover markers at midpoint, coloured by
    # EN 15512 utilisation (numeric -> RdYlGn reversed, with a colour bar)
    dx, dy, dz = [], [], []
    mxs, mys, mzs, mtext, muval = [], [], [], [], []
    for m in model.members.values():
        if deformed_case is not None:
            xs, ys, zs = _deformed_curve(model, deformed_case, m, scale)
        else:
            ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
            xs, ys, zs = [ni.x, nj.x], [ni.y, nj.y], [ni.z, nj.z]
        dx += xs + [None]
        dy += ys + [None]
        dz += zs + [None]
        mid = len(xs) // 2
        mxs.append(xs[mid]); mys.append(ys[mid]); mzs.append(zs[mid])
        v = member_vals.get(m.id, {})
        u = util.get(m.id, 0.0)
        muval.append(u)
        flag = " ⚠ FAIL" if u > 1.0 else ""
        mtext.append(
            f"<b>member {m.id}</b> ({m.member_set}, {m.mtype})<br>"
            f"utilisation = {u:.3f}{flag}<br>"
            f"N = {v.get('N', 0)/1e3:.2f} kN<br>"
            f"My = {v.get('My', 0)/1e6:.2f} kNm  "
            f"Mz = {v.get('Mz', 0)/1e6:.2f} kNm<br>"
            f"V = {v.get('V', 0)/1e3:.2f} kN")
    fig.add_trace(go.Scatter3d(x=dx, y=dy, z=dz, mode="lines",
                               line=dict(color="#1f77b4", width=4),
                               hoverinfo="skip", name="deformed"))
    fig.add_trace(go.Scatter3d(
        x=mxs, y=mys, z=mzs, mode="markers",
        marker=dict(size=5, color=muval, colorscale="RdYlGn",
                    reversescale=True, cmin=0.0, cmax=1.2,
                    colorbar=dict(title="utilisation", thickness=14,
                                  len=0.6)),
        text=mtext, hoverinfo="text", name="members"))

    # support nodes with reaction hover
    if node_reactions:
        nx, ny, nz, ntext = [], [], [], []
        for node, comps in node_reactions.items():
            n = model.nodes[node]
            nx.append(n.x); ny.append(n.y); nz.append(n.z)
            lines = [f"<b>node {node}</b> reactions"]
            for c in ("Fx", "Fy", "Fz", "Mx", "My", "Mz"):
                val = comps.get(c)
                if val is None:
                    continue
                v = val[0] if isinstance(val, tuple) else val
                unit = "kN" if c.startswith("F") else "kNm"
                div = 1e3 if c.startswith("F") else 1e6
                src = (f"  [{val[1]}]" if isinstance(val, tuple) else "")
                lines.append(f"{c} = {v/div:.2f} {unit}{src}")
            ntext.append("<br>".join(lines))
        fig.add_trace(go.Scatter3d(
            x=nx, y=ny, z=nz, mode="markers",
            marker=dict(size=6, color="black", symbol="diamond"),
            text=ntext, hoverinfo="text", name="supports"))

    fig.update_layout(
        title=title, showlegend=False, height=650,
        margin=dict(l=0, r=0, t=30, b=0),
        scene=dict(xaxis_title="X down-aisle [mm]",
                   yaxis_title="Y cross-aisle [mm]",
                   zaxis_title="Z [mm]", aspectmode="data"))
    return fig


def figure_for_case(model, case, checks, scale=1.0):
    member_vals, util = {}, {}
    for mid, mr in case.members.items():
        member_vals[mid] = {"N": -mr.N_min if abs(mr.N_min) > abs(mr.N_max)
                            else mr.N_max,
                            "My": mr.My_absmax, "Mz": mr.Mz_absmax,
                            "V": mr.V_absmax}
    for c in checks:
        if c.case == case.name and c.target.startswith("member") \
                and not c.informative:
            mid = int(c.target.split()[1])
            util[mid] = max(util.get(mid, 0.0), c.utilization)
    comps = ("Fx", "Fy", "Fz", "Mx", "My", "Mz")
    reactions = {node: {c: (r[i], None) for i, c in enumerate(comps)}
                 for node, r in case.reactions.items()}
    return _core_figure(model, case, member_vals, reactions, util,
                        scale, f"{case.name} (×{scale:g})")


def figure_for_envelope(model, env, scale=1.0):
    member_vals = {}
    for mid, e in env.members.items():
        member_vals[mid] = {"N": e.N_min if abs(e.N_min) > abs(e.N_max)
                            else e.N_max,
                            "My": e.My_absmax, "Mz": e.Mz_absmax,
                            "V": e.V_absmax}
    # colour by the real EN 15512 utilisation enveloped over the set
    rep = env.representative_case()
    return _core_figure(model, rep, member_vals, env.reactions,
                        env.member_util,
                        scale, f"{env.name} envelope (×{scale:g})")

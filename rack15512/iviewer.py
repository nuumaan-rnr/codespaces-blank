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


# Orthographic directional cameras (no perspective).  Axes: X = down-aisle,
# Y = cross-aisle, Z = up.  CA elevation looks along X (shows the Y-Z frame
# plane); DA elevation looks along Y (shows the X-Z down-aisle plane); Top
# looks down Z (shows the X-Y plan).
VIEW_OPTIONS = ["3D", "DA elevation (X-Z)", "CA elevation (Y-Z)", "Top (plan)"]
_VIEW_CAMERA = {
    "DA elevation (X-Z)": dict(eye=dict(x=0.0, y=-2.5, z=0.0),
                               up=dict(x=0.0, y=0.0, z=1.0)),
    "CA elevation (Y-Z)": dict(eye=dict(x=-2.5, y=0.0, z=0.0),
                               up=dict(x=0.0, y=0.0, z=1.0)),
    "Top (plan)": dict(eye=dict(x=0.0, y=0.0, z=2.5),
                       up=dict(x=0.0, y=1.0, z=0.0)),
}


def apply_view(fig, view: str):
    """Set an orthographic directional camera on a 3D figure.  ``view`` is one
    of VIEW_OPTIONS; '3D' keeps the default perspective camera."""
    cam = _VIEW_CAMERA.get(view)
    if cam is None:
        return fig
    fig.update_layout(scene_camera=dict(
        projection=dict(type="orthographic"),
        center=dict(x=0.0, y=0.0, z=0.0), **cam))
    return fig


def _core_figure(model, deformed_case, member_vals, node_reactions, util,
                 scale, title, show_only=None):
    fig = go.Figure()
    # undeformed wireframe (one trace, None-separated) - always full, for context
    ux, uy, uz = [], [], []
    for m in model.members.values():
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        ux += [ni.x, nj.x, None]
        uy += [ni.y, nj.y, None]
        uz += [ni.z, nj.z, None]
    fig.add_trace(go.Scatter3d(x=ux, y=uy, z=uz, mode="lines",
                               line=dict(color="lightgray", width=2),
                               hoverinfo="skip", name="undeformed",
                               showlegend=False))

    # deformed members coloured by EN 15512 utilisation, in DISCRETE bands so
    # the colour reflects the per-MEMBER value (not a node):
    #   util < 0.9      -> green
    #   0.9 <= util <=1 -> orange
    #   util > 1        -> red (solid, no gradient = a real overstress)
    # Each band is one line trace (the member lines carry the colour); a marker
    # at each member midpoint carries the per-member hover (forces + util).
    # When show_only is a set of member ids, only those are drawn coloured.
    GREEN, ORANGE, RED = "#2ca02c", "#ff7f0e", "#d62728"

    def _band(u):
        if u > 1.0:
            return "red", RED, "util > 1.0 (fail)"
        if u >= 0.9:
            return "orange", ORANGE, "util 0.9–1.0"
        return "green", GREEN, "util < 0.9"

    bands = {"green": [GREEN, "util < 0.9", [], [], []],
             "orange": [ORANGE, "util 0.9–1.0", [], [], []],
             "red": [RED, "util > 1.0 (fail)", [], [], []]}
    mxs, mys, mzs, mtext, mcol = [], [], [], [], []
    for m in model.members.values():
        if show_only is not None and m.id not in show_only:
            continue
        # draw the deformed shape only when the case has displacements for
        # both end nodes; otherwise (e.g. stale results from a different
        # geometry) fall back to the undeformed chord so we never KeyError
        has_defl = (deformed_case is not None
                    and m.node_i in deformed_case.displacements
                    and m.node_j in deformed_case.displacements)
        if has_defl:
            xs, ys, zs = _deformed_curve(model, deformed_case, m, scale)
        else:
            ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
            xs, ys, zs = [ni.x, nj.x], [ni.y, nj.y], [ni.z, nj.z]
        u = util.get(m.id, 0.0)
        key, col, _ = _band(u)
        bx, by, bz = bands[key][2], bands[key][3], bands[key][4]
        bx += xs + [None]
        by += ys + [None]
        bz += zs + [None]
        mid = len(xs) // 2
        mxs.append(xs[mid]); mys.append(ys[mid]); mzs.append(zs[mid])
        mcol.append(col)
        v = member_vals.get(m.id, {})
        flag = " ⚠ FAIL" if u > 1.0 else ""
        mtext.append(
            f"<b>member {m.id}</b> ({m.member_set}, {m.mtype})<br>"
            f"section: {m.section}<br>"
            f"utilisation = {u:.3f}{flag}<br>"
            f"N = {v.get('N', 0)/1e3:.2f} kN<br>"
            f"My = {v.get('My', 0)/1e6:.2f} kNm  "
            f"Mz = {v.get('Mz', 0)/1e6:.2f} kNm<br>"
            f"V = {v.get('V', 0)/1e3:.2f} kN")
    # one coloured line trace per band (legend doubles as the colour key)
    for col, label, bx, by, bz in bands.values():
        if bx:
            fig.add_trace(go.Scatter3d(
                x=bx, y=by, z=bz, mode="lines",
                line=dict(color=col, width=5), hoverinfo="skip",
                name=label, showlegend=True))
    # per-member hover markers at midspan (the member values live here)
    fig.add_trace(go.Scatter3d(
        x=mxs, y=mys, z=mzs, mode="markers",
        marker=dict(size=4, color=mcol),
        text=mtext, hoverinfo="text", name="members", showlegend=False))

    # support nodes with reaction hover
    if node_reactions:
        nx, ny, nz, ntext = [], [], [], []
        for node, comps in node_reactions.items():
            n = model.nodes.get(node)        # skip stale nodes not in the model
            if n is None:
                continue
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
            text=ntext, hoverinfo="text", name="supports", showlegend=True))

    fig.update_layout(
        title=title, showlegend=True, height=650,
        legend=dict(orientation="h", yanchor="bottom", y=0.0,
                    xanchor="left", x=0.0, title_text="utilisation band"),
        margin=dict(l=0, r=0, t=30, b=0),
        scene=dict(xaxis_title="X down-aisle [mm]",
                   yaxis_title="Y cross-aisle [mm]",
                   zaxis_title="Z [mm]", aspectmode="data"))
    return fig


def _model_diagonal(model) -> float:
    xs = [n.x for n in model.nodes.values()]
    ys = [n.y for n in model.nodes.values()]
    zs = [n.z for n in model.nodes.values()]
    if not xs:
        return 1000.0
    dx, dy, dz = max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)
    return max((dx * dx + dy * dy + dz * dz) ** 0.5, 1.0)


def effective_loads(model, selection):
    """Resolve a load case or combination name to its applied loads.

    Returns (nodal, member) where ``nodal`` maps node id -> (Fx,Fy,Fz) in N
    and ``member`` maps member id -> (qx,qy,qz) in N/mm, with combination
    partial factors already applied.
    """
    if selection in model.load_cases:
        contributions = [(model.load_cases[selection], 1.0)]
    else:
        combo = next((c for c in model.combinations if c.name == selection),
                     None)
        contributions = []
        if combo is not None:
            for name, factor in combo.factors.items():
                lc = model.load_cases.get(name)
                if lc is not None:
                    contributions.append((lc, factor))
    nodal: Dict[int, list] = {}
    member: Dict[int, list] = {}
    for lc, f in contributions:
        for nl in lc.nodal_loads:
            acc = nodal.setdefault(nl.node, [0.0, 0.0, 0.0])
            acc[0] += f * nl.fx
            acc[1] += f * nl.fy
            acc[2] += f * nl.fz
        for ml in lc.member_loads:
            acc = member.setdefault(ml.member, [0.0, 0.0, 0.0])
            acc[0] += f * ml.qx
            acc[1] += f * ml.qy
            acc[2] += f * ml.qz
    nodal = {n: tuple(v) for n, v in nodal.items()
             if any(abs(c) > 1e-9 for c in v)}
    member = {m: tuple(v) for m, v in member.items()
              if any(abs(c) > 1e-9 for c in v)}
    return nodal, member


def _add_load_arrows(fig, model, selection):
    """Overlay the applied loads of *selection* (a load-case or combination
    name) as direction arrows; magnitudes appear on hover."""
    nodal, member = effective_loads(model, selection)
    diag = _model_diagonal(model)
    shaft = 0.07 * diag                       # display length, geometry-scaled
    head = 0.45                               # cone head as a fraction of shaft
    colour = "#d62728"

    sx, sy, sz, hx, hy, hz, htext = [], [], [], [], [], [], []

    def _arrow(x, y, z, vx, vy, vz, label):
        norm = (vx * vx + vy * vy + vz * vz) ** 0.5
        if norm < 1e-9:
            return
        ux, uy, uz = vx / norm, vy / norm, vz / norm    # load direction
        # tail back from the node so the arrow tip lands on the point
        tx, ty, tz = x - ux * shaft, y - uy * shaft, z - uz * shaft
        sx.extend([tx, x, None]); sy.extend([ty, y, None]); sz.extend([tz, z, None])
        hx.append(x - ux * shaft * head)
        hy.append(y - uy * shaft * head)
        hz.append(z - uz * shaft * head)
        htext.append(label)

    for nid, (fx, fy, fz) in nodal.items():
        n = model.nodes[nid]
        mag = (fx * fx + fy * fy + fz * fz) ** 0.5
        _arrow(n.x, n.y, n.z, fx, fy, fz,
               f"<b>node {nid}</b><br>F = {mag/1e3:.2f} kN"
               f"<br>(Fx {fx/1e3:.2f}, Fy {fy/1e3:.2f}, Fz {fz/1e3:.2f}) kN")
    for mid, (qx, qy, qz) in member.items():
        m = model.members.get(mid)
        if m is None:
            continue
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        L = model.member_length(m)
        wtot = (qx * qx + qy * qy + qz * qz) ** 0.5 * L
        for t in (0.25, 0.5, 0.75):           # a few arrows along the span
            _arrow(ni.x + t * (nj.x - ni.x), ni.y + t * (nj.y - ni.y),
                   ni.z + t * (nj.z - ni.z), qx, qy, qz,
                   f"<b>member {mid}</b> UDL<br>"
                   f"w = {((qx*qx+qy*qy+qz*qz)**0.5):.3f} N/mm"
                   f"<br>total = {wtot/1e3:.2f} kN")

    if sx:
        fig.add_trace(go.Scatter3d(
            x=sx, y=sy, z=sz, mode="lines",
            line=dict(color=colour, width=4), hoverinfo="skip",
            name="loads"))
        fig.add_trace(go.Cone(
            x=hx, y=hy, z=hz,
            u=[s2 - s1 for s1, s2 in zip(sx[0::3], sx[1::3])],
            v=[s2 - s1 for s1, s2 in zip(sy[0::3], sy[1::3])],
            w=[s2 - s1 for s1, s2 in zip(sz[0::3], sz[1::3])],
            sizemode="absolute", sizeref=shaft * head,
            anchor="tip", showscale=False,
            colorscale=[[0, colour], [1, colour]],
            text=htext, hoverinfo="text", name="load arrows"))
    return fig


def figure_for_loads(model, selection, show_loads=True):
    """Undeformed model with the applied loads of a chosen load case or
    combination overlaid as arrows (for verifying the load definition)."""
    fig = go.Figure()
    ux, uy, uz = [], [], []
    for m in model.members.values():
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        ux += [ni.x, nj.x, None]
        uy += [ni.y, nj.y, None]
        uz += [ni.z, nj.z, None]
    fig.add_trace(go.Scatter3d(x=ux, y=uy, z=uz, mode="lines",
                               line=dict(color="#8a8a8a", width=3),
                               hoverinfo="skip", name="model"))
    # support markers for orientation
    sup = {s.node for s in model.supports}
    if sup:
        fig.add_trace(go.Scatter3d(
            x=[model.nodes[n].x for n in sup],
            y=[model.nodes[n].y for n in sup],
            z=[model.nodes[n].z for n in sup],
            mode="markers",
            marker=dict(size=5, color="black", symbol="diamond"),
            hoverinfo="skip", name="supports"))
    if show_loads:
        _add_load_arrows(fig, model, selection)
    fig.update_layout(
        title=f"Applied loads — {selection}", showlegend=False, height=650,
        margin=dict(l=0, r=0, t=30, b=0),
        scene=dict(xaxis_title="X down-aisle [mm]",
                   yaxis_title="Y cross-aisle [mm]",
                   zaxis_title="Z [mm]", aspectmode="data"))
    return fig


def figure_for_case(model, case, checks, scale=1.0, show_only=None):
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
                        scale, f"{case.name} (×{scale:g})", show_only=show_only)


def figure_for_envelope(model, env, scale=1.0, show_only=None):
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
                        scale, f"{env.name} envelope (×{scale:g})",
                        show_only=show_only)

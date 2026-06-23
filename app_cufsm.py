"""CUFSM design & handoff UI for the EN 15512 storage-rack pipeline.

Run with:  streamlit run app_cufsm.py

A focused page for the *sections/DSM* leg of the workflow:

  1. define the perforated upright (gross + net properties, material);
  2. (optionally) generate a plain-section node/strip geometry to start the
     CUFSM model from;
  3. import the CUFSM signature curve, pick the local & distortional minima;
  4. compute the Direct Strength Method resistances (rack15512.dsm);
  5. hand off the result - as a DSMData snippet / JSON, or written straight
     into a rack model JSON's section so the EN 15512 checks pick it up.

CUFSM itself is run by you (https://www.ce.jhu.edu/cufsm/); this page consumes
its signature-curve export.  The global buckling load comes from the frame
analysis, not CUFSM (see rack15512.cufsm)."""

from __future__ import annotations

import json
import math
import os
import tempfile

import streamlit as st

from rack15512 import branding as B
from rack15512 import cufsm, dsm, io_json, ui
from rack15512.model import CrossSection, DSMData, Steel

st.set_page_config(page_title=f"{B.COMPANY} · CUFSM → DSM",
                   layout="wide", initial_sidebar_state="expanded")

ss = st.session_state
ss.setdefault("dark_mode", ui.load_dark_pref())
ui.apply_theme()


# ----------------------------------------------------------------- helpers
def parse_two_columns(text: str, hw_col: int = 0, val_col: int = 1):
    """Parse pasted signature data: lines of 'half_wavelength <sep> value'.
    Skips blanks, headers and comments; sep is comma / tab / whitespace."""
    hw, val = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p for p in line.replace(",", " ").replace("\t", " ").split()
                 if p]
        if len(parts) <= max(hw_col, val_col):
            continue
        try:
            h = float(parts[hw_col])
            v = float(parts[val_col])
        except ValueError:
            continue                       # header / non-numeric row
        hw.append(h)
        val.append(v)
    return hw, val


def signature_figure(hw, val, minima, local, dist):
    """Plotly signature curve (log half-wavelength) with the minima marked."""
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hw, y=val, mode="lines+markers",
                             name="signature curve",
                             line=dict(color=B.TEAL, width=2),
                             marker=dict(size=5, color=B.TEAL_LIGHT)))
    if minima:
        fig.add_trace(go.Scatter(
            x=[m[0] for m in minima], y=[m[1] for m in minima],
            mode="markers", name="minima",
            marker=dict(size=11, color="rgba(0,0,0,0)",
                        line=dict(color=B.GREY, width=1.5))))
    if local:
        fig.add_trace(go.Scatter(x=[local[0]], y=[local[1]], mode="markers+text",
                                 name="local", text=["local"],
                                 textposition="top center",
                                 marker=dict(size=14, color="#2E7DD1")))
    if dist:
        fig.add_trace(go.Scatter(x=[dist[0]], y=[dist[1]], mode="markers+text",
                                 name="distortional", text=["distortional"],
                                 textposition="top center",
                                 marker=dict(size=14, color="#E08A1E")))
    fig.update_xaxes(type="log", title="buckle half-wavelength [mm]")
    fig.update_yaxes(title="buckling load / moment")
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10),
                      legend=dict(orientation="h", y=1.12),
                      paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)")
    return fig


def lipped_channel_strips(h, b, c, t, n_web=8, n_flange=4, n_lip=2):
    """Midline node coordinates and strip connectivity for a plain lipped
    channel (rack-upright starting geometry), as a starting point for the
    CUFSM model.  Returns (nodes, strips): nodes = [(x, y)], strips =
    [(node_i, node_j, thickness)].  Add corner radii and perforations in CUFSM."""
    nodes, strips = [], []

    def _add_line(p0, p1, nseg):
        (x0, y0), (x1, y1) = p0, p1
        first = len(nodes)
        if not nodes or nodes[-1] != (x0, y0):
            nodes.append((x0, y0))
            first = len(nodes) - 1
        for k in range(1, nseg + 1):
            xk = x0 + (x1 - x0) * k / nseg
            yk = y0 + (y1 - y0) * k / nseg
            nodes.append((round(xk, 4), round(yk, 4)))
        idx = list(range(first, len(nodes)))
        for a, bb in zip(idx[:-1], idx[1:]):
            strips.append((a, bb, t))

    # open C: top lip -> top flange -> web -> bottom flange -> bottom lip
    _add_line((b, c), (b, 0.0), n_lip)
    _add_line((b, 0.0), (0.0, 0.0), n_flange)
    _add_line((0.0, 0.0), (0.0, h), n_web)
    _add_line((0.0, h), (b, h), n_flange)
    _add_line((b, h), (b, h - c), n_lip)
    return nodes, strips


def _fmt(x, nd=1):
    return f"{x:,.{nd}f}"


# ------------------------------------------------------------------- header
left, right = st.columns([0.8, 0.2])
with left:
    ui.hero("CUFSM → Direct Strength Method",
            subtitle="Local & distortional design of perforated uprights, and "
                     "handoff into the EN 15512 rack checks",
            eyebrow=f"{B.COMPANY} · {B.PRODUCT}")
with right:
    ui.theme_toggle()

st.caption("CUFSM is run by you (ce.jhu.edu/cufsm); this page reads its "
           "signature-curve export. Global buckling comes from the frame "
           "analysis, not CUFSM. Units: N, mm, MPa.")

tab_sec, tab_geo, tab_sig, tab_dsm, tab_out = st.tabs(
    ["1 · Section", "2 · CUFSM geometry", "3 · Signature curve",
     "4 · DSM strength", "5 · Handoff"])


# ----------------------------------------------------------------- 1 · section
with tab_sec:
    ui.section("◫", "Upright section & material")
    c1, c2, c3 = st.columns(3)
    with c1:
        name = st.text_input("Section name", "UP-100x90x2.0", key="name")
        fy = st.number_input("f_y [MPa]", 100.0, 1200.0, 450.0, 5.0, key="fy")
        E = st.number_input("E [MPa]", 100000.0, 250000.0, 210000.0, 1000.0,
                            key="E")
    with c2:
        A = st.number_input("Gross area A [mm²]", 1.0, 1e5, 600.0, 10.0, key="A")
        Wely = st.number_input("W_el,y (local y) [mm³]", 0.0, 1e7, 21000.0,
                              500.0, key="Wely")
        Welz = st.number_input("W_el,z (local z) [mm³]", 0.0, 1e7, 14000.0,
                              500.0, key="Welz")
    with c3:
        Iy = st.number_input("I_y [mm⁴]", 0.0, 1e9, 1.05e6, 1e4, key="Iy")
        Iz = st.number_input("I_z [mm⁴]", 0.0, 1e9, 0.62e6, 1e4, key="Iz")
        Anet = st.number_input("Net area A_net [mm²] (perforations)", 1.0, 1e5,
                              540.0, 10.0, key="Anet",
                              help="Minimum net cross-section through a "
                                   "perforation. Set = A for an unperforated "
                                   "section.")
    cc1, cc2 = st.columns(2)
    with cc1:
        Wnet_z = st.number_input("W_net,z [mm³] (0 = use gross)", 0.0, 1e7, 0.0,
                               500.0, key="Wnetz")
    with cc2:
        Wnet_y = st.number_input("W_net,y [mm³] (0 = use gross)", 0.0, 1e7, 0.0,
                               500.0, key="Wnety")
    ui.stat_strip([("P_y = A·f_y", f"{_fmt(A*fy/1e3)} kN"),
                   ("P_ynet = A_net·f_y", f"{_fmt(Anet*fy/1e3)} kN"),
                   ("hole loss", f"{_fmt((1-Anet/A)*100,1)} %")])


# ------------------------------------------------------------ 2 · CUFSM geometry
with tab_geo:
    ui.section("⇪", "Import a DXF → CUFSM nodes & elements")
    st.write("Draw or export the section **midline** in CAD (lines, polylines, "
             "arcs) and import it to build the CUFSM mesh — far faster than "
             "entering nodes by hand. Thickness is assigned per CAD layer.")
    from rack15512 import dxf_section as _dx
    dxf_up = st.file_uploader(
        "DXF (LINE / LWPOLYLINE / POLYLINE / ARC / CIRCLE; explode splines "
        "first)", type=["dxf"], key="dxf")
    if dxf_up is not None:
        dtext = dxf_up.getvalue().decode("utf-8", errors="ignore")
        try:
            _polys = _dx.entity_polylines(_dx.parse_dxf_entities(dtext))
            _layers = sorted({lay for _p, lay, _c in _polys})
        except Exception as exc:        # noqa: BLE001 - surface any parse error
            st.error(f"could not read the DXF: {exc}")
            _polys, _layers = [], []
        if _polys:
            d1, d2, d3 = st.columns(3)
            ddt = d1.number_input("default thickness [mm]", 0.1, 12.0, 2.0,
                                  0.1, key="dxft")
            dseg = d2.number_input("arc segment angle [°]", 2.0, 45.0, 12.0,
                                   1.0, key="dxfseg")
            drec = d3.checkbox("recentre to CG (thickness-weighted)",
                               value=False, key="dxfcg",
                               help="Translate every node so the section's "
                                    "centre of gravity sits at the origin; the "
                                    "CG is weighted by each element's thickness.")
            lt = {}
            if _layers:
                st.caption(f"Layers: {', '.join(_layers)} — set a thickness per "
                           "layer (0 = use the default).")
                lc = st.columns(min(len(_layers), 4))
                for _i, lay in enumerate(_layers):
                    _v = lc[_i % len(lc)].number_input(
                        f"t · {lay} [mm]", 0.0, 12.0, 0.0, 0.1, key=f"lt_{lay}")
                    if _v > 0:
                        lt[lay] = _v
            try:
                mesh = _dx.dxf_to_mesh(dtext, default_t=ddt, layer_thickness=lt,
                                       seg_angle=dseg, recenter=drec)
            except Exception as exc:    # noqa: BLE001
                st.error(f"mesh build failed: {exc}")
                mesh = None
            if mesh is not None:
                mv1, mv2 = st.columns([0.55, 0.45])
                with mv1:
                    import plotly.graph_objects as go
                    fig = go.Figure()
                    for i, j, _t in mesh.elems:
                        fig.add_trace(go.Scatter(
                            x=[mesh.nodes[i][0], mesh.nodes[j][0]],
                            y=[mesh.nodes[i][1], mesh.nodes[j][1]],
                            mode="lines", line=dict(color=B.TEAL, width=3),
                            showlegend=False))
                    if drec:
                        fig.add_trace(go.Scatter(
                            x=[0], y=[0], mode="markers+text", text=["CG"],
                            textposition="top center", showlegend=False,
                            marker=dict(size=11, color="#E08A1E", symbol="x")))
                    fig.update_yaxes(scaleanchor="x", scaleratio=1)
                    fig.update_layout(height=380, title="DXF → CUFSM mesh",
                                      margin=dict(l=10, r=10, t=30, b=10),
                                      paper_bgcolor="rgba(0,0,0,0)",
                                      plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, width="stretch")
                with mv2:
                    ui.stat_strip([("nodes", len(mesh.nodes)),
                                   ("elements", len(mesh.elems)),
                                   ("layers", len(mesh.layers))])
                    if mesh.centroid_removed:
                        cgx, cgy = mesh.centroid_removed
                        st.caption(f"recentred — original CG "
                                   f"({cgx:.2f}, {cgy:.2f}) mm")
                    cufsm_text = _dx.mesh_to_cufsm_text(mesh)
                    st.download_button("Download CUFSM model (.txt)", cufsm_text,
                                       file_name="cufsm_model.txt",
                                       mime="text/plain")
                    st.text_area("CUFSM nodes & elements", cufsm_text,
                                 height=190)
    st.divider()

    ui.section("⊏", "Or generate a plain lipped-channel geometry (optional)")
    st.write("Generate the midline node/strip geometry of a **plain** lipped "
             "channel to seed the CUFSM model, then add corner radii and the "
             "perforation pattern inside CUFSM.")
    g1, g2, g3, g4 = st.columns(4)
    gh = g1.number_input("web h [mm]", 10.0, 400.0, 100.0, 1.0, key="gh")
    gb = g2.number_input("flange b [mm]", 10.0, 200.0, 90.0, 1.0, key="gb")
    gc = g3.number_input("lip c [mm]", 0.0, 60.0, 18.0, 1.0, key="gc")
    gt = g4.number_input("thickness t [mm]", 0.5, 6.0, 2.0, 0.1, key="gt")
    nodes, strips = lipped_channel_strips(gh, gb, gc, gt)
    gv1, gv2 = st.columns([0.5, 0.5])
    with gv1:
        import plotly.graph_objects as go
        outline = go.Figure()
        xs = [n[0] for n in nodes]
        ys = [n[1] for n in nodes]
        outline.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers",
                                     line=dict(color=B.TEAL, width=3),
                                     marker=dict(size=5)))
        outline.update_yaxes(scaleanchor="x", scaleratio=1,
                             title="y [mm]")
        outline.update_xaxes(title="x [mm]")
        outline.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10),
                             paper_bgcolor="rgba(0,0,0,0)",
                             plot_bgcolor="rgba(0,0,0,0)",
                             title="midline outline")
        st.plotly_chart(outline, width="stretch")
    with gv2:
        node_csv = "node,x_mm,y_mm\n" + "\n".join(
            f"{i+1},{x},{y}" for i, (x, y) in enumerate(nodes))
        elem_csv = "elem,node_i,node_j,t_mm\n" + "\n".join(
            f"{k+1},{i+1},{j+1},{t}" for k, (i, j, t) in enumerate(strips))
        st.text_area("nodes (x, y) [mm]", node_csv, height=150)
        st.text_area("strips (node_i, node_j, t)", elem_csv, height=120)
        st.download_button("Download nodes.csv", node_csv,
                          file_name="cufsm_nodes.csv", mime="text/csv")
        st.download_button("Download strips.csv", elem_csv,
                          file_name="cufsm_strips.csv", mime="text/csv")
    st.info("This is a plain (unperforated, sharp-corner) starting geometry. "
            "Reproduce it in CUFSM, add the rounded corners and the upright's "
            "perforation pattern (or an equivalent reduced thickness), then run "
            "the signature curve.")

    st.divider()
    ui.section("✓", "Validate a CUFSM model → section properties (EN 15512 9.7.5)")
    st.write("Upload the CUFSM **model** (node + element mesh) to compute the "
             "full property set — A, I, **J, Cw, shear centre, i₀** — and check "
             "it against the Section-tab values. These populate the gross "
             "torsion/warping/shear-centre the flexural-torsional buckling "
             "check needs.")
    mdl = st.file_uploader("CUFSM model: [nodes]/[elements] blocks, or the raw "
                          "8-col node / 5-col element matrices",
                          type=["txt", "csv", "dat"], key="cufsmmodel")
    if mdl is not None:
        try:
            nn, ee = cufsm.parse_cufsm_model(
                mdl.getvalue().decode("utf-8", errors="ignore").splitlines())
            props = cufsm.properties_from_cufsm((nn, ee))
        except (ValueError, KeyError) as exc:
            st.error(f"could not read the CUFSM model: {exc}")
            props = None
        if props is not None:
            mc1, mc2 = st.columns([0.45, 0.55])
            with mc1:
                import plotly.graph_objects as go
                mesh = go.Figure()
                for i, j, _t in ee:
                    mesh.add_trace(go.Scatter(
                        x=[nn[i][0], nn[j][0]], y=[nn[i][1], nn[j][1]],
                        mode="lines", line=dict(color=B.TEAL, width=3),
                        showlegend=False))
                mesh.add_trace(go.Scatter(
                    x=[props.xc + props.x_sc], y=[props.yc + props.y_sc],
                    mode="markers+text", text=["shear centre"],
                    textposition="top center", showlegend=False,
                    marker=dict(size=12, color="#E08A1E", symbol="x")))
                mesh.add_trace(go.Scatter(
                    x=[props.xc], y=[props.yc], mode="markers+text",
                    text=["centroid"], textposition="bottom center",
                    showlegend=False, marker=dict(size=9, color=B.GREY)))
                mesh.update_yaxes(scaleanchor="x", scaleratio=1)
                mesh.update_layout(height=360, title="CUFSM mesh",
                                  margin=dict(l=10, r=10, t=30, b=10),
                                  paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(mesh, width="stretch")
            with mc2:
                ui.stat_strip([
                    ("A", f"{_fmt(props.A,0)} mm²"),
                    ("J (It)", f"{_fmt(props.J,0)} mm⁴"),
                    ("Cw (Iw)", f"{props.Cw:,.3g} mm⁶")])
                ui.stat_strip([
                    ("I_major", f"{props.I1:,.4g}"),
                    ("I_minor", f"{props.I2:,.4g}"),
                    ("shear-centre offset",
                     f"{_fmt(math.hypot(props.x_sc, props.y_sc),1)} mm"),
                    ("i₀", f"{_fmt(props.i0,1)} mm")])
                if props.closed:
                    st.warning("a closed cell was detected — the shear centre / "
                               "Cw assume an open section; review.")
            # validate against the Section-tab inputs (A, I); J/Cw/y0 are new
            sec = CrossSection(name, "steel", A, Iy, Iz, props.J, Wely, Welz)
            report = cufsm.validate_properties(props, sec)
            st.markdown(cufsm.validation_markdown(report))
            st.code(
                "from rack15512 import cufsm\n"
                "# fill It_gross / Iw_gross / y0 (EN 15512 9.7.5 inputs):\n"
                "props = cufsm.properties_from_cufsm('your_model.txt')\n"
                "cufsm.populate_gross_properties(section, props)",
                language="python")
            st.download_button(
                "Download section_properties.json",
                json.dumps({"A": props.A, "Ix": props.Ix, "Iy": props.Iy,
                            "I_major": props.I1, "I_minor": props.I2,
                            "J": props.J, "Cw": props.Cw,
                            "x_sc": props.x_sc, "y_sc": props.y_sc,
                            "i0": props.i0}, indent=2),
                file_name=f"{name}_section_properties.json",
                mime="application/json")


# ----------------------------------------------------------- 3 · signature curve
with tab_sig:
    ui.section("∿", "CUFSM signature curve → local & distortional")
    mode = st.radio("Input", ["Upload CSV/TXT", "Paste two columns",
                              "Enter the two minima directly"],
                    horizontal=True, key="sigmode")
    unit = st.radio("Value column is",
                    ["buckling load / moment (already in N or N·mm)",
                     "load factor × reference"], horizontal=True, key="unit")
    reference = 1.0
    if unit.startswith("load factor"):
        reference = st.number_input("reference load/moment", 0.0, 1e12, 1.0,
                                   key="ref")

    hw, val = [], []
    direct = None
    if mode == "Upload CSV/TXT":
        up = st.file_uploader("CUFSM signature export (2 columns: "
                              "half-wavelength, value)", type=["csv", "txt"])
        if up is not None:
            text = up.getvalue().decode("utf-8", errors="ignore")
            hw, val = parse_two_columns(text)
    elif mode == "Paste two columns":
        text = st.text_area("half_wavelength  value   (one pair per line)",
                            "80   360000\n350  340000\n…", height=160)
        hw, val = parse_two_columns(text)
    else:
        d1, d2 = st.columns(2)
        pcrl = d1.number_input("P_crl (local) [N]", 0.0, 1e9, 360000.0, 1000.0)
        pcrd = d2.number_input("P_crd (distortional) [N]", 0.0, 1e9, 340000.0,
                              1000.0)
        direct = (pcrl, pcrd)

    Pcrl = Pcrd = None
    if direct is not None:
        Pcrl, Pcrd = direct
        ss["Pcrl"], ss["Pcrd"] = Pcrl, Pcrd
        ui.stat_strip([("P_crl (local)", f"{_fmt(Pcrl/1e3)} kN"),
                       ("P_crd (distortional)", f"{_fmt(Pcrd/1e3)} kN")])
    elif hw and val:
        minima = cufsm.signature_minima(hw, val)
        if not minima:
            st.warning("No interior minimum found - the half-wavelength range "
                       "must cover the local and distortional modes (the "
                       "descending long-wave global branch has no minimum).")
        else:
            labels = [f"{m[0]:g} mm  →  {m[1]*reference:,.0f}" for m in minima]
            auto_l, auto_d = cufsm.classify_minima(minima)
            il = st.selectbox("local minimum", range(len(minima)),
                             format_func=lambda i: labels[i],
                             index=minima.index(auto_l) if auto_l else 0)
            id_opts = list(range(len(minima)))
            id_default = minima.index(auto_d) if auto_d else min(1, len(minima)-1)
            idd = st.selectbox("distortional minimum", id_opts,
                              format_func=lambda i: labels[i], index=id_default)
            local, dist = minima[il], minima[idd]
            Pcrl, Pcrd = local[1] * reference, dist[1] * reference
            ss["Pcrl"], ss["Pcrd"] = Pcrl, Pcrd
            st.plotly_chart(signature_figure(hw, val, minima, local, dist),
                           width="stretch")
            ui.stat_strip([("P_crl (local)", f"{_fmt(Pcrl/1e3)} kN"),
                           ("P_crd (distortional)", f"{_fmt(Pcrd/1e3)} kN")])
    else:
        st.caption("Provide the signature curve or enter the two minima.")


# -------------------------------------------------------------- 4 · DSM strength
with tab_dsm:
    ui.section("∑", "Direct Strength Method (AISI S100-16 + holes)")
    Pcrl = ss.get("Pcrl")
    Pcrd = ss.get("Pcrd")
    if not Pcrl or not Pcrd:
        ui.empty_state("∿", "No buckling loads yet",
                       "Set the local / distortional loads on the "
                       "Signature curve tab first.")
    else:
        gcol1, gcol2, gcol3 = st.columns(3)
        gmode = gcol1.radio("Global elastic load P_cre",
                           ["Euler from panel length", "Enter directly"],
                           key="gmode")
        if gmode == "Enter directly":
            Pcre = gcol2.number_input("P_cre [N]", 0.0, 1e9, 571000.0, 1000.0)
            Lnote = "entered"
        else:
            L = gcol2.number_input("panel length L [mm] (beam-level spacing)",
                                  100.0, 12000.0, 1500.0, 50.0, key="Lpanel")
            import math
            Pcre = math.pi ** 2 * E * min(Iy, Iz) / L ** 2
            Lnote = f"Euler, L={L:.0f} mm, I=min(I_y,I_z)"
        gM1 = gcol3.number_input("γ_M1", 1.0, 1.5, 1.1, 0.05, key="gM1",
                                help="EN 15512 member partial factor applied "
                                     "to the DSM nominal strength.")
        col = dsm.column_strength(A * fy, Pcre, Pcrl, Pcrd, Pynet=Anet * fy)
        Nb_rd = col.Pn / gM1
        ui.stat_strip([
            ("P_cre", f"{_fmt(Pcre/1e3)} kN"),
            ("P_n", f"{_fmt(col.Pn/1e3)} kN"),
            ("governs", col.governs),
            ("N_b,Rd = P_n/γ_M1", f"{_fmt(Nb_rd/1e3)} kN")])
        st.markdown(
            ui.tile("P_ne (global)", f"{_fmt(col.Pne/1e3)} kN")
            + ui.tile("P_nl (local)", f"{_fmt(col.Pnl/1e3)} kN")
            + ui.tile("P_nd (distortional)", f"{_fmt(col.Pnd/1e3)} kN"),
            unsafe_allow_html=True)
        st.caption(f"P_cre source: {Lnote}.  P_n = min(P_ne, P_nl, P_nd) "
                   "(AISI S100-16 E2/E3/E4, members-with-holes capped at "
                   "P_ynet).")
        A_eff = cufsm.effective_area(
            CrossSection(name, "steel", A, Iy, Iz, 1.0, Wely, Welz),
            Steel("steel", fy=fy),
            cufsm.BucklingLoads(Pcrl=Pcrl, Pcrd=Pcrd), Anet=Anet)
        st.success(f"DSM effective area A_eff = **{_fmt(A_eff,0)} mm²** "
                   f"(gross {_fmt(A,0)} mm²) — this can populate the EN 15512 "
                   f"effective-section STRESS / BUCKLING checks.")
        ss["A_eff"] = A_eff


# ----------------------------------------------------------------- 5 · handoff
with tab_out:
    ui.section("⇨", "Handoff to the EN 15512 rack model")
    Pcrl = ss.get("Pcrl")
    Pcrd = ss.get("Pcrd")
    if not Pcrl or not Pcrd:
        ui.empty_state("⇨", "Nothing to hand off yet",
                       "Compute the buckling loads first.")
    else:
        dsm_kwargs = dict(Pcrl=float(Pcrl), Pcrd=float(Pcrd), Anet=float(Anet))
        if Wnet_z > 0:
            dsm_kwargs["Wnet_z"] = float(Wnet_z)
        if Wnet_y > 0:
            dsm_kwargs["Wnet_y"] = float(Wnet_y)
        kw = ", ".join(f"{k}={v:g}" for k, v in dsm_kwargs.items())
        snippet = (
            "from rack15512.model import DSMData\n"
            "from rack15512 import cufsm\n\n"
            f"# attach the CUFSM/DSM data to the '{name}' section\n"
            f"section.dsm = DSMData({kw})\n\n"
            "# …or let it populate the EN 15512 effective area directly:\n"
            "cufsm.populate_effective_properties(\n"
            "    section, steel,\n"
            f"    axial=cufsm.BucklingLoads(Pcrl={Pcrl:g}, Pcrd={Pcrd:g}),\n"
            f"    Anet={Anet:g})")
        st.markdown("**Python** — attach to a `CrossSection` in the library:")
        st.code(snippet, language="python")

        st.markdown("**JSON** — the section's `dsm` field (paste into a model "
                    "file, or use the writer below):")
        st.code(json.dumps(dsm_kwargs, indent=2), language="json")
        st.download_button(
            f"Download {name}.dsm.json",
            json.dumps({"section": name, "dsm": dsm_kwargs}, indent=2),
            file_name=f"{name}.dsm.json", mime="application/json")

        st.divider()
        st.markdown("**Write into a rack model JSON** — upload a model, choose "
                    "a section, and download it with the `dsm` data attached:")
        mfile = st.file_uploader("rack model JSON (rack15512 io_json format)",
                                type=["json"], key="modeljson")
        if mfile is not None:
            try:
                model = io_json.model_from_dict(
                    json.loads(mfile.getvalue().decode("utf-8")))
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                st.error(f"could not read model: {exc}")
                model = None
            if model and model.sections:
                target = st.selectbox("section to update",
                                     sorted(model.sections))
                also_eff = st.checkbox(
                    "also populate A_eff (effective-section checks)", True)
                if st.button("Attach DSM data and prepare download",
                            type="primary"):
                    sec = model.sections[target]
                    sec.dsm = DSMData(**dsm_kwargs)
                    if also_eff:
                        steel = model.materials.get(sec.material) \
                            or Steel(sec.material, fy=fy)
                        cufsm.populate_effective_properties(
                            sec, steel,
                            axial=cufsm.BucklingLoads(Pcrl=Pcrl, Pcrd=Pcrd),
                            Anet=Anet, overwrite=True)
                    out = json.dumps(io_json.model_to_dict(model), indent=2)
                    st.success(f"DSM data attached to '{target}'"
                               + (f"; A_eff set to {sec.A_eff:.0f} mm²"
                                  if also_eff and sec.A_eff else ""))
                    st.download_button("Download updated model JSON", out,
                                      file_name=mfile.name.replace(
                                          ".json", "") + "_dsm.json",
                                      mime="application/json")
            elif model:
                st.warning("the uploaded model has no sections")

        st.divider()
        st.markdown("**Write into a stored master** — pick a saved master and "
                    "upright; the Pcrl/Pcrd (A_eff + DSM) above, plus J/Cw/y0 "
                    "from an optional CUFSM model, are imported and saved for "
                    "the main app.")
        from rack15512.master_store import MasterStore
        store = MasterStore("masters")
        mids = [m.id for m in store.list()]
        if not mids:
            st.caption("No stored masters found — import one in the main app's "
                       "**Section masters** page first.")
        else:
            smid = st.selectbox("Stored master", mids, key="storemaster")
            sm = store.load(smid)
            ups = sm.names("upright") or sm.names()
            if not ups:
                st.warning("this master has no sections")
            else:
                up_t = st.selectbox("Upright section", ups, key="storeup")
                modelf = st.file_uploader(
                    "CUFSM model for J/Cw/y0 (optional)",
                    type=["txt", "csv", "dat"], key="storemodel")
                if st.button("Import to master & save", type="primary",
                             key="storego"):
                    mpath = None
                    try:
                        if modelf is not None:
                            tf = tempfile.NamedTemporaryFile(suffix=".txt",
                                                             delete=False)
                            tf.write(modelf.getvalue())
                            tf.close()
                            mpath = tf.name
                        data = cufsm.CufsmData(
                            model=mpath,
                            signature=(float(Pcrl), float(Pcrd)),
                            Anet=float(Anet) or None)
                        report = sm.apply_cufsm(up_t, data, overwrite=True)
                        store.save(sm)
                        st.success(f"Imported into '{up_t}' of master "
                                   f"'{smid}' and saved.")
                        if report is not None:
                            st.markdown(cufsm.validation_markdown(report))
                    except Exception as exc:
                        st.error(f"import failed: {exc}")
                    finally:
                        if mpath and os.path.exists(mpath):
                            os.remove(mpath)

st.caption("DSM is a validated analytical route, but does not remove "
           "EN 15512's requirement to type-test the final perforated section. "
           f"{B.COMPANY} · {B.WEBSITE}")

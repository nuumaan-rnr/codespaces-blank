"""Streamlit UI: enter rack parameters, run the 3D analysis, view results.

    streamlit run streamlit_app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from rackapp.config import (
    AnalysisConfig, BracingConfig, CheckConfig, CombinationFactors,
    ConnectionConfig, GeometryConfig, ImperfectionConfig, LoadConfig,
    MaterialConfig, RackConfig, SectionConfig,
)
from rackapp.pipeline import run
from rackapp.report import to_markdown
from rackapp.viz import plot_deformed, plot_model, plot_utilization

st.set_page_config(page_title="Rack EN 15512", layout="wide")
st.title("Storage rack - 3D second-order analysis & EN 15512 checks")

with st.sidebar:
    st.header("Geometry")
    n_bays = st.number_input("Bays", 1, 20, 3)
    bay_width = st.number_input("Bay width [m]", 0.5, 5.0, 2.7, 0.05)
    depth = st.number_input("Frame depth [m]", 0.5, 2.5, 1.1, 0.05)
    n_levels = st.number_input("Beam levels", 1, 12, 4)
    level_h = st.number_input("Level spacing [m]", 0.5, 3.0, 1.5, 0.05)
    brace_pattern = st.selectbox("Frame bracing", ["z", "none"])
    panel_h = st.number_input("Brace panel height [m]", 0.3, 3.0, 1.0, 0.05)

    st.header("Upright (effective props)")
    up_A = st.number_input("A [cm2]", 1.0, 100.0, 6.5, key="ua") * 1e-4
    up_Iy = st.number_input("Iy down-aisle [cm4]", 1.0, 5000.0, 110.0, key="ui") * 1e-8
    up_Wy = st.number_input("Wy [cm3]", 0.5, 1000.0, 22.0, key="uw") * 1e-6
    up_Iz = st.number_input("Iz cross-aisle [cm4]", 1.0, 5000.0, 60.0, key="uiz") * 1e-8
    up_Wz = st.number_input("Wz [cm3]", 0.5, 1000.0, 14.0, key="uwz") * 1e-6
    up_g = st.number_input("Self weight [kg/m]", 0.0, 50.0, 5.1, key="ug")

    st.header("Beam (effective props)")
    bm_A = st.number_input("A [cm2]", 1.0, 100.0, 4.6, key="ba") * 1e-4
    bm_Iy = st.number_input("Iy major [cm4]", 1.0, 5000.0, 80.0, key="bi") * 1e-8
    bm_Wy = st.number_input("Wy [cm3]", 0.5, 1000.0, 14.5, key="bw") * 1e-6
    bm_Iz = st.number_input("Iz minor [cm4]", 1.0, 5000.0, 30.0, key="biz") * 1e-8
    bm_Wz = st.number_input("Wz [cm3]", 0.5, 1000.0, 8.0, key="bwz") * 1e-6
    bm_g = st.number_input("Self weight [kg/m]", 0.0, 50.0, 3.8, key="bg")

    st.header("Brace")
    br_A = st.number_input("A [cm2]", 0.2, 50.0, 2.0, key="bra") * 1e-4
    br_I = st.number_input("I min [cm4]", 0.05, 500.0, 2.0, key="bri") * 1e-8
    br_g = st.number_input("Self weight [kg/m]", 0.0, 20.0, 1.6, key="brg")

    st.header("Material")
    fy = st.number_input("fy [MPa]", 200.0, 700.0, 355.0)
    E = st.number_input("E [GPa]", 180.0, 220.0, 210.0)

    st.header("Connections (from tests)")
    k_conn = st.number_input("Connector stiffness [kNm/rad]", 1.0, 1000.0, 110.0)
    phi_l = st.number_input("Connector looseness [mrad]", 0.0, 20.0, 5.0) / 1e3
    m_rd = st.number_input("Connector M_Rd [kNm] (0 = skip)", 0.0, 50.0, 2.4)
    k_base = st.number_input("Base stiffness [kNm/rad]", 0.0, 5000.0, 150.0)

    st.header("Loads")
    q_unit = st.number_input("Unit load per beam [kN]", 0.5, 100.0, 5.0)
    q_place = st.number_input("Placement load [kN]", 0.0, 5.0, 0.5)

    st.header("Imperfection / analysis")
    oop = st.number_input("Out-of-plumb 1/x (down-aisle)", 100.0, 1000.0, 350.0)
    oop_c = st.number_input("Out-of-plumb 1/x (cross-aisle)", 100.0, 1000.0, 500.0)
    second_order = st.checkbox("Second-order (P-Delta) at ULS", True)

cfg = RackConfig(
    name="Streamlit rack",
    geometry=GeometryConfig(
        n_bays=int(n_bays), bay_width=bay_width, depth=depth,
        level_heights=[level_h] * int(n_levels),
        bracing=BracingConfig(pattern=brace_pattern, panel_height=panel_h)),
    upright_section=SectionConfig("Upright", up_A, up_Iy, up_Wy, up_Iz, up_Wz,
                                  1e-8, up_g),
    beam_section=SectionConfig("Beam", bm_A, bm_Iy, bm_Wy, bm_Iz, bm_Wz,
                               1e-8, bm_g),
    brace_section=SectionConfig("Brace", br_A, br_I, br_I * 100, br_I,
                                br_I * 100, 1e-9, br_g),
    material=MaterialConfig(E=E * 1e9, fy=fy * 1e6),
    connections=ConnectionConfig(
        beam_end_stiffness=k_conn * 1e3, beam_end_looseness=phi_l,
        beam_end_moment_resistance=m_rd * 1e3 if m_rd > 0 else None,
        base_stiffness=k_base * 1e3),
    loads=LoadConfig(unit_load_per_beam=q_unit * 1e3,
                     placement_load=q_place * 1e3),
    imperfections=ImperfectionConfig(out_of_plumb=1.0 / oop,
                                     out_of_plumb_cross=1.0 / oop_c),
    factors=CombinationFactors(),
    analysis=AnalysisConfig(engine="internal", second_order=second_order),
    checks=CheckConfig(),
)

if st.button("Run analysis", type="primary"):
    with st.spinner("Solving..."):
        try:
            out = run(cfg)
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")
            st.stop()
    st.session_state["out"] = out

out = st.session_state.get("out")
if out:
    rep = out.report
    st.subheader("Verdict: " + ("PASS :white_check_mark:" if rep.all_passed
                                else "FAIL :x:"))
    for w in out.results.warnings + rep.warnings:
        st.warning(w)

    t_model, t_checks, t_forces, t_report = st.tabs(
        ["Model & deformation", "EN 15512 checks", "Forces & reactions", "Report"])

    with t_model:
        c1, c2 = st.columns(2)
        c1.pyplot(plot_model(out.model))
        combo_def = st.selectbox(
            "Deformed shape for",
            [c for c in out.results.combos], index=0)
        c2.pyplot(plot_deformed(out.model, out.results.combos[combo_def]))
        st.pyplot(plot_utilization(out.model, rep))

    with t_checks:
        df = pd.DataFrame([{
            "check": r.check, "combo": r.combo, "target": r.target,
            "utilization": round(r.ratio, 3),
            "status": "OK" if r.passed else "FAIL", "detail": r.note,
        } for r in rep.results]).sort_values("utilization", ascending=False)
        st.dataframe(df, use_container_width=True, height=480)

    with t_forces:
        combo_id = st.selectbox("Combination", list(out.results.combos))
        cr = out.results.combos[combo_id]
        st.markdown(f"**Member end forces** "
                    f"({'2nd' if cr.second_order else '1st'} order, "
                    f"{cr.iterations} iterations)")
        st.dataframe(pd.DataFrame([{
            "member": mid,
            "kind": out.model.members[mid].kind,
            "N1 [kN]": round(r.N1 / 1e3, 2), "N2 [kN]": round(r.N2 / 1e3, 2),
            "My1 [kNm]": round(r.My1 / 1e3, 2),
            "My2 [kNm]": round(r.My2 / 1e3, 2),
            "Mz1 [kNm]": round(r.Mz1 / 1e3, 2),
            "Mz2 [kNm]": round(r.Mz2 / 1e3, 2),
            "My max [kNm]": round(r.My_abs_max / 1e3, 2),
            "defl [mm]": round(r.defl_rel_max * 1e3, 1),
        } for mid, r in cr.members.items()]), use_container_width=True)
        st.markdown("**Base reactions**")
        st.dataframe(pd.DataFrame([{
            "node": nid,
            "Fx [kN]": round(rc.fx / 1e3, 2),
            "Fy [kN]": round(rc.fy / 1e3, 2),
            "Fz [kN]": round(rc.fz / 1e3, 2),
            "Mx [kNm]": round(rc.mx / 1e3, 2),
            "My [kNm]": round(rc.my / 1e3, 2),
        } for nid, rc in cr.reactions.items()]), use_container_width=True)

    with t_report:
        md = to_markdown(out.cfg, out.model, out.results, rep)
        st.download_button("Download report.md", md, "report.md")
        st.markdown(md)
else:
    st.info("Set the parameters in the sidebar and press **Run analysis**.")

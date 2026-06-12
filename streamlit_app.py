"""Streamlit UI: enter rack parameters, run the analysis, view results.

    streamlit run streamlit_app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from rackapp.config import (
    AnalysisConfig, CheckConfig, CombinationFactors, ConnectionConfig,
    GeometryConfig, ImperfectionConfig, LoadConfig, MaterialConfig,
    RackConfig, SectionConfig,
)
from rackapp.pipeline import run
from rackapp.report import to_markdown
from rackapp.viz import plot_deformed, plot_model, plot_utilization

st.set_page_config(page_title="Rack EN 15512", layout="wide")
st.title("Storage rack - 2nd order analysis & EN 15512 checks")

with st.sidebar:
    st.header("Geometry")
    n_bays = st.number_input("Bays", 1, 20, 3)
    bay_width = st.number_input("Bay width [m]", 0.5, 5.0, 2.7, 0.05)
    n_levels = st.number_input("Beam levels", 1, 12, 4)
    level_h = st.number_input("Level spacing [m]", 0.5, 3.0, 1.5, 0.05)

    st.header("Upright (effective props)")
    up_A = st.number_input("A [cm2]", 1.0, 100.0, 6.5, key="ua") * 1e-4
    up_I = st.number_input("Iy [cm4]", 1.0, 5000.0, 110.0, key="ui") * 1e-8
    up_W = st.number_input("Wy [cm3]", 0.5, 1000.0, 22.0, key="uw") * 1e-6
    up_g = st.number_input("Self weight [kg/m]", 0.0, 50.0, 5.1, key="ug")

    st.header("Beam (effective props)")
    bm_A = st.number_input("A [cm2]", 1.0, 100.0, 4.6, key="ba") * 1e-4
    bm_I = st.number_input("Iy [cm4]", 1.0, 5000.0, 80.0, key="bi") * 1e-8
    bm_W = st.number_input("Wy [cm3]", 0.5, 1000.0, 14.5, key="bw") * 1e-6
    bm_g = st.number_input("Self weight [kg/m]", 0.0, 50.0, 3.8, key="bg")

    st.header("Material")
    fy = st.number_input("fy [MPa]", 200.0, 700.0, 355.0)
    E = st.number_input("E [GPa]", 180.0, 220.0, 210.0)

    st.header("Connections (from tests)")
    k_conn = st.number_input("Connector stiffness [kNm/rad]", 1.0, 1000.0, 110.0)
    phi_l = st.number_input("Connector looseness [mrad]", 0.0, 20.0, 5.0) / 1e3
    m_rd = st.number_input("Connector M_Rd [kNm] (0 = skip)", 0.0, 50.0, 2.4)
    k_base = st.number_input("Base stiffness [kNm/rad]", 0.0, 5000.0, 150.0)

    st.header("Loads")
    q_unit = st.number_input("Unit load per beam [kN]", 0.5, 100.0, 10.0)
    q_place = st.number_input("Placement load [kN]", 0.0, 5.0, 0.5)

    st.header("Imperfection / analysis")
    oop = st.number_input("Out-of-plumb 1/x", 100.0, 1000.0, 350.0)
    second_order = st.checkbox("Second-order (P-Delta) at ULS", True)

cfg = RackConfig(
    name="Streamlit rack",
    geometry=GeometryConfig(n_bays=int(n_bays), bay_width=bay_width,
                            level_heights=[level_h] * int(n_levels)),
    upright_section=SectionConfig("Upright", up_A, up_I, up_W, up_g),
    beam_section=SectionConfig("Beam", bm_A, bm_I, bm_W, bm_g),
    material=MaterialConfig(E=E * 1e9, fy=fy * 1e6),
    connections=ConnectionConfig(
        beam_end_stiffness=k_conn * 1e3, beam_end_looseness=phi_l,
        beam_end_moment_resistance=m_rd * 1e3 if m_rd > 0 else None,
        base_stiffness=k_base * 1e3),
    loads=LoadConfig(unit_load_per_beam=q_unit * 1e3,
                     placement_load=q_place * 1e3),
    imperfections=ImperfectionConfig(out_of_plumb=1.0 / oop),
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
        uls = next((c for c in out.results.combos.values()
                    if c.combo_id.startswith("ULS")), None)
        if uls:
            c2.pyplot(plot_deformed(out.model, uls))
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
            "M1 [kNm]": round(r.M1 / 1e3, 2), "M2 [kNm]": round(r.M2 / 1e3, 2),
            "Mmax [kNm]": round(r.M_abs_max / 1e3, 2),
            "defl [mm]": round(r.defl_rel_max * 1e3, 1),
        } for mid, r in cr.members.items()]), use_container_width=True)
        st.markdown("**Base reactions**")
        st.dataframe(pd.DataFrame([{
            "node": nid, "Fx [kN]": round(rc.fx / 1e3, 2),
            "Fz [kN]": round(rc.fz / 1e3, 2), "My [kNm]": round(rc.my / 1e3, 2),
        } for nid, rc in cr.reactions.items()]), use_container_width=True)

    with t_report:
        md = to_markdown(out.cfg, out.model, out.results, rep)
        st.download_button("Download report.md", md, "report.md")
        st.markdown(md)
else:
    st.info("Set the parameters in the sidebar and press **Run analysis**.")

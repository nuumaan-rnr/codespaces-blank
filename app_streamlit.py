"""Interactive web app for EN 15512 storage-rack analysis.

Run with:  streamlit run app_streamlit.py

Define the rack in the sidebar (geometry, sections, semi-rigid connections,
loads, imperfections, factors), run the second-order OpenSees analysis and
browse results, plots and EN 15512 checks.
"""

import json

import streamlit as st

from rack15512 import io_json
from rack15512.analysis import run_all
from rack15512.builder import RackConfig, build_rack, default_beam, default_upright
from rack15512.checks.en15512 import all_ok, governing, run_checks
from rack15512.model import CrossSection
from rack15512.report import write_report
from rack15512.viewer import (plot_deformed, plot_diagram, plot_model,
                              plot_utilization)

st.set_page_config(page_title="EN 15512 Rack Check", layout="wide")
st.title("Storage rack analysis & EN 15512 checks")
st.caption("Engine: OpenSees (second-order elastic, semi-rigid connections). "
           "Units: N, mm, MPa.")

with st.sidebar:
    st.header("Geometry")
    n_bays = st.number_input("Bays", 1, 12, 3)
    bay_width = st.number_input("Bay width [mm]", 1000.0, 4500.0, 2700.0, 50.0)
    n_levels = st.number_input("Beam levels", 1, 10, 3)
    level_h = st.number_input("Level height [mm]", 500.0, 4000.0, 2000.0, 50.0)

    st.header("Steel & sections")
    fy = st.number_input("fy [MPa]", 200.0, 700.0, 355.0, 5.0)
    with st.expander("Upright section"):
        uA = st.number_input("A [mm2]", value=780.0)
        uI = st.number_input("I [mm4]", value=1.20e6, format="%.3e")
        uW = st.number_input("Wel [mm3]", value=2.40e4, format="%.3e")
        uAe = st.number_input("A_eff [mm2]", value=660.0)
        uWe = st.number_input("W_eff [mm3]", value=2.05e4, format="%.3e")
        u_curve = st.selectbox("Buckling curve", ["a0", "a", "b", "c", "d"], 2)
    with st.expander("Pallet beam section"):
        bA = st.number_input("A [mm2] ", value=950.0)
        bI = st.number_input("I [mm4] ", value=2.10e6, format="%.3e")
        bW = st.number_input("Wel [mm3] ", value=3.80e4, format="%.3e")

    st.header("Semi-rigid connections")
    kc = st.number_input("Connector stiffness [kNm/rad]", 1.0, 1000.0, 100.0)
    mrd = st.number_input("Connector M_Rd [kNm]", 0.1, 50.0, 2.5)
    phi_l = st.number_input("Connector looseness phi_l [mrad]", 0.0, 20.0, 0.0)
    kbase = st.number_input("Floor connection stiffness [kNm/rad] (0 = pinned)",
                            0.0, 5000.0, 500.0)

    st.header("Loads")
    pallet = st.number_input("Pallet load per bay per level [kN]",
                             1.0, 100.0, 20.0)
    dead_w = st.number_input("Beam dead load [N/mm]", 0.0, 1.0, 0.05)
    place = st.number_input("Placement load [kN]", 0.0, 5.0, 0.5)

    st.header("Imperfection & factors")
    phi_s = st.number_input("Out-of-plumb phi_s (1/x)", 100.0, 1000.0, 350.0)
    gG = st.number_input("gamma_G", 1.0, 2.0, 1.3)
    gQ = st.number_input("gamma_Q", 1.0, 2.0, 1.4)
    order = st.selectbox("Analysis", ["Second order (EN 15512)", "First order"])

    go = st.button("Run analysis", type="primary", use_container_width=True)

cfg = RackConfig(
    n_bays=int(n_bays), bay_width=bay_width,
    level_heights=[level_h] * int(n_levels),
    steel_fy=fy,
    upright=CrossSection("UPRIGHT", "steel", A=uA, I=uI, Wel=uW,
                         A_eff=uAe, W_eff=uWe, buckling_curve=u_curve),
    beam=CrossSection("BEAM", "steel", A=bA, I=bI, Wel=bW),
    connector_stiffness=kc * 1e6, connector_m_rd=mrd * 1e6,
    connector_looseness=phi_l / 1000.0,
    base_stiffness=kbase * 1e6,
    pallet_load_per_level=pallet * 1e3, dead_load_beam=dead_w,
    placement_load=place * 1e3,
    gamma_G=gG, gamma_Q=gQ, phi_s=1.0 / phi_s,
)
model = build_rack(cfg)
if order.startswith("First"):
    model.analysis.order = 1

tab_model, tab_results, tab_checks, tab_report = st.tabs(
    ["Model", "Results", "EN 15512 checks", "Report"])

with tab_model:
    st.pyplot(plot_model(model))
    st.download_button("Download model JSON",
                       json.dumps(io_json.model_to_dict(model), indent=2),
                       "rack_model.json")

if go:
    with st.spinner("Running OpenSees..."):
        cases = run_all(model)
        checks = run_checks(model, cases)
    st.session_state["cases"] = cases
    st.session_state["checks"] = checks

if "cases" in st.session_state:
    cases = st.session_state["cases"]
    checks = st.session_state["checks"]

    with tab_results:
        names = [c.name for c in cases]
        sel = st.selectbox("Analysis case", names)
        case = cases[names.index(sel)]
        if not case.converged:
            st.error("Analysis did not converge - structure likely unstable "
                     "under this combination.")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Max sway [mm]", f"{case.max_sway:.2f}")
            a = case.alpha_cr_estimate
            c2.metric("alpha_cr (est.)", f"{a:.2f}" if a else "n/a")
            c3.metric("Order", "2nd" if case.order == 2 else "1st")
            st.pyplot(plot_deformed(model, case))
            kind = st.radio("Diagram", ["M", "N", "V"], horizontal=True)
            st.pyplot(plot_diagram(model, case, kind))
            st.subheader("Reactions [N, N, N*mm]")
            st.dataframe([{"node": n, "Fx": f"{r[0]:.0f}", "Fy": f"{r[1]:.0f}",
                           "Mz": f"{r[2]:.0f}"}
                          for n, r in case.reactions.items()])

    with tab_checks:
        verdict = all_ok(checks)
        gov = governing(checks)
        if verdict:
            st.success(f"ALL CHECKS PASS - governing utilization "
                       f"{gov.utilization:.3f} ({gov.check} on {gov.target})")
        else:
            st.error(f"CHECK FAILURES - governing {gov.check} on {gov.target} "
                     f"in '{gov.case}': utilization {gov.utilization:.3f}")
        st.pyplot(plot_utilization(model, checks))
        st.dataframe([{"check": c.check, "target": c.target,
                       "set": c.member_set, "case": c.case,
                       "utilization": round(c.utilization, 3),
                       "status": c.status, "detail": c.detail}
                      for c in sorted(checks, key=lambda c: -c.utilization)],
                     use_container_width=True)

    with tab_report:
        report = write_report(model, cases, checks)
        st.download_button("Download report.md", report, "report.md")
        st.markdown(report)
else:
    with tab_results:
        st.info("Set the parameters in the sidebar and press *Run analysis*.")

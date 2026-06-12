"""Interactive web app for 3D EN 15512 storage-rack analysis.

Run with:  streamlit run app_streamlit.py

Upload your section master (.xlsx workbook or CSV/JSON), pick sections by
role, define the rack in the sidebar (geometry, beam level by level, D/X
bracing, semi-rigid connections, loads, imperfections, factors), run the
second-order OpenSees analysis and browse results, plots and EN 15512
checks.
"""

import json
import tempfile

import streamlit as st

from rack15512 import io_json
from rack15512.analysis import run_all
from rack15512.builder import RackConfig, bracing_elevations, build_rack
from rack15512.checks.en15512 import all_ok, governing, run_checks
from rack15512.library import SectionLibrary
from rack15512.master_xlsx import MasterWorkbook, load_master
from rack15512.report import write_report
from rack15512.viewer import (plot_deformed, plot_diagram, plot_model,
                              plot_utilization)

st.set_page_config(page_title="EN 15512 Rack Check", layout="wide")
st.title("Storage rack analysis & EN 15512 checks (3D)")
st.caption("Engine: OpenSees (second-order elastic, semi-rigid connections). "
           "Units: N, mm, MPa. Axes: X down-aisle, Y cross-aisle, Z up.")


@st.cache_data
def load_master_cached(uploaded_bytes: bytes | None, filename: str):
    """Returns (SectionLibrary, MasterWorkbook | None)."""
    if uploaded_bytes is None:
        return SectionLibrary.bundled(), None
    lower = filename.lower()
    suffix = ".xlsx" if lower.endswith((".xlsx", ".xlsm")) else (
        ".json" if lower.endswith(".json") else ".csv")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(uploaded_bytes)
        path = f.name
    if suffix == ".xlsx":
        mw = load_master(path)
        return mw.library, mw
    return SectionLibrary.from_file(path), None


with st.sidebar:
    st.header("Section master")
    up_file = st.file_uploader("Master file (.xlsx, .csv or .json)",
                               type=["xlsx", "xlsm", "csv", "json"])
    try:
        lib, master = load_master_cached(
            up_file.getvalue() if up_file else None,
            up_file.name if up_file else "")
    except (ValueError, KeyError) as e:
        st.error(str(e))
        st.stop()
    st.caption(f"{len(lib.sections)} sections, roles: {', '.join(lib.roles())}"
               + (f" - base-stiffness tables: {len(master.base_tables)}"
                  if master else ""))

    def pick(label, role):
        names = lib.names(role) or lib.names()
        return st.selectbox(label, names)

    upright_sec = pick("Upright", "upright")
    beam_sec = pick("Pallet beam", "beam")
    brace_sec = pick("Bracing", "bracing")

    st.header("Geometry")
    module = st.radio("Module type", ["Single", "Back-to-back"],
                      horizontal=True)
    n_bays = st.number_input("Bays (down-aisle)", 1, 12, 3)
    bay_width = st.number_input("Beam span / bay width [mm]",
                                1000.0, 4500.0, 2700.0, 50.0)
    depth = st.number_input("Frame depth [mm]", 600.0, 2000.0, 1100.0, 50.0)
    b2b_gap = st.number_input("Back-to-back gap [mm]", 50.0, 600.0, 250.0,
                              10.0, disabled=module == "Single")

    st.subheader("Beam levels (each level individually)")
    n_levels = int(st.number_input("Number of beam levels", 1, 12, 3))
    beam_levels = []
    prev = 0.0
    for k in range(n_levels):
        z = st.number_input(f"Level {k + 1} elevation [mm]",
                            min_value=prev + 100.0, max_value=30000.0,
                            value=max(2000.0 * (k + 1), prev + 100.0),
                            step=50.0, key=f"lvl{k}")
        beam_levels.append(z)
        prev = z
    frame_h = st.number_input("Frame height [mm] (>= top level)",
                              min_value=beam_levels[-1],
                              value=beam_levels[-1], step=50.0)

    st.subheader("Cross-aisle bracing")
    btype = st.radio("Type", ["D (zigzag)", "X (crossed)"], horizontal=True)
    bstart = st.number_input("First horizontal above floor [mm]",
                             50.0, 1000.0, 150.0, 10.0)
    bpitch = st.number_input("Diagonal pitch [mm]", 200.0, 2000.0, 600.0, 50.0)
    n_pts = len(bracing_elevations(
        RackConfig(bracing_start=bstart, bracing_pitch=bpitch), frame_h))
    st.caption(f"-> {max(n_pts - 1, 0)} diagonal panels, top horizontal at "
               f"{bstart + max(n_pts - 1, 0) * bpitch:.0f} mm")

    st.header("Steel & connections")
    fy = st.number_input("Default fy [MPa] (sections without own fy)",
                         200.0, 700.0, 355.0, 5.0)
    kc = st.number_input("Connector stiffness [kNm/rad]", 1.0, 1000.0, 100.0)
    mrd = st.number_input("Connector M_Rd [kNm]", 0.1, 50.0, 2.5)
    phi_l = st.number_input("Connector looseness phi_l [mrad]", 0.0, 20.0, 0.0)
    if master:
        base_auto = st.checkbox("Base stiffness from master BASE_STIFFNESS "
                                "table (at estimated upright load)", True)
    else:
        base_auto = False
    kbase = st.number_input("Floor connection stiffness [kNm/rad] "
                            "(0 = pinned)", 0.0, 5000.0, 500.0,
                            disabled=base_auto)

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
    module="back-to-back" if module.startswith("Back") else "single",
    b2b_gap=b2b_gap,
    n_bays=int(n_bays), bay_width=bay_width, depth=depth,
    beam_levels=beam_levels, frame_height=frame_h,
    bracing_type="X" if btype.startswith("X") else "D",
    bracing_start=bstart, bracing_pitch=bpitch,
    library=lib, master=master,
    upright_section=upright_sec, beam_section=beam_sec,
    brace_section=brace_sec, steel_fy=fy,
    connector_stiffness=kc * 1e6, connector_m_rd=mrd * 1e6,
    connector_looseness=phi_l / 1000.0,
    base_stiffness="auto" if base_auto else kbase * 1e6,
    pallet_load_per_level=pallet * 1e3, dead_load_beam=dead_w,
    placement_load=place * 1e3,
    gamma_G=gG, gamma_Q=gQ, phi_s=1.0 / phi_s,
)
try:
    model = build_rack(cfg)
except (ValueError, KeyError) as e:
    st.error(str(e))
    st.stop()
if order.startswith("First"):
    model.analysis.order = 1

tab_model, tab_results, tab_checks, tab_report = st.tabs(
    ["Model", "Results", "EN 15512 checks", "Report"])

with tab_model:
    st.pyplot(plot_model(model))
    sec_rows = [{"name": s.name, "role": s.role,
                 "material fy [MPa]": model.materials[s.material].fy,
                 "A": s.A, "Iy": s.Iy, "Iz": s.Iz, "J": round(s.J, 1),
                 "A_eff": s.area_eff,
                 "curve y/z": f"{s.buckling_curve_y}/{s.buckling_curve_z}"}
                for s in model.sections.values()]
    st.subheader("Selected sections (from master)")
    st.dataframe(sec_rows)
    if isinstance(model.supports[0].rx, float):
        st.caption(f"Floor connection stiffness in the model: "
                   f"{model.supports[0].rx/1e6:.1f} kNm/rad"
                   + (" (interpolated from BASE_STIFFNESS)" if base_auto else ""))
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
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Sway X [mm]", f"{case.max_sway_x:.2f}")
            c2.metric("Sway Y [mm]", f"{case.max_sway_y:.2f}")
            a = case.alpha_cr_estimate
            c3.metric("alpha_cr (est.)", f"{a:.2f}" if a else "n/a")
            c4.metric("Order", "2nd" if case.order == 2 else "1st")
            st.pyplot(plot_deformed(model, case))
            kind = st.radio("Diagram", ["Mz", "My", "N", "Vy", "Vz", "T"],
                            horizontal=True)
            st.pyplot(plot_diagram(model, case, kind))
            st.subheader("Reactions [N / N*mm]")
            st.dataframe([{"node": n, "Fx": f"{r[0]:.0f}", "Fy": f"{r[1]:.0f}",
                           "Fz": f"{r[2]:.0f}", "Mx": f"{r[3]:.0f}",
                           "My": f"{r[4]:.0f}", "Mz": f"{r[5]:.0f}"}
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

"""Interactive web app for 3D EN 15512 storage-rack analysis.

Run with:  streamlit run app_streamlit.py

Upload your section master (.xlsx workbook or CSV/JSON), pick sections by
role, define the rack in the sidebar (geometry, beam level by level, D/X
bracing, semi-rigid connections, loads, imperfections, factors), run the
second-order OpenSees analysis and browse results, plots and EN 15512
checks.
"""

import json
import os
import tempfile

import streamlit as st

from rack15512 import io_json
from rack15512.analysis import run_all
from rack15512.builder import (LevelSpec, RackConfig, bracing_elevations,
                               build_rack)
from rack15512.checks.en15512 import all_ok, governing, run_checks
from rack15512.library import SectionLibrary
from rack15512.master_xlsx import MasterWorkbook, load_master
from rack15512.project import ProjectStore
from rack15512.project_run import run_configuration
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

    st.subheader("Beam levels (gap, section and load per level)")
    n_levels = int(st.number_input("Number of beam levels", 1, 20, 3))
    beam_names = lib.names("beam") or lib.names()
    level_specs = []
    elev = 0.0
    for k in range(n_levels):
        c1, c2, c3 = st.columns([1, 1.4, 1])
        gap = c1.number_input(f"L{k + 1} gap [mm]", 300.0, 4000.0, 2000.0,
                              50.0, key=f"gap{k}")
        sec = c2.selectbox(f"L{k + 1} beam", beam_names, key=f"sec{k}")
        load = c3.number_input(f"L{k + 1} load [kN]", 0.0, 100.0, 20.0,
                               1.0, key=f"load{k}")
        level_specs.append(LevelSpec(gap=gap, beam_section=sec,
                                     pallet_load=load * 1e3))
        elev += gap
    st.caption(f"Top beam level at {elev:.0f} mm")
    frame_h = st.number_input("Frame height [mm] (>= top level)",
                              min_value=elev, value=elev + 500.0, step=50.0)

    st.subheader("Cross-aisle bracing")
    btype = st.radio("Type", ["D (zigzag)", "X (crossed)"], horizontal=True)
    zone1 = st.selectbox("Different pattern below level 1",
                         ["same", "X (crossed)", "D (zigzag)"], 0,
                         help="e.g. X bracing up to the first beam level "
                              "for accidental loads; the CA buckling "
                              "length follows the actual bracing per level")
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
    st.caption("Connector stiffness / M_Rd / looseness are taken "
               "AUTOMATICALLY from the BEAM master per selected beam; the "
               "values below are fallbacks for beams without connector "
               "data in the master.")
    kc = st.number_input("Fallback connector stiffness [kNm/rad]",
                         1.0, 1000.0, 100.0)
    mrd = st.number_input("Fallback connector M_Rd [kNm]", 0.1, 50.0, 2.5)
    phi_l = st.number_input("Fallback connector looseness phi_l [mrad]",
                            0.0, 20.0, 0.0)
    if master:
        base_auto = st.checkbox("Base stiffness from master BASE_STIFFNESS "
                                "table (at estimated upright load)", True)
    else:
        base_auto = False
    kbase = st.number_input("Floor connection stiffness [kNm/rad] "
                            "(0 = pinned)", 0.0, 5000.0, 500.0,
                            disabled=base_auto)

    st.header("Bracing connection & footplate")
    brace_factor = st.number_input(
        "Bracing area factor in analysis (connection flexibility)",
        0.05, 1.0, 0.15, 0.05)
    bolt_size = st.selectbox("Connection bolt size",
                             ["M8", "M10", "M12", "M14", "M16"], index=2)
    bolt_grade = st.selectbox("Bolt grade",
                              ["4.6", "4.8", "5.6", "5.8", "8.8", "10.9"], 0)
    n_bolts = st.number_input("Bolts per brace end", 1, 4, 1)
    fck = st.number_input("Floor concrete f_ck [MPa]", 15.0, 60.0, 25.0, 5.0)
    plate_fy = st.number_input("Base plate fy [MPa]", 200.0, 460.0, 250.0, 5.0)
    with st.expander("Base plate (0 = standard footplate for the upright: "
                     "90 -> 100x145x4, 120 -> 100x176x4)"):
        pb = st.number_input("Plate width X [mm] (0 = standard)", 0.0, 500.0, 0.0)
        pd_ = st.number_input("Plate depth Y [mm] (0 = standard)", 0.0, 500.0, 0.0)
        pt = st.number_input("Plate thickness [mm] (0 = standard)", 0.0, 40.0, 0.0)

    splice_auto = frame_h > 11000.0
    with st.expander(f"Upright splice "
                     f"({'REQUIRED, H > 11 m' if splice_auto else 'optional'})",
                     expanded=splice_auto):
        sp_on = st.checkbox("Add splice + connection check", splice_auto)
        sp_z = st.number_input("Splice elevation [mm]", 500.0, 15000.0,
                               round(frame_h / 2 / 50) * 50.0, 50.0,
                               disabled=not sp_on)
        sp_bolt = st.selectbox("Splice bolt size",
                               ["M8", "M10", "M12", "M14", "M16"], 2,
                               disabled=not sp_on)
        sp_grade = st.selectbox("Splice bolt grade",
                                ["4.6", "4.8", "5.6", "5.8", "8.8", "10.9"],
                                0, disabled=not sp_on)
        c1, c2 = st.columns(2)
        sp_rows = c1.number_input("Bolt rows / side (pitch p1)", 1, 6, 2,
                                  disabled=not sp_on)
        sp_cols = c2.number_input("Bolt columns (pitch p2)", 1, 4, 1,
                                  disabled=not sp_on)
        sp_e1 = c1.number_input("e1 [mm]", 10.0, 100.0, 30.0, disabled=not sp_on)
        sp_e2 = c2.number_input("e2 [mm]", 10.0, 100.0, 20.0, disabled=not sp_on)
        sp_p1 = c1.number_input("p1 [mm]", 0.0, 200.0, 60.0, disabled=not sp_on)
        sp_p2 = c2.number_input("p2 [mm]", 0.0, 200.0, 0.0, disabled=not sp_on)
        sp_t = st.number_input("Sleeve thickness [mm] (0 = upright wall)",
                               0.0, 10.0, 0.0, disabled=not sp_on)

    st.header("Loads")
    dead_w = st.number_input("Beam dead load [N/mm]", 0.0, 1.0, 0.05)
    place = st.number_input("Placement load [kN]", 0.0, 5.0, 0.5)
    acc_x = st.number_input("Accidental load X (down-aisle) [kN]",
                            0.0, 10.0, 1.25,
                            help="EN 15512 impact on the corner upright; "
                                 "combined at gamma = 1.0 (0 disables)")
    acc_y = st.number_input("Accidental load Y (cross-aisle) [kN]",
                            0.0, 10.0, 2.5)
    acc_h = st.number_input("Accidental load height [mm]",
                            100.0, 1000.0, 400.0, 50.0)

    st.header("Imperfection & factors")
    phi_s = st.number_input("Out-of-plumb phi_s (1/x)", 100.0, 1000.0, 350.0)
    gG = st.number_input("gamma_G", 1.0, 2.0, 1.3)
    gQ = st.number_input("gamma_Q", 1.0, 2.0, 1.4)
    order = st.selectbox("Analysis", ["Second order (EN 15512)", "First order"])

    go = st.button("Run analysis", type="primary", use_container_width=True)

    st.header("Project")
    st.caption("Record this configuration under a project / system. "
               "Each system can hold many configurations.")
    store = ProjectStore("projects")
    projects = store.list_projects()
    proj_labels = ["(new project)"] + [f"{p.name} [{p.id}]" for p in projects]
    proj_sel = st.selectbox("Project", proj_labels)
    if proj_sel == "(new project)":
        new_proj_name = st.text_input("New project name", "My project")
        new_client = st.text_input("Client", "")
        new_engineer = st.text_input("Engineer", "")
    else:
        cur_proj = projects[proj_labels.index(proj_sel) - 1]
        sys_labels = ["(new system)"] + [f"{s.name} [{s.id}]"
                                         for s in cur_proj.systems]
        sys_sel = st.selectbox("System", sys_labels)
        if sys_sel == "(new system)":
            new_sys_name = st.text_input("New system name", "Aisle 1")
        config_name = st.text_input("Configuration name", "Config 1")
        config_notes = st.text_input("Notes", "")
    save_proj = st.button("Save configuration to project",
                          use_container_width=True)

cfg = RackConfig(
    module="back-to-back" if module.startswith("Back") else "single",
    b2b_gap=b2b_gap,
    n_bays=int(n_bays), bay_width=bay_width, depth=depth,
    levels=level_specs, frame_height=frame_h,
    bracing_type="X" if btype.startswith("X") else "D",
    bracing_type_zone1=(None if zone1 == "same"
                        else ("X" if zone1.startswith("X") else "D")),
    bracing_start=bstart, bracing_pitch=bpitch,
    splice_z=sp_z if sp_on else None,
    splice_above=0.0 if sp_on else 1.0e9,
    splice_bolt_d=float(sp_bolt[1:]), splice_bolt_grade=sp_grade,
    splice_rows=int(sp_rows), splice_cols=int(sp_cols),
    splice_e1=sp_e1, splice_e2=sp_e2, splice_p1=sp_p1, splice_p2=sp_p2,
    splice_t=sp_t or None,
    library=lib, master=master,
    upright_section=upright_sec,
    brace_section=brace_sec, steel_fy=fy,
    connector_stiffness=kc * 1e6, connector_m_rd=mrd * 1e6,
    connector_looseness=phi_l / 1000.0,
    base_stiffness="auto" if base_auto else kbase * 1e6,
    brace_area_factor=brace_factor,
    bolt_d=float(bolt_size[1:]), bolt_grade=bolt_grade,
    bolts_per_connection=int(n_bolts),
    concrete_fck=fck, plate_fy=plate_fy,
    plate_b=pb or None, plate_d=pd_ or None, plate_t=pt or None,
    dead_load_beam=dead_w,
    placement_load=place * 1e3,
    accidental_load_x=acc_x * 1e3, accidental_load_y=acc_y * 1e3,
    accidental_height=acc_h,
    gamma_G=gG, gamma_Q=gQ, phi_s=1.0 / phi_s,
)
try:
    model = build_rack(cfg)
except (ValueError, KeyError) as e:
    st.error(str(e))
    st.stop()
if order.startswith("First"):
    model.analysis.order = 1

if save_proj:
    # persist the uploaded master so the configuration can be re-run later
    master_path = None
    if up_file is not None:
        os.makedirs("projects/_masters", exist_ok=True)
        master_path = os.path.join("projects/_masters", up_file.name)
        with open(master_path, "wb") as f:
            f.write(up_file.getvalue())
    try:
        if proj_sel == "(new project)":
            proj = store.create_project(new_proj_name, client=new_client,
                                        engineer=new_engineer)
            sysm = store.add_system(proj.id, "System 1")
            pid, sid = proj.id, sysm.id
            cname, cnotes = "Config 1", ""
        else:
            pid = cur_proj.id
            if sys_sel == "(new system)":
                sysm = store.add_system(pid, new_sys_name)
                sid = sysm.id
            else:
                sid = cur_proj.systems[sys_labels.index(sys_sel) - 1].id
            cname, cnotes = config_name, config_notes
        conf = store.add_configuration(pid, sid, cname, cfg,
                                       master_path=master_path, notes=cnotes)
        st.success(f"Saved to project '{pid}' / system '{sid}' / "
                   f"config '{conf.id}'. Run it from the Projects tab or "
                   f"`rack15512 project run {pid} {sid} {conf.id}`.")
    except (ValueError, KeyError) as e:
        st.error(f"Could not save: {e}")

tab_model, tab_results, tab_checks, tab_report, tab_projects = st.tabs(
    ["Model", "Results", "EN 15512 checks", "Report", "Projects"])

with tab_model:
    st.pyplot(plot_model(model))
    sec_rows = [{"name": s.name, "role": s.role,
                 "material fy [MPa]": model.materials[s.material].fy,
                 "A": s.A, "Iy": s.Iy, "Iz": s.Iz, "J": round(s.J, 1),
                 "A_eff": s.area_eff,
                 "curve y/z": f"{s.buckling_curve_y}/{s.buckling_curve_z}",
                 "connector k [kNm/rad]":
                     round(s.connector_k / 1e6, 1) if s.connector_k
                     else ("fallback" if s.role == "beam" else "-"),
                 "connector M_Rd [kNm]":
                     round(s.connector_m_rd / 1e6, 2) if s.connector_m_rd
                     else ("fallback" if s.role == "beam" else "-")}
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

with tab_projects:
    st.subheader("Projects")
    st.caption("Each project holds systems; each system holds many "
               "configurations with their recorded results.")
    pstore = ProjectStore("projects")
    allprojs = pstore.list_projects()
    if not allprojs:
        st.info("No projects yet. Build a configuration in the sidebar and "
                "press *Save configuration to project*.")
    for proj in allprojs:
        meta = " · ".join(x for x in (proj.client, proj.location,
                                      proj.engineer) if x)
        with st.expander(f"{proj.name}  ({proj.id})"
                         + (f" — {meta}" if meta else "")):
            for sysm in proj.systems:
                st.markdown(f"**System: {sysm.name}**"
                            + (f" — {sysm.description}"
                               if sysm.description else ""))
                rows = []
                for conf in sysm.configurations:
                    rs = conf.run_summary or {}
                    gov = rs.get("governing") or {}
                    rows.append({
                        "configuration": conf.name,
                        "id": conf.id,
                        "verdict": rs.get("verdict", "not run"),
                        "governing": (f"{gov.get('check')} "
                                      f"{gov.get('utilization')}"
                                      if gov else "-"),
                        "members": rs.get("n_members", "-"),
                        "run at": rs.get("run_at", "-")})
                if rows:
                    st.dataframe(rows, use_container_width=True)
                names = [c.name for c in sysm.configurations]
                if names:
                    pick = st.selectbox("Run configuration", names,
                                        key=f"run_{proj.id}_{sysm.id}")
                    if st.button("Run", key=f"btn_{proj.id}_{sysm.id}"):
                        conf = sysm.configurations[names.index(pick)]
                        with st.spinner("Running OpenSees..."):
                            summary, cdir = run_configuration(
                                pstore, proj.id, sysm.id, conf.id)
                        st.success(f"{summary['verdict']} — artifacts in "
                                   f"{cdir}")
                        st.json(summary)

"""Dashboard web app for 3D EN 15512 storage-rack design.

Run with:  streamlit run app_streamlit.py

Opens on a dashboard: a left menu and the saved projects on the right.
Create a new project or open an existing one to view its model and results
(if a configuration has been run), or enter a new configuration. Section
masters are managed in their own page and held inside the system.
"""

import os
import tempfile

import streamlit as st

import pickle

from rack15512 import branding as B
from rack15512 import ui
from rack15512.analysis import run_all
from rack15512.builder import (LevelSpec, RackConfig, bracing_elevations,
                               build_rack)
from rack15512.checks.en15512 import all_ok, governing, run_checks
from rack15512.envelopes import build_envelopes
from rack15512.iviewer import figure_for_case, figure_for_envelope
from rack15512.library import SectionLibrary
from rack15512.master_store import MasterStore
from rack15512.model import CrossSection
from rack15512.project import ProjectStore, rackconfig_from_dict
from rack15512.project_run import run_configuration
from rack15512.report import write_report
from rack15512.viewer import plot_deformed, plot_frame_elevation, plot_model

st.set_page_config(page_title=f"{B.COMPANY} · {B.PRODUCT}", layout="wide",
                   initial_sidebar_state="expanded")

PSTORE = ProjectStore("projects")
MSTORE = MasterStore("masters")

ss = st.session_state
ss.setdefault("view", "dashboard")
ss.setdefault("project_id", None)
ss.setdefault("system_id", None)
ss.setdefault("config_id", None)
ss.setdefault("edit_cfg", None)        # RackConfig pre-fill when editing
ss.setdefault("dark_mode", False)

ui.apply_theme()


def goto(view, **kw):
    ss.view = view
    for k, v in kw.items():
        ss[k] = v
    st.rerun()


def _load_results(cdir):
    p = os.path.join(cdir, "results.pkl")
    if not os.path.exists(p):
        return None
    try:
        with open(p, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


@st.dialog("Analysis run summary", width="large")
def _run_summary_dialog(rs, target=None):
    v = rs.get("verdict", "?")
    gov = rs.get("governing") or {}
    st.markdown(f"### {'🟢' if v == 'PASS' else '🔴'} {v}  ·  "
                f"max member stress utilisation = {rs.get('max_stress', '-')}")
    if gov:
        st.markdown(f"Governing: **{gov.get('check')}** on "
                    f"{gov.get('target')} = **{gov.get('utilization')}** "
                    f"({gov.get('case')})")
    if target is not None:
        if st.button("📊 View results (model coloured by utilisation, "
                     "hover for forces/reactions) →", type="primary",
                     use_container_width=True):
            ss.project_id, ss.system_id, ss.config_id = target
            goto("view_config")
    st.markdown(f"**{rs.get('n_cases', 0)} analysis cases** from "
                f"{len(rs.get('combinations', []))} load combinations on "
                f"{len(rs.get('load_cases', []))} load cases.")
    st.markdown("**Load cases:** " + ", ".join(rs.get("load_cases", [])))
    st.markdown("**Load combinations**")
    st.dataframe([{"combination": c["name"], "kind": c["kind"],
                   "factors": ", ".join(f"{f:g}×{lc}"
                                        for lc, f in c["factors"].items()),
                   "imperfection": "yes" if c["imperfection"] else "no"}
                  for c in rs.get("combinations", [])],
                 use_container_width=True)
    st.markdown("**Analysis cases — convergence**")
    st.dataframe([{"case": c["name"], "kind": c["kind"],
                   "converged": "✅" if c["converged"] else "❌ NO",
                   "sway X [mm]": c["max_sway_x"],
                   "sway Y [mm]": c["max_sway_y"]}
                  for c in rs.get("cases", [])], use_container_width=True)
    not_conv = [c["name"] for c in rs.get("cases", []) if not c["converged"]]
    if not_conv:
        st.error("Did NOT converge: " + ", ".join(not_conv)
                 + " — likely sway instability at ULS.")
    else:
        st.success("All analysis cases converged.")


# ----------------------------------------------------------------- masters
def resolve_master(master_id, master_path=None):
    """Return (library, MasterWorkbook|None, master_id) for a config."""
    if master_id and MSTORE.exists(master_id):
        mw = MSTORE.load(master_id).to_workbook()
        return mw.library, mw, master_id
    if master_path and os.path.exists(master_path):
        if master_path.lower().endswith((".xlsx", ".xlsm")):
            from rack15512.master_xlsx import load_master
            mw = load_master(master_path)
            return mw.library, mw, None
        lib = SectionLibrary.from_file(master_path)
        return lib, None, None
    return SectionLibrary.bundled(), None, None


def master_selector(default_id=None):
    """Sidebar/main master picker; returns (library, workbook, master_id)."""
    stored = MSTORE.list()
    if not stored:
        st.warning("No section masters stored yet. Import one in the "
                   "**Section masters** page first (bundled demo used "
                   "meanwhile).")
        return SectionLibrary.bundled(), None, None
    labels = [f"{m.name} [{m.id}]" for m in stored]
    idx = next((i for i, m in enumerate(stored) if m.id == default_id), 0)
    sel = st.selectbox("Section master", labels, index=idx)
    sm = stored[labels.index(sel)]
    mw = sm.to_workbook()
    return mw.library, mw, sm.id


# ----------------------------------------------------------- configuration
def configuration_form(lib, master, cfg0: RackConfig | None):
    """Render the full configuration form; return a RackConfig (master not
    attached). cfg0 pre-fills the widgets when editing."""
    g = lambda f, d: getattr(cfg0, f, d) if cfg0 else d
    up_names = lib.names("upright") or lib.names()
    br_names = lib.names("bracing") or lib.names()
    beam_names = lib.names("beam") or lib.names()

    with st.container(border=True):
        ui.section("📐", "Geometry")
        c = st.columns(4)
        name = c[0].text_input("Configuration name", g("name", "Config 1"))
        module = c[1].radio("Module", ["single", "back-to-back"],
                            index=0 if g("module", "single") == "single" else 1)
        n_bays = c[2].number_input("Bays", 1, 20, int(g("n_bays", 3)))
        bay_width = c[3].number_input("Beam span [mm]", 1000.0, 4500.0,
                                      float(g("bay_width", 2700.0)), 50.0)
        c = st.columns(4)
        depth = c[0].number_input("Frame depth [mm]", 600.0, 2000.0,
                                  float(g("depth", 1000.0)), 50.0)
        b2b_gap = c[1].number_input("Back-to-back gap [mm]", 50.0, 600.0,
                                    float(g("b2b_gap", 250.0)), 10.0,
                                    disabled=module == "single")
        up_sec = c[2].selectbox("Upright", up_names,
                                index=_idx(up_names, g("upright_section", None)))
        br_sec = c[3].selectbox("Bracing", br_names,
                                index=_idx(br_names, g("brace_section", None)))

    with st.container(border=True):
        ui.section("🪜", "Beam levels  ·  gap · section · load, per level")
        levels0 = g("levels", None)
        n_levels = st.number_input("Number of beam levels", 1, 20,
                                   len(levels0) if levels0 else 3)
        levels, elev = [], 0.0
        for k in range(int(n_levels)):
            l0 = levels0[k] if levels0 and k < len(levels0) else None
            cc = st.columns([1, 1.6, 1])
            gap = cc[0].number_input(f"L{k+1} gap [mm]", 300.0, 4000.0,
                                     float(l0.gap if l0 else 1500.0), 50.0,
                                     key=f"g{k}")
            bs = cc[1].selectbox(f"L{k+1} beam", beam_names,
                                 index=_idx(beam_names,
                                            l0.beam_section if l0 else None),
                                 key=f"b{k}")
            ld = cc[2].number_input(
                f"L{k+1} load [kN]", 0.0, 100.0,
                float((l0.pallet_load if l0 else 20000.0) / 1e3), 1.0,
                key=f"l{k}")
            levels.append(LevelSpec(gap=gap, beam_section=bs,
                                    pallet_load=ld * 1e3))
            elev += gap
        frame_h = st.number_input(
            "Frame height [mm] (>= top level)", min_value=elev,
            value=float(g("frame_height", None) or elev + 500), step=50.0)

    with st.container(border=True):
        ui.section("◣", "Cross-aisle bracing")
        c = st.columns(4)
        btype = c[0].radio("Pattern", ["D", "X"],
                           index=0 if g("bracing_type", "D") == "D" else 1,
                           help="D = zigzag, X = crossed pairs")
        first_side = c[1].radio(
            "First diagonal connects to", ["outer", "inner"],
            index=0 if g("bracing_first_side", "outer") == "outer" else 1,
            help="The first diagonal above the bottom horizontal connects to "
                 "the OUTER (aisle-side) or INNER upright of each frame; both "
                 "frames of a back-to-back module are mirrored accordingly.")
        bstart = c[2].number_input("First horizontal [mm]", 50.0, 1000.0,
                                   float(g("bracing_start", 150.0)), 10.0)
        bpitch = c[3].number_input("Diagonal pitch [mm]", 200.0, 2000.0,
                                   float(g("bracing_pitch", 600.0)), 50.0)
        z1 = g("bracing_type_zone1", None)
        zone1 = st.selectbox("Different pattern below level 1",
                             ["same", "X", "D"],
                             index={None: 0, "X": 1, "D": 2}.get(z1, 0))

    with st.expander("🔩  Connections, base & checks"):
        c = st.columns(3)
        fy = c[0].number_input("Default fy [MPa]", 200.0, 700.0,
                               float(g("steel_fy", 355.0)), 5.0)
        base_auto = c[1].checkbox("Base stiffness from master table",
                                  isinstance(g("base_stiffness", "auto"), str))
        kbase = c[2].number_input("Floor stiffness [kNm/rad] (if not auto)",
                                  0.0, 5000.0,
                                  float(g("base_stiffness", 5e8) / 1e6
                                        if not isinstance(
                                            g("base_stiffness", "auto"), str)
                                        else 500.0), disabled=base_auto)
        c = st.columns(3)
        brace_factor = c[0].number_input("Bracing area factor", 0.05, 1.0,
                                         float(g("brace_area_factor", 0.15)),
                                         0.05)
        bolt = c[1].selectbox("Brace bolt", ["M8", "M10", "M12", "M14", "M16"],
                              index=_idx(["8", "10", "12", "14", "16"],
                                         str(int(g("bolt_d", 12.0)))))
        grade = c[2].selectbox("Bolt grade",
                               ["4.6", "4.8", "5.6", "5.8", "8.8", "10.9"],
                               index=_idx(["4.6", "4.8", "5.6", "5.8", "8.8",
                                           "10.9"], g("bolt_grade", "4.6")))
        c = st.columns(3)
        fck = c[0].number_input("Concrete f_ck [MPa]", 15.0, 60.0,
                                float(g("concrete_fck", 25.0)), 5.0)
        plate_fy = c[1].number_input("Plate fy [MPa]", 200.0, 460.0,
                                     float(g("plate_fy", 250.0)), 5.0)
        c[2].caption("Footplate auto: 90→100×145×4, 120→100×176×4 "
                     "(blank fields below)")
        c = st.columns(3)
        pb = c[0].number_input("Plate b [mm] (0=std)", 0.0, 500.0,
                               float(g("plate_b", None) or 0.0))
        pd_ = c[1].number_input("Plate d [mm] (0=std)", 0.0, 500.0,
                                float(g("plate_d", None) or 0.0))
        pt = c[2].number_input("Plate t [mm] (0=std)", 0.0, 40.0,
                               float(g("plate_t", None) or 0.0))

    with st.expander("⬇  Loads, imperfection & factors"):
        c = st.columns(3)
        dead = c[0].number_input("Beam dead load [N/mm]", 0.0, 1.0,
                                 float(g("dead_load_beam", 0.05)))
        place = c[1].number_input("Placement load [kN]", 0.0, 5.0,
                                  float(g("placement_load", 500.0) / 1e3))
        phi_s = c[2].number_input("Out-of-plumb (1/x)", 100.0, 1000.0, 350.0)
        c = st.columns(3)
        ax = c[0].number_input("Accidental X [kN]", 0.0, 10.0,
                               float(g("accidental_load_x", 1250.0) / 1e3))
        ay = c[1].number_input("Accidental Y [kN]", 0.0, 10.0,
                               float(g("accidental_load_y", 2500.0) / 1e3))
        ah = c[2].number_input("Accidental height [mm]", 100.0, 1000.0,
                               float(g("accidental_height", 400.0)), 50.0)
        c = st.columns(3)
        inc_place = c[0].checkbox("Include placement loads",
                                  bool(g("include_placement", True)))
        inc_acc = c[1].checkbox("Include accidental loads",
                                bool(g("include_accidental", True)))
        c = st.columns(3)
        gG = c[0].number_input("gamma_G", 1.0, 2.0, float(g("gamma_G", 1.3)))
        gQ = c[1].number_input("gamma_Q", 1.0, 2.0, float(g("gamma_Q", 1.4)))

    cfg = RackConfig(
        name=name, module=module, n_bays=int(n_bays), bay_width=bay_width,
        depth=depth, b2b_gap=b2b_gap, levels=levels, frame_height=frame_h,
        bracing_first_side=first_side, bracing_type=btype,
        bracing_start=bstart, bracing_pitch=bpitch,
        bracing_type_zone1=None if zone1 == "same" else zone1,
        upright_section=up_sec, brace_section=br_sec, steel_fy=fy,
        base_stiffness="auto" if base_auto else kbase * 1e6,
        brace_area_factor=brace_factor, bolt_d=float(bolt[1:]),
        bolt_grade=grade, concrete_fck=fck, plate_fy=plate_fy,
        plate_b=pb or None, plate_d=pd_ or None, plate_t=pt or None,
        dead_load_beam=dead, placement_load=place * 1e3,
        accidental_load_x=ax * 1e3, accidental_load_y=ay * 1e3,
        accidental_height=ah, include_placement=inc_place,
        include_accidental=inc_acc,
        gamma_G=gG, gamma_Q=gQ, phi_s=1.0 / phi_s)
    cfg.master = master
    return cfg


def _idx(options, value):
    try:
        return options.index(value) if value in options else 0
    except (ValueError, AttributeError):
        return 0


# --------------------------------------------------------------- dashboard
def render_dashboard():
    ui.hero("Storage Rack Design", "Design, verify and document selective "
            "pallet racking to EN 15512 — second-order analysis with "
            "semi-rigid connections.", eyebrow=f"{B.COMPANY} · {B.PRODUCT}")

    top = st.columns([3, 1])
    top[0].subheader("Projects")
    if top[1].button("➕ Create new project", use_container_width=True,
                     type="primary"):
        goto("new_project")

    projects = PSTORE.list_projects()
    if not projects:
        st.info("No projects yet. Click **Create new project** to start.")
        return
    for proj in projects:
        n_cfg = sum(len(s.configurations) for s in proj.systems)
        verdicts = [c.run_summary["verdict"]
                    for s in proj.systems for c in s.configurations
                    if c.run_summary]
        status = ("PASS" if verdicts and all(v == "PASS" for v in verdicts)
                  else ("FAIL" if any(v == "FAIL" for v in verdicts)
                        else "not run"))
        with st.container(border=True):
            cc = st.columns([4, 2, 2, 1.6])
            meta = " · ".join(x for x in (proj.client, proj.location,
                                          proj.engineer) if x)
            cc[0].markdown(f"#### {proj.name}\n<span class='rnr-muted'>"
                           f"{meta or 'no metadata'}</span>",
                           unsafe_allow_html=True)
            cc[1].markdown(ui.tile("Systems", len(proj.systems)),
                           unsafe_allow_html=True)
            cc[2].markdown(ui.tile("Configurations", n_cfg),
                           unsafe_allow_html=True)
            cc[3].markdown(ui.pill(status), unsafe_allow_html=True)
            if cc[3].button("Open →", key=f"open_{proj.id}",
                            use_container_width=True, type="primary"):
                goto("project", project_id=proj.id)
            if cc[3].button("🗑 Delete", key=f"delp_{proj.id}",
                            use_container_width=True):
                ss[f"confirm_delp_{proj.id}"] = True
            if ss.get(f"confirm_delp_{proj.id}"):
                st.warning(f"Permanently delete project '{proj.name}' and all "
                           f"its systems / configurations / results?")
                wc = st.columns(2)
                if wc[0].button("Yes, delete project", key=f"delpy_{proj.id}",
                                type="primary"):
                    PSTORE.delete_project(proj.id)
                    ss[f"confirm_delp_{proj.id}"] = False
                    st.rerun()
                if wc[1].button("Cancel", key=f"delpn_{proj.id}"):
                    ss[f"confirm_delp_{proj.id}"] = False
                    st.rerun()


def render_new_project():
    if st.button("← Back to dashboard"):
        goto("dashboard")
    ui.hero("Create New Project", "Set up the job details and the first "
            "system.", eyebrow="New project")
    with st.form("newproj"):
        name = st.text_input("Project name *", "")
        c = st.columns(2)
        client = c[0].text_input("Client", "")
        location = c[1].text_input("Location", "")
        engineer = c[0].text_input("Engineer", "")
        desc = st.text_area("Description", "")
        sysname = st.text_input("First system name", "Aisle 1")
        if st.form_submit_button("Create project", type="primary"):
            if not name.strip():
                st.error("Project name is required.")
            else:
                proj = PSTORE.create_project(name, client=client,
                                             location=location,
                                             engineer=engineer,
                                             description=desc)
                sysm = PSTORE.add_system(proj.id, sysname or "System 1")
                goto("project", project_id=proj.id, system_id=sysm.id)


# ----------------------------------------------------------------- project
def render_project():
    proj = PSTORE.load(ss.project_id)
    if st.button("← Back to dashboard"):
        goto("dashboard")
    meta = " · ".join(x for x in (proj.client, proj.location, proj.engineer,
                                  proj.standard) if x)
    ui.hero(proj.name, meta, eyebrow="Project")

    with st.expander("➕ Add a system"):
        sn = st.text_input("System name", key="newsysname")
        if st.button("Add system") and sn.strip():
            sysm = PSTORE.add_system(proj.id, sn)
            goto("project", project_id=proj.id, system_id=sysm.id)

    if not proj.systems:
        st.info("Add a system, then create a configuration in it.")
        return

    for sysm in proj.systems:
        sc = st.columns([6, 2])
        sc[0].subheader(f"System: {sysm.name}")
        if sc[1].button("🗑 Delete system", key=f"dsys_{sysm.id}",
                        use_container_width=True):
            ss[f"confirm_dsys_{sysm.id}"] = True
        if ss.get(f"confirm_dsys_{sysm.id}"):
            st.warning(f"Delete system '{sysm.name}' and its "
                       f"{len(sysm.configurations)} configuration(s)?")
            wc = st.columns(2)
            if wc[0].button("Yes, delete system", key=f"dsysy_{sysm.id}",
                            type="primary"):
                PSTORE.delete_system(proj.id, sysm.id)
                ss[f"confirm_dsys_{sysm.id}"] = False
                goto("project", project_id=proj.id)
            if wc[1].button("Cancel", key=f"dsysn_{sysm.id}"):
                ss[f"confirm_dsys_{sysm.id}"] = False
                st.rerun()
        if sysm.description:
            st.caption(sysm.description)
        if st.button("➕ New configuration", key=f"newcfg_{sysm.id}"):
            goto("configure", project_id=proj.id, system_id=sysm.id,
                 config_id=None, edit_cfg=None)
        if not sysm.configurations:
            st.caption("_No configurations yet._")
            continue
        for conf in sysm.configurations:
            rs = conf.run_summary or {}
            gov = rs.get("governing") or {}
            with st.container(border=True):
                cc = st.columns([3, 2, 1.6, 1.6, 1.6])
                cc[0].markdown(f"**{conf.name}**  \n`{conf.id}`"
                               + (f"  \n{conf.notes}" if conf.notes else ""))
                verdict = rs.get("verdict", "not run")
                cc[1].markdown(ui.pill(verdict), unsafe_allow_html=True)
                if gov:
                    cc[1].caption(f"gov {gov.get('check')} "
                                  f"{gov.get('utilization')}")
                if cc[2].button("Open", key=f"oc_{conf.id}",
                                use_container_width=True, type="primary"):
                    goto("view_config", project_id=proj.id,
                         system_id=sysm.id, config_id=conf.id)
                if cc[3].button("Edit", key=f"ec_{conf.id}",
                                use_container_width=True):
                    cfg0 = rackconfig_from_dict(conf.config)
                    goto("configure", project_id=proj.id, system_id=sysm.id,
                         config_id=conf.id, edit_cfg=cfg0)
                if cc[4].button("🗑 Delete", key=f"dc_{conf.id}",
                                use_container_width=True):
                    ss[f"confirm_dc_{conf.id}"] = True
                if ss.get(f"confirm_dc_{conf.id}"):
                    if cc[4].button("Confirm delete", key=f"dcy_{conf.id}",
                                    type="primary", use_container_width=True):
                        PSTORE.delete_configuration(proj.id, sysm.id, conf.id)
                        ss[f"confirm_dc_{conf.id}"] = False
                        goto("project", project_id=proj.id)
                    if cc[4].button("Cancel", key=f"dcn_{conf.id}",
                                    use_container_width=True):
                        ss[f"confirm_dc_{conf.id}"] = False
                        st.rerun()


# ------------------------------------------------------- view a saved config
def render_view_config():
    proj = PSTORE.load(ss.project_id)
    sysm = proj.system(ss.system_id)
    conf = sysm.configuration(ss.config_id)
    if st.button("← Back to project"):
        goto("project", project_id=proj.id)
    ui.hero(conf.name, f"{proj.name} · {sysm.name}", eyebrow="Results")

    lib, master, _ = resolve_master(conf.master_id, conf.master_path)
    cfg = rackconfig_from_dict(conf.config, master=master)
    try:
        model = build_rack(cfg)
    except (ValueError, KeyError) as e:
        st.error(f"Could not rebuild the model: {e}")
        return

    cdir = PSTORE.config_dir(proj.id, sysm.id, conf.id)
    t_model, t_results, t_report, t_params = st.tabs(
        ["Model", "Results", "Report", "Parameters"])

    with t_model:
        c = st.columns(2)
        c[0].pyplot(plot_model(model))
        c[1].pyplot(plot_frame_elevation(model, 0.0))
        st.caption(f"{len(model.nodes)} nodes · {len(model.members)} members "
                   f"· bracing first diagonal: {cfg.bracing_first_side}")

    with t_results:
        rs = conf.run_summary
        if not rs:
            st.info("This configuration has not been run yet.")
        else:
            gov = rs.get("governing") or {}
            c = st.columns(5)
            c[0].markdown("<div class='rnr-tile'><div class='k'>Verdict</div>"
                          f"<div style='margin-top:4px'>{ui.pill(rs['verdict'])}"
                          "</div></div>", unsafe_allow_html=True)
            c[1].markdown(ui.tile("Governing", gov.get("check", "-")),
                          unsafe_allow_html=True)
            c[2].markdown(ui.tile("Utilization", gov.get("utilization", "-")),
                          unsafe_allow_html=True)
            c[3].markdown(ui.tile("Max stress", rs.get("max_stress", "-")),
                          unsafe_allow_html=True)
            c[4].markdown(ui.tile("Cases", rs.get("n_cases", "-")),
                          unsafe_allow_html=True)
            st.write("")
            if st.button("📋 Show load cases / combinations summary"):
                _run_summary_dialog(rs)

            results = _load_results(cdir)
            if results:
                cases, checks = results["cases"], results["checks"]
                envs = build_envelopes(model, cases, checks)
                opts = ([f"Envelope: {e.name}" for e in envs]
                        + [f"Case: {c.name}" for c in cases])
                cc = st.columns([3, 2])
                sel = cc[0].selectbox("View envelope / case", opts)
                scale = cc[1].slider("Deformation scale", 0, 200, 30, 5)
                st.caption("Hover a member for its forces, a ◆ support for "
                           "its reactions.")
                if sel.startswith("Envelope:"):
                    env = envs[opts.index(sel)]
                    fig = figure_for_envelope(model, env, scale=scale)
                    st.plotly_chart(fig, use_container_width=True)
                    if env.governing:
                        st.caption(f"Governing in this envelope: "
                                   f"{env.governing.check} on "
                                   f"{env.governing.target} = "
                                   f"{env.governing.utilization:.3f}")
                else:
                    case = cases[opts.index(sel) - len(envs)]
                    st.plotly_chart(figure_for_case(model, case, checks,
                                                    scale=scale),
                                    use_container_width=True)
                    if not case.converged:
                        st.error("This case did NOT converge.")
            else:
                st.info("Re-run to enable the interactive viewer / envelopes.")
            st.markdown("**Max utilization by check**")
            st.dataframe([rs.get("max_utilization_by_check", {})],
                         use_container_width=True)
        if st.button("▶ Run / re-run analysis", type="primary"):
            with st.spinner("Running OpenSees (this can take a few minutes)…"):
                summary, _ = run_configuration(PSTORE, proj.id, sysm.id,
                                               conf.id)
            st.success(f"{summary['verdict']}")
            st.rerun()

    with t_report:
        st.markdown("#### Design Validation Report (EN 15512)")
        st.caption("Engineering calc-sheet: model summary, supports & "
                   "stiffness, load combinations, front / side / plan / 3D "
                   "views with dimensions, and every check with its EN "
                   "clause and PASS/FAIL.")
        res = _load_results(cdir)
        meta = {"project": proj.name, "system": sysm.name,
                "configuration": conf.name, "client": proj.client,
                "location": proj.location, "engineer": proj.engineer}
        if res and st.button("⚙ Generate / refresh report files",
                             use_container_width=True):
            from rack15512.report_doc import write_reports
            from rack15512.report_html import design_validation_report
            with open(os.path.join(cdir, "design_validation_report.html"),
                      "w", encoding="utf-8") as f:
                f.write(design_validation_report(model, res["cases"],
                                                 res["checks"], meta))
            try:
                write_reports(model, res["cases"], res["checks"], meta,
                              docx_path=os.path.join(
                                  cdir, "design_validation_report.docx"),
                              pdf_path=os.path.join(
                                  cdir, "design_validation_report.pdf"))
            except Exception as exc:
                st.warning(f"DOCX/PDF needs python-docx + reportlab: {exc}")
            st.rerun()

        files = [("design_validation_report.pdf", "📕 Download PDF",
                  "application/pdf"),
                 ("design_validation_report.docx",
                  "📘 Download DOCX (editable)",
                  "application/vnd.openxmlformats-officedocument."
                  "wordprocessingml.document"),
                 ("design_validation_report.html",
                  "🌐 Download HTML (print to PDF)", "text/html")]
        cols = st.columns(len(files))
        any_file = False
        for col, (fname, label, mime) in zip(cols, files):
            fp = os.path.join(cdir, fname)
            if os.path.exists(fp):
                any_file = True
                with open(fp, "rb") as f:
                    col.download_button(label, f.read(),
                                        f"{conf.id}_{fname}", mime=mime,
                                        use_container_width=True)
        if not any_file:
            if res:
                st.info("Press *Generate / refresh report files* above.")
            else:
                st.info("Run the configuration to generate the report.")
        rp = os.path.join(cdir, "report.md")
        if os.path.exists(rp):
            with st.expander("Preview check report (text)"):
                st.markdown(open(rp, encoding="utf-8").read())

    with t_params:
        st.json(conf.config)


# ----------------------------------------------------- create/edit a config
def render_configure():
    proj = PSTORE.load(ss.project_id)
    sysm = proj.system(ss.system_id)
    if st.button("← Back to project"):
        goto("project", project_id=proj.id)
    ui.hero("Configuration", f"{proj.name} · {sysm.name}",
            eyebrow="Edit configuration" if ss.config_id else "New "
            "configuration")

    cur_mid = (sysm.configuration(ss.config_id).master_id
               if ss.config_id else None)
    lib, master, master_id = master_selector(default_id=cur_mid)

    cfg = configuration_form(lib, master, ss.edit_cfg)
    notes = st.text_input("Notes", "")

    c = st.columns(3)
    if c[0].button("👁 Preview model", use_container_width=True):
        try:
            model = build_rack(cfg)
            st.session_state["_preview"] = True
            cc = st.columns(2)
            cc[0].pyplot(plot_model(model))
            cc[1].pyplot(plot_frame_elevation(model, 0.0))
            st.caption(f"{len(model.nodes)} nodes · {len(model.members)} "
                       f"members · first diagonal: {cfg.bracing_first_side}")
        except (ValueError, KeyError) as e:
            st.error(str(e))
    save_label = ("💾 Update configuration" if ss.config_id
                  else "💾 Save configuration")
    if c[1].button(save_label, use_container_width=True):
        conf = _save_config(proj.id, sysm.id, cfg, master_id, notes)
        if conf:
            ss.config_id = conf.id        # subsequent saves update this one
    if c[2].button("💾▶ Save & run", type="primary",
                   use_container_width=True):
        conf = _save_config(proj.id, sysm.id, cfg, master_id, notes,
                            silent=True)
        if conf:
            ss.config_id = conf.id
            with st.spinner("Running OpenSees (this can take a few minutes)…"):
                summary, _ = run_configuration(PSTORE, proj.id, sysm.id,
                                               conf.id)
            # popup with cases/combinations/convergence/stress + results link
            _run_summary_dialog(summary, target=(proj.id, sysm.id, conf.id))


def _save_config(pid, sid, cfg, master_id, notes, silent=False):
    try:
        cfg_save = RackConfig(**{k: v for k, v in cfg.__dict__.items()
                                 if k not in ("library", "master")})
        cfg_save.levels = cfg.levels
        if ss.config_id and PSTORE.load(pid).system(sid) \
                and PSTORE.load(pid).system(sid).configuration(ss.config_id):
            conf = PSTORE.update_configuration(
                pid, sid, ss.config_id, cfg.name, cfg_save,
                master_id=master_id, notes=notes)
            verb = "Updated"
        else:
            conf = PSTORE.add_configuration(pid, sid, cfg.name, cfg_save,
                                            master_id=master_id, notes=notes)
            verb = "Saved"
        if not silent:
            st.success(f"{verb} configuration '{conf.name}' ({conf.id}).")
        return conf
    except (ValueError, KeyError) as e:
        st.error(f"Could not save: {e}")
        return None


# ----------------------------------------------------------------- masters
def render_masters():
    ui.hero("Section Masters", "Import a master once, then edit or delete "
            "sections in place — no need to re-read the spreadsheet.",
            eyebrow="Section library")
    up = st.file_uploader("Import a master (.xlsx / .csv / .json)",
                          type=["xlsx", "xlsm", "csv", "json"])
    nm = st.text_input("Store as", up.name if up else "")
    if up and st.button("Import"):
        suffix = os.path.splitext(up.name)[1] or ".xlsx"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(up.getvalue())
        tmp.close()
        m = MSTORE.import_xlsx(tmp.name, name=nm or up.name)
        st.success(f"Imported '{m.id}' with {len(m.sections)} sections.")
        st.rerun()

    for sm in MSTORE.list():
        with st.expander(f"{sm.name}  ({sm.id}) — {len(sm.sections)} sections"):
            cc = st.columns([4, 1])
            cc[0].caption(f"roles: {', '.join(sm.roles())} · base tables: "
                          f"{len(sm.base_tables)} · updated {sm.updated}")
            if cc[1].button("🗑 Delete master", key=f"dm_{sm.id}"):
                MSTORE.delete(sm.id)
                st.rerun()
            role = st.selectbox("Role", ["upright", "beam", "bracing"],
                                key=f"r_{sm.id}")
            names = sm.names(role)
            if names:
                st.dataframe([{"name": n, "A": sm.sections[n].get("A"),
                               "Iy": sm.sections[n].get("Iy"),
                               "Iz": sm.sections[n].get("Iz"),
                               "fy": sm.fy.get(n)} for n in names],
                             use_container_width=True)
                e = st.columns([2, 1.5, 1.5, 1])
                edit = e[0].selectbox("Section", names, key=f"s_{sm.id}")
                fld = e[1].selectbox("Field", ["A", "Iy", "Iz", "J", "Wely",
                                               "Welz", "fy", "e1", "e2", "t"],
                                     key=f"f_{sm.id}")
                cur = (sm.fy.get(edit) if fld == "fy"
                       else sm.sections[edit].get(fld))
                nv = e[2].number_input("Value", value=float(cur or 0.0),
                                       key=f"v_{sm.id}")
                if e[3].button("Update", key=f"u_{sm.id}"):
                    sm.update_fields(edit, **{fld: nv})
                    MSTORE.save(sm)
                    st.rerun()
                if st.button(f"🗑 Delete section '{edit}'", key=f"ds_{sm.id}"):
                    sm.delete_section(edit)
                    MSTORE.save(sm)
                    st.rerun()


# ------------------------------------------------------------------- router
with st.sidebar:
    if os.path.exists(B.LOGO_PATH):
        st.image(B.LOGO_PATH, use_container_width=True)
    st.markdown(f"<div style='font-weight:800;font-size:1.02rem;margin-top:2px'>"
                f"{B.PRODUCT}</div>"
                f"<div class='rnr-muted' style='font-size:.8rem'>{B.TAGLINE}"
                f"</div>", unsafe_allow_html=True)
    st.divider()
    if st.button("🏠  Dashboard", use_container_width=True):
        goto("dashboard")
    if st.button("📚  Section masters", use_container_width=True):
        goto("masters")
    st.divider()
    ui.theme_toggle()
    if ss.project_id and ss.view in ("project", "configure", "view_config"):
        st.divider()
        st.caption("Current project")
        try:
            st.info(PSTORE.load(ss.project_id).name)
        except Exception:
            pass
    st.divider()
    st.caption("OpenSees 2nd-order · semi-rigid · units N, mm, MPa")
    st.caption(f"© {B.COMPANY} · {B.WEBSITE}")

_VIEWS = {
    "dashboard": render_dashboard,
    "new_project": render_new_project,
    "project": render_project,
    "configure": render_configure,
    "view_config": render_view_config,
    "masters": render_masters,
}
_VIEWS.get(ss.view, render_dashboard)()

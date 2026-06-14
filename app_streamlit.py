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
from rack15512.model import BasePlate, CrossSection
from rack15512.project import ProjectStore, rackconfig_from_dict
from rack15512.project_run import run_configuration
from rack15512.report import write_report
from rack15512.viewer import (plot_deformed, plot_frame_elevation,
                              plot_front_elevation, plot_model, plot_plan)

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
ss.setdefault("dark_mode", ui.load_dark_pref())   # persisted across sessions

ui.apply_theme()
ui.console()           # CAD-style command/log bar pinned to the page bottom


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
def _config_warnings(cfg, lib):
    """Lightweight pre-flight checks shown inline before running."""
    w = []
    names = set(lib.sections)
    if cfg.upright_section not in names:
        w.append(("warn", f"Upright '{cfg.upright_section}' is not in the "
                          "selected master — the first upright will be used."))
    if cfg.brace_section not in names:
        w.append(("warn", f"Bracing '{cfg.brace_section}' is not in the "
                          "master — the first bracing will be used."))
    levels = cfg.levels or []
    for k, l in enumerate(levels, 1):
        if l.beam_section and l.beam_section not in names:
            w.append(("warn", f"Level {k} beam '{l.beam_section}' is not in "
                              "the master — the first beam will be used."))
    top = (sum(l.gap for l in levels) if levels
           else (max(cfg.beam_levels) if cfg.beam_levels else 0))
    H = cfg.frame_height or top
    if H + 1 < top:
        w.append(("error", f"Frame height {H:.0f} mm is below the top beam "
                           f"level {top:.0f} mm."))
    if cfg.bracing_start >= H:
        w.append(("warn", "First horizontal is at/above the frame top — the "
                          "frame will have no bracing."))
    if cfg.module == "back-to-back" and cfg.b2b_gap <= 0:
        w.append(("error", "Back-to-back gap must be greater than 0."))
    if levels and all((l.pallet_load or 0) <= 0 for l in levels):
        w.append(("warn", "All pallet loads are zero — only self-weight "
                          "and dead load will be applied."))
    if 0 < cfg.accidental_height >= H and cfg.include_accidental:
        w.append(("warn", "Accidental-load height is above the frame top; "
                          "it will be ignored."))
    return w


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
        st.markdown("**Footplate anchors** — wedge anchor, EN 1992-4 "
                    "(non-seismic); defaults from code, adjust to pass.")
        c = st.columns(4)
        n_anch = c[0].number_input("Anchors / plate", 1, 6,
                                   int(g("n_anchors", 2)))
        anch_d = c[1].selectbox("Anchor", ["M8", "M10", "M12", "M16", "M20"],
                                index=_idx(["8", "10", "12", "16", "20"],
                                           str(int(g("anchor_d", 12.0)))))
        anch_grade = c[2].selectbox("Anchor grade",
                                    ["4.6", "5.6", "5.8", "8.8", "10.9"],
                                    index=_idx(["4.6", "5.6", "5.8", "8.8",
                                                "10.9"],
                                               g("anchor_grade", "5.6")))
        anch_hef = c[3].number_input("Embedment hef [mm]", 30.0, 250.0,
                                     float(g("anchor_hef", 70.0)), 5.0)
        c = st.columns(4)
        anch_s = c[0].number_input("Anchor spacing [mm] (0=auto)", 0.0, 500.0,
                                   float(g("anchor_spacing", None) or 0.0))
        anch_c = c[1].number_input("Edge distance [mm] (0=none)", 0.0, 500.0,
                                   float(g("anchor_edge", None) or 0.0))
        anch_np = c[2].number_input("Pull-out N_Rk,p [kN] (0=default)", 0.0,
                                    200.0,
                                    float((g("anchor_pullout_rk", None) or 0.0)
                                          / 1e3))
        anch_vc = c[3].number_input("Shear V_Rk,c [kN] (0=default)", 0.0, 200.0,
                                    float((g("anchor_shear_rk", None) or 0.0)
                                          / 1e3))

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

    with st.expander("🌐  Seismic (IS 1893:2016) & seismic bracing"):
        from rack15512.seismic import (STRUCTURE_TYPES, ZONE_FACTORS,
                                       design_spectrum_sa_g)
        seismic = st.checkbox("Run seismic (modal response spectrum) analysis",
                              bool(g("seismic", False)))
        ui.section("📋", "Seismic parameters (IS 1893:2016)")
        soil_labels = {"I": "I — Rock / hard", "II": "II — Medium",
                       "III": "III — Soft"}
        c = st.columns(4)
        s_zone = c[0].selectbox(
            "Seismic zone", ["II", "III", "IV", "V"],
            index=_idx(["II", "III", "IV", "V"], g("seismic_zone", "III")),
            help="Zone factor Z: II=0.10, III=0.16, IV=0.24, V=0.36 (Table 3)")
        s_soil = c[1].selectbox(
            "Soil / site type", ["I", "II", "III"],
            index=_idx(["I", "II", "III"], g("seismic_soil", "II")),
            format_func=lambda k: soil_labels[k])
        s_I = c[2].number_input(
            "Importance factor I", 1.0, 1.5,
            float(g("seismic_importance", 1.0)), 0.1,
            help="1.0 normal, 1.5 important / high-occupancy (Table 8)")
        s_kappa = c[3].number_input(
            "Imposed-load factor κ", 0.0, 1.0,
            float(g("seismic_imposed_factor", 0.5)), 0.05,
            help="Fraction of pallet load taken as seismic mass (Table 8)")
        s_damp = st.slider("Damping ratio", 0.01, 0.10,
                           float(g("seismic_damping", 0.05)), 0.01,
                           help="5% typical for bolted steel racks")
        s_struct = st.selectbox(
            "Structure type (lateral system → R)", list(STRUCTURE_TYPES),
            index=_idx(list(STRUCTURE_TYPES),
                       g("seismic_structure_type",
                         "Storage rack - cross-aisle braced")),
            help="Sets the response reduction factor R (Table 9); choose "
                 "'Custom' to type R.")
        cc = st.columns(2)
        r_from_type = STRUCTURE_TYPES.get(s_struct)
        s_R = cc[0].number_input(
            "Response reduction R", 1.0, 6.0,
            float(r_from_type if r_from_type is not None
                  else g("seismic_response_reduction", 4.0)), 0.5,
            disabled=r_from_type is not None)
        s_modes = cc[1].number_input(
            "Modes (min)", 1, 12, int(g("seismic_n_modes", 6)),
            help="Auto-increased until ≥90% mass per direction (Cl 7.7.5.2)")
        Z = ZONE_FACTORS[s_zone]
        sa_plateau = design_spectrum_sa_g(0.3, s_soil)
        ah = (Z / 2.0) * (s_I / s_R) * sa_plateau
        st.caption(
            f"**Z = {Z}**, Sa/g(plateau) = {sa_plateau:.2f}, "
            f"**Ah = (Z/2)(I/R)(Sa/g) = {ah:.4f}** (R = {s_R:g}). "
            "Combinations 1.2(DL+IL±EL), 1.5(DL±EL), 0.9DL±1.5EL (IS 800 LSD); "
            "modal RSA, SRSS, base-shear scaling, directions 100%+30%.")
        st.markdown("**Seismic bracing** (truss members)")
        c = st.columns(4)
        brace_opts = ["(frame brace)"] + list(br_names)
        sp_on = c[0].checkbox("Spine bracing (down-aisle X)",
                              bool(g("spine_bracing", False)))
        sp_sec = c[1].selectbox("Spine section", brace_opts,
                                index=_idx(brace_opts,
                                           g("spine_bracing_section", None)
                                           or "(frame brace)"))
        sp_mod = c[2].selectbox("Spine modules", ["all", "alternate",
                                                  "every_3rd"],
                                index=_idx(["all", "alternate", "every_3rd"],
                                           g("spine_bracing_modules", "all")))
        pl_on = c[3].checkbox("Plan bracing (horizontal X)",
                              bool(g("plan_bracing", False)))
        c = st.columns(4)
        pl_default = g("plan_bracing_section", "1C36x21x6x1.2")
        pl_sec = c[0].selectbox("Plan section", brace_opts,
                                index=_idx(brace_opts,
                                           pl_default if pl_default in brace_opts
                                           else "(frame brace)"))
        pl_mod = c[1].selectbox("Plan modules", ["all", "alternate",
                                                 "every_3rd"],
                                index=_idx(["all", "alternate", "every_3rd"],
                                           g("plan_bracing_modules", "all")))

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
        n_anchors=int(n_anch), anchor_d=float(anch_d[1:]),
        anchor_grade=anch_grade, anchor_hef=anch_hef,
        anchor_spacing=anch_s or None, anchor_edge=anch_c or None,
        anchor_pullout_rk=(anch_np * 1e3) or None,
        anchor_shear_rk=(anch_vc * 1e3) or None,
        dead_load_beam=dead, placement_load=place * 1e3,
        accidental_load_x=ax * 1e3, accidental_load_y=ay * 1e3,
        accidental_height=ah, include_placement=inc_place,
        include_accidental=inc_acc,
        gamma_G=gG, gamma_Q=gQ, phi_s=1.0 / phi_s,
        seismic=seismic, seismic_zone=s_zone, seismic_soil=s_soil,
        seismic_importance=s_I, seismic_response_reduction=s_R,
        seismic_structure_type=s_struct,
        seismic_damping=s_damp, seismic_imposed_factor=s_kappa,
        seismic_n_modes=int(s_modes),
        spine_bracing=sp_on,
        spine_bracing_section=None if sp_sec == "(frame brace)" else sp_sec,
        spine_bracing_modules=sp_mod,
        plan_bracing=pl_on,
        plan_bracing_section=None if pl_sec == "(frame brace)" else pl_sec,
        plan_bracing_modules=pl_mod)
    cfg.master = master
    return cfg


def _idx(options, value):
    try:
        return options.index(value) if value in options else 0
    except (ValueError, AttributeError):
        return 0


# --------------------------------------------------------------- dashboard
def render_dashboard():
    ui.topbar("Tip: run a few configurations, then use Compare to see their "
              "EN 15512 utilisations side by side.", kind="tip")
    ui.hero("Storage Rack Design", "Design, verify and document selective "
            "pallet racking to EN 15512 — second-order analysis with "
            "semi-rigid connections.", eyebrow=f"{B.COMPANY} · {B.PRODUCT}")

    projects = PSTORE.list_projects()
    # portfolio KPIs
    n_sys = sum(len(p.systems) for p in projects)
    confs = [c for p in projects for s in p.systems for c in s.configurations]
    runs = [c.run_summary["verdict"] for c in confs if c.run_summary]
    pass_rate = (f"{round(100 * sum(v == 'PASS' for v in runs) / len(runs))}%"
                 if runs else "—")
    ui.stat_strip([("Projects", len(projects)), ("Systems", n_sys),
                   ("Configurations", len(confs)), ("Pass rate", pass_rate)])

    top = st.columns([3, 1])
    top[0].subheader("Projects")
    if top[1].button("➕ Create new project", use_container_width=True,
                     type="primary"):
        goto("new_project")

    if not projects:
        ui.empty_state("📦", "No projects yet",
                       "Create your first project to start designing a rack.")
        if st.button("➕ Create your first project", type="primary"):
            goto("new_project")
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
    ui.hero(proj.name, meta, eyebrow="Project",
            crumbs=["Dashboard", proj.name])

    n_total_cfg = sum(len(s.configurations) for s in proj.systems)
    hc = st.columns([3, 1])
    with hc[0].expander("➕ Add a system"):
        sn = st.text_input("System name", key="newsysname")
        if st.button("Add system") and sn.strip():
            sysm = PSTORE.add_system(proj.id, sn)
            goto("project", project_id=proj.id, system_id=sysm.id)
    if n_total_cfg >= 2 and hc[1].button("⚖️ Compare configurations",
                                         use_container_width=True):
        goto("compare", project_id=proj.id)

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
    ui.hero(conf.name, f"{proj.name} · {sysm.name}", eyebrow="Results",
            crumbs=["Dashboard", proj.name, sysm.name, conf.name])

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

            st.write("")
            results = _load_results(cdir)
            if results:
                cases, checks = results["cases"], results["checks"]
                envs = build_envelopes(model, cases, checks)
                opts = ([f"Envelope: {e.name}" for e in envs]
                        + [f"Case: {c.name}" for c in cases])
                with st.container(border=True):
                    ui.section("🧊", "Interactive model — coloured by "
                                     "utilisation")
                    cc = st.columns([3, 2])
                    sel = cc[0].selectbox("View envelope / case", opts,
                                          label_visibility="collapsed")
                    scale = cc[1].slider("Deformation scale ×", 0, 200, 30, 5)
                    if sel.startswith("Envelope:"):
                        env = envs[opts.index(sel)]
                        st.plotly_chart(figure_for_envelope(model, env,
                                                            scale=scale),
                                        use_container_width=True)
                        if env.governing:
                            st.markdown(
                                f"<span class='rnr-muted'>Governing: "
                                f"<b>{env.governing.check}</b> on "
                                f"{env.governing.target} = "
                                f"{env.governing.utilization:.3f}</span>",
                                unsafe_allow_html=True)
                    else:
                        case = cases[opts.index(sel) - len(envs)]
                        st.plotly_chart(figure_for_case(model, case, checks,
                                                        scale=scale),
                                        use_container_width=True)
                        if not case.converged:
                            st.error("This case did NOT converge.")
                    st.caption("Hover a member for its forces, a ◆ support "
                               "for its reactions.")
            else:
                st.info("Re-run to enable the interactive viewer / envelopes.")
            with st.container(border=True):
                ui.section("📊", "Maximum utilisation by check")
                st.dataframe([rs.get("max_utilization_by_check", {})],
                             use_container_width=True)
            seis = rs.get("seismic")
            if seis:
                with st.container(border=True):
                    ui.section("🌐", "Seismic (IS 1893) summary")
                    sc = st.columns(5)
                    sc[0].markdown(ui.tile("Zone", seis.get("zone", "-")),
                                   unsafe_allow_html=True)
                    sc[1].markdown(ui.tile("T₁ [s]",
                                           seis.get("fundamental_T", "-")),
                                   unsafe_allow_html=True)
                    sc[2].markdown(ui.tile("V_b,x [kN]",
                                           seis.get("base_shear_x_kN", "-")),
                                   unsafe_allow_html=True)
                    sc[3].markdown(ui.tile("Drift util",
                                           seis.get("max_drift_util", "-")),
                                   unsafe_allow_html=True)
                    sc[4].markdown(ui.pill(seis.get("verdict", "not run")),
                                   unsafe_allow_html=True)
                    st.caption(f"Method {seis.get('method')} · seismic weight "
                               f"{seis.get('seismic_weight_kN')} kN · captured "
                               f"mass {seis.get('captured_mass_x_pct')}%")
        rc = st.columns(3)
        if rc[0].button("▶ Run / re-run analysis", type="primary",
                        use_container_width=True):
            ui.log(f"Run invoked: {proj.name} · {sysm.name} · {conf.name}")
            try:
                summary, _ = ui.run_with_status(
                    lambda progress: run_configuration(
                        PSTORE, proj.id, sysm.id, conf.id, progress=progress),
                    label="OpenSees second-order analysis")
                ui.toast_verdict(summary["verdict"])
                st.rerun()
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")
                st.exception(exc)
        if rc[1].button("🌐 Seismic design (IS 1893)",
                        use_container_width=True):
            goto("seismic_study", project_id=proj.id, system_id=sysm.id,
                 config_id=conf.id)
        if rc[2].button("🔩 Anchor & footplate designer",
                        use_container_width=True,
                        disabled=not _load_results(cdir),
                        help="Design the anchor + footplate against the "
                             "governing ULS / seismic base reactions "
                             "(after a run)."):
            goto("anchor_designer", project_id=proj.id, system_id=sysm.id,
                 config_id=conf.id)

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

        files = [("design_validation_report.pdf", "📕", "PDF",
                  "Print-ready engineering report.", "application/pdf"),
                 ("design_validation_report.docx", "📘", "DOCX",
                  "Editable Word document for review / stamping.",
                  "application/vnd.openxmlformats-officedocument."
                  "wordprocessingml.document"),
                 ("design_validation_report.html", "🌐", "HTML",
                  "Self-contained — open in any browser, print to PDF.",
                  "text/html")]
        cols = st.columns(len(files))
        any_file = False
        for col, (fname, icon, label, desc, mime) in zip(cols, files):
            fp = os.path.join(cdir, fname)
            with col:
                with st.container(border=True):
                    exists = os.path.exists(fp)
                    st.markdown(
                        f"<div style='font-size:1.6rem'>{icon}</div>"
                        f"<div style='font-weight:700;font-size:1.05rem'>"
                        f"{label}</div><div class='rnr-muted' "
                        f"style='font-size:.82rem;min-height:2.4em'>{desc}"
                        f"</div>", unsafe_allow_html=True)
                    if exists:
                        any_file = True
                        with open(fp, "rb") as f:
                            st.download_button(
                                f"Download {label}", f.read(),
                                f"{conf.id}_{fname}", mime=mime,
                                use_container_width=True, type="primary",
                                key=f"dl_{fname}")
                    else:
                        st.button(f"Download {label}", disabled=True,
                                  use_container_width=True, key=f"dlx_{fname}")
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


# --------------------------------------------------- compare configurations
def _config_facts(conf):
    """Pull comparable facts out of a stored configuration."""
    cfg = conf.config or {}
    rs = conf.run_summary or {}
    gov = rs.get("governing") or {}
    levels = cfg.get("levels") or []
    return {
        "verdict": rs.get("verdict", "not run"),
        "governing": gov.get("check", "—"),
        "gov_util": gov.get("utilization"),
        "max_stress": rs.get("max_stress"),
        "by_check": rs.get("max_utilization_by_check", {}) or {},
        "module": cfg.get("module", "single"),
        "n_bays": cfg.get("n_bays", "—"),
        "bay_width": cfg.get("bay_width", "—"),
        "depth": cfg.get("depth", "—"),
        "n_levels": len(levels),
        "frame_height": cfg.get("frame_height", "—"),
        "upright": cfg.get("upright_section", "—"),
        "brace": cfg.get("brace_section", "—"),
    }


def _fmt(x):
    return f"{x:g}" if isinstance(x, (int, float)) else str(x)


def render_compare():
    proj = PSTORE.load(ss.project_id)
    if st.button("← Back to project"):
        goto("project", project_id=proj.id)
    ui.hero("Compare Configurations", proj.name, eyebrow="Comparison",
            crumbs=["Dashboard", proj.name, "Compare"])

    # flat list of (label, system, conf) across all systems
    choices = []
    for sysm in proj.systems:
        for conf in sysm.configurations:
            choices.append((f"{sysm.name} · {conf.name}  [{conf.id}]",
                            sysm, conf))
    if len(choices) < 2:
        ui.empty_state("⚖️", "Need at least two configurations",
                       "Create and run a few configurations, then compare "
                       "their utilisations side by side.")
        return

    labels = [c[0] for c in choices]
    picked = st.multiselect("Configurations to compare", labels,
                            default=labels[:min(3, len(labels))],
                            max_selections=4)
    if len(picked) < 2:
        st.info("Pick at least two configurations.")
        return

    sel = [choices[labels.index(p)] for p in picked]

    # union of all check names, for aligned utilisation rows
    facts = [(_label, _config_facts(conf)) for _label, _sysm, conf in sel]
    all_checks = []
    for _, f in facts:
        for k in f["by_check"]:
            if k not in all_checks:
                all_checks.append(k)

    cols = st.columns(len(sel))
    for col, (_lbl, _sysm, conf) in zip(cols, sel):
        f = _config_facts(conf)
        rows = [
            ("Governing check", f["governing"], None),
            ("Governing util.",
             _fmt(f["gov_util"]) if f["gov_util"] is not None else "—",
             f["gov_util"]),
            ("Max stress util.",
             _fmt(f["max_stress"]) if f["max_stress"] is not None else "—",
             f["max_stress"]),
            ("Module", f["module"], None),
            ("Bays × span",
             f"{_fmt(f['n_bays'])} × {_fmt(f['bay_width'])} mm", None),
            ("Levels / height",
             f"{f['n_levels']} / {_fmt(f['frame_height'])} mm", None),
            ("Upright / brace", f"{f['upright']} / {f['brace']}", None),
        ]
        for chk in all_checks:
            val = f["by_check"].get(chk)
            rows.append((f"util · {chk}",
                         _fmt(val) if val is not None else "—", val))
        col.markdown(ui.compare_card(conf.name, rows, verdict=f["verdict"]),
                     unsafe_allow_html=True)

    st.caption("Utilisation bars are filled relative to 1.0; red means the "
               "ratio exceeds unity (fails that check).")


# ------------------------------------------------ seismic design + preview
def render_seismic_study():
    import dataclasses
    from rack15512.seismic import ZONE_FACTORS, design_spectrum_sa_g
    from rack15512.seismic_study import _beam_levels
    proj = PSTORE.load(ss.project_id)
    sysm = proj.system(ss.system_id)
    conf = sysm.configuration(ss.config_id)
    if st.button("← Back to results"):
        goto("view_config", project_id=proj.id, system_id=sysm.id,
             config_id=conf.id)
    ui.hero("Seismic Design (IS 1893)", f"{proj.name} · {conf.name}",
            eyebrow="Bracing + response spectrum",
            crumbs=["Dashboard", proj.name, conf.name, "Seismic"])
    st.caption("Specify the seismic lateral system, preview the model with the "
               "bracing, then run exactly that specification. Footplate / "
               "anchors are designed separately (anchor designer) after the "
               "analysis, so they don't govern the bracing here.")

    lib, master, master_id = resolve_master(conf.master_id, conf.master_path)
    cfg0 = rackconfig_from_dict(conf.config, master=master)
    blevels = _beam_levels(cfg0)
    br_opts = ["(frame brace)"] + list(lib.names("bracing") or lib.names())

    ui.section("📋", "Seismic parameters (IS 1893:2016)")
    c = st.columns(5)
    zone = c[0].selectbox("Zone", ["II", "III", "IV", "V"],
                          index=_idx(["II", "III", "IV", "V"],
                                     cfg0.seismic_zone))
    soil = c[1].selectbox("Soil", ["I", "II", "III"],
                          index=_idx(["I", "II", "III"], cfg0.seismic_soil))
    s_I = c[2].number_input("Importance I", 1.0, 1.5,
                            float(cfg0.seismic_importance), 0.1)
    s_R = c[3].number_input("Response reduction R", 1.0, 6.0,
                            float(cfg0.seismic_response_reduction), 0.5)
    s_damp = c[4].number_input("Damping ratio", 0.01, 0.10,
                               float(cfg0.seismic_damping), 0.01)
    Z = ZONE_FACTORS[zone]
    st.caption(f"Z = {Z} · damping {s_damp*100:.0f}% · "
               f"Ah(plateau) = {(Z/2)*(s_I/s_R)*2.5:.4f}")

    ui.section("◫", "Bracing specification (truss members) — runs exactly this")
    c = st.columns(3)
    da_on = c[0].checkbox("Spine X bracing (down-aisle)",
                          bool(cfg0.spine_bracing) or True)
    da_sec = c[1].selectbox("Spine section", br_opts,
                            index=_idx(br_opts, cfg0.spine_bracing_section
                                       or "(frame brace)"))
    da_mod = c[2].selectbox(
        "Spine modules (≤ alternate)", ["alternate", "every_3rd"],
        index=_idx(["alternate", "every_3rd"],
                   cfg0.spine_bracing_modules
                   if cfg0.spine_bracing_modules in ("alternate", "every_3rd")
                   else "alternate"))
    spine_where = ("centre of the back-to-back flue"
                   if cfg0.module == "back-to-back"
                   else f"{cfg0.spine_offset_single:.0f} mm behind the rack")
    st.caption(f"Spine is a full-height X tower at the {spine_where}, tied to "
               "the frame(s) by horizontal frame spacers at every level. Plan "
               "bracing is placed only in the spine modules.")
    c = st.columns(3)
    Hmax = float(cfg0.frame_height or (blevels[-1] if blevels else 3000.0))
    ca_h = c[0].number_input("CA X up to height [mm] (0 = none)", 0.0, Hmax,
                             float(cfg0.ca_x_height or 0.0), 50.0)
    pl_on = c[1].checkbox("Plan bracing (in spine modules)",
                          bool(cfg0.plan_bracing))
    pl_sec = c[2].selectbox("Plan section", br_opts,
                            index=_idx(br_opts, cfg0.plan_bracing_section
                                       or "(frame brace)"))
    pl_levels = st.multiselect(
        "Plan bracing at beam levels (≤ alternate)", blevels,
        default=(cfg0.plan_bracing_levels or blevels[::2]),
        format_func=lambda z: f"{z:.0f} mm")
    if pl_on and len(pl_levels) > len(blevels[::2]):
        st.warning("Plan bracing should not exceed alternate beam levels.")
    beam_opts = ["(frame brace)"] + list(lib.names("beam") or lib.names())
    sp_sec = st.selectbox(
        "Frame / row spacer section (beam section; simply-supported truss tie)",
        beam_opts, index=_idx(beam_opts, cfg0.spacer_section
                              or "(frame brace)"))

    cfg = dataclasses.replace(
        cfg0, seismic=True, seismic_zone=zone, seismic_soil=soil,
        seismic_importance=s_I, seismic_response_reduction=s_R,
        seismic_damping=s_damp,
        spine_bracing=da_on,
        spine_bracing_section=None if da_sec == "(frame brace)" else da_sec,
        spine_bracing_modules=da_mod, ca_x_height=(ca_h or None),
        plan_bracing=pl_on,
        plan_bracing_section=None if pl_sec == "(frame brace)" else pl_sec,
        plan_bracing_levels=(pl_levels or None), plan_bracing_modules=da_mod,
        spacer_section=None if sp_sec == "(frame brace)" else sp_sec)
    cfg.master = master

    ui.section("🧊", "Model preview (before running)")
    try:
        model = build_rack(cfg)
    except (ValueError, KeyError) as e:
        st.error(f"Could not build the model: {e}")
        return

    def _n(s):
        return sum(1 for x in model.members.values() if x.member_set == s)
    cc = st.columns(2)
    cc[0].pyplot(plot_model(model))
    cc[1].pyplot(plot_front_elevation(model))
    st.pyplot(plot_plan(model))
    st.caption(f"{len(model.nodes)} nodes · {len(model.members)} members · "
               f"spine {_n('spine bracing')} · frame spacers "
               f"{_n('frame spacer')} · plan {_n('plan bracing')} (all truss)")

    if st.button("▶ Run seismic analysis (this specification)",
                 type="primary", use_container_width=True):
        cfg_save = RackConfig(**{k: v for k, v in cfg.__dict__.items()
                                 if k not in ("library", "master")})
        cfg_save.levels = cfg.levels
        PSTORE.update_configuration(proj.id, sysm.id, conf.id, conf.name,
                                    cfg_save, master_id=master_id,
                                    notes=conf.notes or "")
        ui.log(f"Seismic run invoked (zone {zone}): {conf.name}")
        try:
            summary, _ = ui.run_with_status(
                lambda progress: run_configuration(
                    PSTORE, proj.id, sysm.id, conf.id, progress=progress),
                label="Seismic + EN 15512 analysis")
            ui.toast_verdict(summary["verdict"])
            goto("view_config", project_id=proj.id, system_id=sysm.id,
                 config_id=conf.id)
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")
            st.exception(exc)


# ------------------------------------------------ anchor & footplate designer
def render_anchor_designer():
    import math
    from rack15512.checks.en15512 import (_anchorage_checks,
                                          _base_plate_checks)
    proj = PSTORE.load(ss.project_id)
    sysm = proj.system(ss.system_id)
    conf = sysm.configuration(ss.config_id)
    if st.button("← Back to results"):
        goto("view_config", project_id=proj.id, system_id=sysm.id,
             config_id=conf.id)
    ui.hero("Anchor & Footplate Designer", f"{proj.name} · {conf.name}",
            eyebrow="EN 15512 / EN 1992-4 — post-analysis",
            crumbs=["Dashboard", proj.name, conf.name, "Anchor designer"])

    cdir = PSTORE.config_dir(proj.id, sysm.id, conf.id)
    results = _load_results(cdir)
    if not results:
        st.info("Run the analysis first — the designer uses the saved base "
                "reactions from the ULS (and seismic) cases.")
        return
    lib, master, master_id = resolve_master(conf.master_id, conf.master_path)
    cfg0 = rackconfig_from_dict(conf.config, master=master)
    try:
        model = build_rack(cfg0)
    except (ValueError, KeyError) as e:
        st.error(f"Could not rebuild the model: {e}")
        return

    uls = [c for c in results["cases"] if c.kind == "ULS"]
    seis = [c for c in results["cases"] if c.kind == "SEISMIC"]
    st.caption(f"Designing against {len(uls)} ULS case(s)"
               + (f" + {len(seis)} seismic case(s)" if seis else "")
               + ". The anchor / footplate are not part of the seismic member "
                 "run; they are designed here from the governing base reactions.")

    def _env(cases):
        comp = up = sh = mom = 0.0
        for c in cases:
            for r in c.reactions.values():
                comp = max(comp, r[2]); up = max(up, -r[2])
                sh = max(sh, math.hypot(r[0], r[1]))
                mom = max(mom, math.hypot(r[3], r[4]))
        return comp, up, sh, mom

    cols = st.columns(2)
    for col, (lbl, cs) in zip(cols, [("ULS", uls), ("Seismic", seis)]):
        if not cs:
            continue
        comp, up, sh, mom = _env(cs)
        col.markdown(f"**{lbl} base reactions (envelope)**")
        col.caption(f"max compression {comp/1e3:.1f} kN · max uplift "
                    f"{up/1e3:.1f} kN · max shear {sh/1e3:.1f} kN · max moment "
                    f"{mom/1e6:.2f} kNm")

    ui.section("🔩", "Footplate")
    c = st.columns(4)
    fck = c[0].number_input("Concrete f_ck [MPa]", 15.0, 60.0,
                            float(cfg0.concrete_fck), 5.0)
    plate_fy = c[1].number_input("Plate fy [MPa]", 200.0, 460.0,
                                 float(cfg0.plate_fy), 5.0)
    pb = c[2].number_input("Plate b [mm] (0=std)", 0.0, 500.0,
                           float(cfg0.plate_b or 0.0))
    c2 = st.columns(4)
    pd_ = c2[0].number_input("Plate d [mm] (0=std)", 0.0, 500.0,
                             float(cfg0.plate_d or 0.0))
    pt = c2[1].number_input("Plate t [mm] (0=std)", 0.0, 40.0,
                            float(cfg0.plate_t or 0.0))

    ui.section("⚓", "Wedge anchors (EN 1992-4, non-seismic defaults)")
    c = st.columns(4)
    n_anch = c[0].number_input("Anchors / plate", 1, 6, int(cfg0.n_anchors))
    a_d = c[1].selectbox("Anchor", ["M8", "M10", "M12", "M16", "M20"],
                         index=_idx(["8", "10", "12", "16", "20"],
                                    str(int(cfg0.anchor_d))))
    a_g = c[2].selectbox("Grade", ["4.6", "5.6", "5.8", "8.8", "10.9"],
                         index=_idx(["4.6", "5.6", "5.8", "8.8", "10.9"],
                                    cfg0.anchor_grade))
    a_hef = c[3].number_input("Embedment hef [mm]", 30.0, 250.0,
                              float(cfg0.anchor_hef), 5.0)
    c = st.columns(4)
    a_s = c[0].number_input("Spacing [mm] (0=auto)", 0.0, 500.0,
                            float(cfg0.anchor_spacing or 0.0))
    a_c = c[1].number_input("Edge dist. [mm] (0=none)", 0.0, 500.0,
                            float(cfg0.anchor_edge or 0.0))
    a_np = c[2].number_input("Pull-out N_Rk,p [kN] (0=default)", 0.0, 200.0,
                             float((cfg0.anchor_pullout_rk or 0.0) / 1e3))
    a_vc = c[3].number_input("Shear V_Rk,c [kN] (0=default)", 0.0, 200.0,
                             float((cfg0.anchor_shear_rk or 0.0) / 1e3))

    bp = BasePlate(
        f_ck=fck, fy_plate=plate_fy, b=pb or None, d=pd_ or None,
        t=pt or None, m_rd_n=model.base_plate.m_rd_n if model.base_plate else None,
        n_anchors=int(n_anch), anchor_d=float(a_d[1:]), anchor_grade=a_g,
        anchor_hef=a_hef, anchor_spacing=a_s or None, anchor_edge=a_c or None,
        anchor_pullout_rk=(a_np * 1e3) or None,
        anchor_shear_rk=(a_vc * 1e3) or None)
    model.base_plate = bp

    # evaluate the base-plate + anchorage checks against ULS + seismic cases
    bp_res, an_res = [], []
    for c in uls + seis:
        bp_res += _base_plate_checks(model, c)
        an_res += _anchorage_checks(model, c)
    real = [r for r in bp_res + an_res if not r.informative]
    worst_bp = max((r for r in bp_res if not r.informative),
                   key=lambda r: r.utilization, default=None)
    worst_an = max((r for r in an_res if not r.informative),
                   key=lambda r: r.utilization, default=None)

    ui.section("✅", "Verification (governing case)")
    vc = st.columns(2)
    for col, title, w in [(vc[0], "Footplate (BASEPLATE)", worst_bp),
                          (vc[1], "Anchorage (EN 1992-4)", worst_an)]:
        with col:
            if not w:
                st.info(f"{title}: not evaluated.")
                continue
            verdict = "PASS" if w.ok else "FAIL"
            st.markdown(ui.pill(verdict), unsafe_allow_html=True)
            st.markdown(f"**{title}** — util **{w.utilization:.2f}** "
                        f"(case {w.case}, {w.target})")
            st.caption(w.detail)

    ok = all(r.ok for r in real) if real else False
    if st.button("💾 Save anchor & footplate to configuration",
                 type="primary", disabled=not real):
        cfg_save = RackConfig(**{k: v for k, v in cfg0.__dict__.items()
                                 if k not in ("library", "master")})
        cfg_save.levels = cfg0.levels
        cfg_save.concrete_fck = fck
        cfg_save.plate_fy = plate_fy
        cfg_save.plate_b = pb or None
        cfg_save.plate_d = pd_ or None
        cfg_save.plate_t = pt or None
        cfg_save.n_anchors = int(n_anch)
        cfg_save.anchor_d = float(a_d[1:])
        cfg_save.anchor_grade = a_g
        cfg_save.anchor_hef = a_hef
        cfg_save.anchor_spacing = a_s or None
        cfg_save.anchor_edge = a_c or None
        cfg_save.anchor_pullout_rk = (a_np * 1e3) or None
        cfg_save.anchor_shear_rk = (a_vc * 1e3) or None
        PSTORE.update_configuration(proj.id, sysm.id, conf.id, conf.name,
                                    cfg_save, master_id=master_id,
                                    notes=conf.notes or "")
        ui.log(f"Anchor/footplate saved ({'PASS' if ok else 'FAIL'}): "
               f"{conf.name}", "ok" if ok else "error")
        st.success("Saved. Re-run the analysis to refresh the full report.")


# ----------------------------------------------------- create/edit a config
def render_configure():
    proj = PSTORE.load(ss.project_id)
    sysm = proj.system(ss.system_id)
    if st.button("← Back to project"):
        goto("project", project_id=proj.id)
    ui.hero("Configuration", f"{proj.name} · {sysm.name}",
            eyebrow="Edit configuration" if ss.config_id else "New "
            "configuration",
            crumbs=["Dashboard", proj.name, sysm.name,
                    "Edit" if ss.config_id else "New"])

    cur_mid = (sysm.configuration(ss.config_id).master_id
               if ss.config_id else None)
    lib, master, master_id = master_selector(default_id=cur_mid)

    cfg = configuration_form(lib, master, ss.edit_cfg)
    notes = st.text_input("Notes", "")

    # pre-flight validation hints
    warns = _config_warnings(cfg, lib)
    errs = [m for lvl, m in warns if lvl == "error"]
    for lvl, m in warns:
        (st.error if lvl == "error" else st.warning)(m)

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
            ui.log(f"Save & run invoked: {conf.name}")
            try:
                summary, _ = ui.run_with_status(
                    lambda progress: run_configuration(
                        PSTORE, proj.id, sysm.id, conf.id, progress=progress),
                    label="OpenSees second-order analysis")
                ui.toast_verdict(summary["verdict"])
                # popup: cases/combinations/convergence/stress + results link
                _run_summary_dialog(summary, target=(proj.id, sysm.id, conf.id))
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")
                st.exception(exc)


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
        ui.log(f"{verb} configuration '{conf.name}' ({conf.id})", "ok")
        if not silent:
            st.success(f"{verb} configuration '{conf.name}' ({conf.id}).")
        return conf
    except (ValueError, KeyError) as e:
        ui.log(f"Save failed: {e}", "error")
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

            if sm.base_tables:
                with st.expander(f"📈 Base-stiffness curves "
                                 f"({len(sm.base_tables)} uprights) — "
                                 "floor connection k_b(N) and M_Rd(N)"):
                    bu = st.selectbox("Upright", sorted(sm.base_tables),
                                      key=f"bt_{sm.id}")
                    rows = sm.base_tables[bu]   # [[N, k_b, M_Rd], ...] N·mm units
                    data = [{"N [kN]": round(r[0] / 1e3, 1),
                             "k_b [kNm/rad]": round(r[1] / 1e6, 1),
                             "M_Rd [kNm]": round(r[2] / 1e6, 2)} for r in rows]
                    st.dataframe(data, use_container_width=True)
                    try:
                        import pandas as pd
                        df = pd.DataFrame(data).set_index("N [kN]")
                        gc = st.columns(2)
                        gc[0].caption("Rotational stiffness k_b vs axial N")
                        gc[0].line_chart(df[["k_b [kNm/rad]"]])
                        gc[1].caption("Moment resistance M_Rd vs axial N")
                        gc[1].line_chart(df[["M_Rd [kNm]"]])
                    except Exception:
                        pass
                    st.caption("Used by the base partial-restraint (BASE_"
                               "RESTRAINT) check and base springs; set "
                               "base_stiffness='auto' on the configuration to "
                               "interpolate this per upright at the design N.")
            elif "upright" in sm.roles():
                st.caption("No BASE_STIFFNESS table in this master — add a "
                           "BASE_STIFFNESS sheet (per upright: N vs k_b vs "
                           "M_Rd) to use load-dependent base springs.")

            from rack15512.cf_sections import STD_1C, standard_1c_sections
            missing = [n for n in STD_1C if n not in sm.sections]
            bc = st.columns([3, 2])
            bc[0].caption(f"Standard 1C bracing family: "
                          f"{len(STD_1C) - len(missing)}/{len(STD_1C)} present")
            if missing and bc[1].button(f"➕ Add {len(missing)} 1C bracing "
                                        "sections", key=f"add1c_{sm.id}"):
                for nm, sec in standard_1c_sections().items():
                    if nm in missing:
                        sm.upsert_section(sec, fy=355.0)
                MSTORE.save(sm)
                st.success(f"Added {len(missing)} 1C bracing sections.")
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
    st.caption(f"build {B.BUILD}")

_VIEWS = {
    "dashboard": render_dashboard,
    "new_project": render_new_project,
    "project": render_project,
    "configure": render_configure,
    "view_config": render_view_config,
    "compare": render_compare,
    "seismic_study": render_seismic_study,
    "anchor_designer": render_anchor_designer,
    "masters": render_masters,
}
_VIEWS.get(ss.view, render_dashboard)()

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

from rack15512 import background_run, branding as B
from rack15512 import ui
from rack15512.analysis import run_all
from rack15512.auth import UserStore
from rack15512.builder import (LevelSpec, RackConfig, bracing_elevations,
                               build_rack)
from rack15512.checks.en15512 import all_ok, governing, run_checks
from rack15512.envelopes import build_envelopes, member_envelope_summary_md
from rack15512.iviewer import (VIEW_OPTIONS, apply_view, figure_for_case,
                               figure_for_envelope, figure_for_loads)
from rack15512.library import SectionLibrary
from rack15512.master_store import MasterStore
from rack15512.model import BasePlate, CrossSection
from rack15512.project import ProjectStore, rackconfig_from_dict
from rack15512.report import write_report
from rack15512.viewer import (plot_deformed, plot_footplate,
                              plot_frame_elevation, plot_front_elevation,
                              plot_model, plot_plan, plot_side_elevation)

st.set_page_config(page_title=f"{B.COMPANY} · {B.PRODUCT}", layout="wide",
                   initial_sidebar_state="expanded")

G_ACC = 9.81   # m/s^2 - standard gravity, kg -> N throughout the UI (matches
               # builder._G_ACC / loadcharts.G_ACC; never the 10 shortcut)

PSTORE = ProjectStore("projects")
MSTORE = MasterStore("masters")  # starts empty; masters are uploaded per company
USTORE = UserStore("users")      # login directory - admin manages this in-app
USTORE.bootstrap_admin_from_env()   # first boot only: seeds one admin (see auth.py)

ss = st.session_state
ss.setdefault("view", "dashboard")
ss.setdefault("project_id", None)
ss.setdefault("system_id", None)
ss.setdefault("config_id", None)
ss.setdefault("edit_cfg", None)        # RackConfig pre-fill when editing
ss.setdefault("dark_mode", ui.load_dark_pref())   # persisted across sessions
ss.setdefault("user", None)            # {"username","name","role"} once logged in

ui.apply_theme()

if ss.user is None:
    ui.render_login(USTORE)
    st.stop()

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


def _rstab_results_compare(model, res, cdir, conf):
    """Upload an RSTAB results workbook and compare it against this
    configuration's own analysis: every load combination, every member, and a
    governing-per-section summary."""
    st.markdown("#### RSTAB results comparison — validate the app against RSTAB")
    st.caption("Drop the RSTAB *results* export (the workbook with "
               "'COn - 4.1 Members - Internal Forces' sheets). Each RSTAB "
               "load combination COn is matched to this app's combination of "
               "the same number, then N / My / Mz are compared for every "
               "member, with a governing load-combination per cross-section.")
    up = st.file_uploader(
        "RSTAB results workbook (.xlsx)", type=["xlsx"],
        key="rstab_results_ref")
    if up is None:
        return
    if not res:
        st.info("Run the configuration first — there are no app results to "
                "compare against yet.")
        return
    ref_path = os.path.join(cdir, "_rstab_results.xlsx")
    with open(ref_path, "wb") as f:
        f.write(up.getbuffer())
    from rack15512 import rfem_compare as rc
    try:
        rfem = rc.read_rfem_results(ref_path)
    except Exception as exc:
        st.error(f"Could not read the RSTAB results workbook: {exc}")
        return
    if not rfem:
        st.error("No 'COn - 4.1 Members' result sheets were found in that "
                 "workbook — export the member internal forces per combination "
                 "from RSTAB (Tables → Results → Members).")
        return
    cases = res["cases"]
    # the RSTAB file is this app's own export, so reproduce the exact CO
    # numbering the exporter assigned (per combination x imperfection dir)
    co_for = rc.export_co_map(model)
    comps = rc.compare_results(model, cases, rfem, co_for=co_for)
    cov = rc.coverage(model, cases, rfem, co_for=co_for)
    if not comps:
        st.warning("The workbook was read but no combination numbers matched "
                   "this configuration's combinations. RSTAB combinations: "
                   f"{', '.join(cov['their_combos']) or '-'}; app "
                   f"combinations: {', '.join(cov['our_combos']) or '-'}.")
        return

    dsc = rc.discrepancies(comps)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Combinations compared", len(cov["matched_combos"]))
    agree = len(comps) - len(dsc)
    m2.metric("Agree within tolerance", f"{agree}/{len(comps)}")
    diffs = sorted(c.rel_diff for c in comps)
    med = 100.0 * diffs[len(diffs) // 2]
    m3.metric("Median difference", f"{med:.1f}%")
    m4.metric("To review", len(dsc))
    st.caption("“Within tolerance” = relative difference ≤ 15% **or** absolute "
               "difference ≤ 2.5 kN / 0.2 kNm (≈1–5% of a rack member's "
               "capacity). Large *relative* differences sit on members with "
               "tiny *absolute* forces — the sway-imperfection load-path tail: "
               "this app applies the imperfection as equivalent horizontal "
               "forces at every node, the RSTAB deck uses RSTAB's native "
               "inclination, so a small axial lands in the tie beams / "
               "orthogonal braces here where RSTAB shows ≈0. Neither governs "
               "any design.")
    if cov["only_theirs"]:
        st.caption("⚠ In RSTAB but not run here: "
                   + ", ".join(cov["only_theirs"]))
    if cov["only_ours"]:
        st.caption("⚠ Run here but absent from the RSTAB workbook: "
                   + ", ".join(cov["only_ours"]))

    govs = rc.governing_by_section(model, comps)
    st.markdown("**Governing load combination per cross-section** — the "
                "combination that sizes each section (worst by this app), with "
                "the RSTAB value at the same member and combination. `status` "
                "flags whether that governing value agrees within tolerance.")
    st.dataframe(rc.section_gov_rows(govs), width="stretch",
                 hide_index=True)

    if dsc:
        st.markdown(f"**Differences to review ({len(dsc)})** — outside the "
                    "agreement tolerance. In this model these are small "
                    "secondary forces (imperfection load-path); check none of "
                    "them govern a section above.")
        st.dataframe(rc.comparison_rows(dsc), width="stretch",
                     hide_index=True)
    else:
        st.success("Every compared value agrees within tolerance.")

    # ---- per-member N/My/Mz, filtered by member type + section --------
    st.markdown("**Per-member forces — N, My, Mz together (app vs RSTAB)**")
    triples = rc.member_triples(model, cases, rfem, co_for=co_for)
    if triples:
        sets = sorted({r["set"] for r in triples})
        secs = sorted({r["section"] for r in triples})
        fc = st.columns(3)
        set_pick = fc[0].multiselect("Member type / set", sets, default=sets,
                                     key="rstab_tri_set")
        sec_pick = fc[1].multiselect("Section", secs, default=secs,
                                     key="rstab_tri_sec")
        tcombos = sorted({r["combination"] for r in triples},
                         key=lambda s: (len(s), s))
        co_pick = fc[2].multiselect("Load combinations", tcombos,
                                    default=tcombos, key="rstab_tri_co")
        only_rev = st.checkbox("Only rows outside tolerance", value=False,
                               key="rstab_tri_rev")
        shown = [r for r in triples
                 if r["set"] in set_pick and r["section"] in sec_pick
                 and r["combination"] in co_pick
                 and (not only_rev or r["status"] == "review")]
        st.caption(f"{len(shown)} of {len(triples)} member×combination rows "
                   "— N in kN, My/Mz in kNcm; Δ% per component.")
        st.dataframe(sorted(shown, key=lambda r: -r["max Δ%"]),
                     width="stretch", hide_index=True)

    # ---- buckling + stress per SET OF MEMBERS (each upright) -----------
    st.markdown("**Buckling & stress check per upright — app vs RSTAB**")
    st.caption("For every upright set of members (continuous lines and "
               "per-level storey segments): the governing upright's EN 15512 "
               "**stress** and **buckling** utilisation, app vs RSTAB. The "
               "utilisation is **station-concurrent** (each station's "
               "simultaneous N, My, Mz — exactly like the design check), NOT "
               "an envelope of separate maxima (which would over-predict and "
               "read as a false FAIL on both sides). Both sides use the "
               "identical EN 15512 resistance, so the columns isolate the "
               "forces from the code calc. The RSTAB column needs the RSTAB "
               "member internal forces per station (the 4.1 sheets you "
               "uploaded); RSTAB's own steel-design ratio lives in its "
               "RF-/STEEL add-on.")
    checks = res.get("checks") if isinstance(res, dict) else None
    import inspect
    stale = "rfem_stations" not in inspect.signature(
        rc.set_buckling_comparison).parameters
    if stale:
        st.error("⚠ The app is running an **older cached `rfem_compare` "
                 "module** — the concurrent buckling fix (build 2026-07-12i) "
                 "isn't loaded, so this table would over-predict and show a "
                 "false FAIL. **Stop and restart** the Streamlit server "
                 "(Ctrl+C, then `streamlit run app_streamlit.py`) — a browser "
                 "rerun does not reload changed Python modules. If `rack15512` "
                 "is pip-installed, run `pip install -e .` first, then "
                 "restart.")
    else:
        rfem_stations = None
        if hasattr(rc, "read_rfem_stations"):
            try:
                rfem_stations = rc.read_rfem_stations(ref_path)
            except Exception:
                rfem_stations = None
        try:
            buck = rc.set_buckling_comparison(
                model, cases, rfem, co_for=co_for, checks=checks,
                rfem_stations=rfem_stations)
            if buck:
                n_fail = sum(1 for r in buck if r.get("ours") == "FAIL"
                             or r.get("RSTAB") == "FAIL")
                if n_fail:
                    st.warning(f"{n_fail} upright set(s) exceed utilisation "
                               "1.0 — see the FAIL rows.")
                else:
                    st.success("All uprights PASS buckling & stress on both "
                               "sides.")
                st.dataframe(buck, width="stretch", hide_index=True)
            else:
                st.info("No upright sets of members found for this "
                        "configuration.")
        except Exception as exc:
            st.warning(f"Buckling comparison unavailable: {exc}")

    # ---- load-beam deflection (SLS) app vs RSTAB ----------------------
    st.markdown("**Load-beam deflection (SLS) — app vs RSTAB**")
    rfem_defl = None
    try:
        rfem_defl = rc.read_rfem_deflections(ref_path)
    except Exception:
        rfem_defl = None
    st.caption("Two groups. **SLS**: this app's serviceability deflection and "
               "L/{:.0f} utilisation (the design check). **RSTAB**: the "
               "chord-relative deflection compared on whatever combinations "
               "RSTAB exported member deformations for — often the ULS combos "
               "('COn - 4.7 Members - Local Deformations'); `RSTAB basis` "
               "shows which, and `defl ours (cmp)` is this app on those same "
               "combos so the Δ% is like-for-like. RSTAB lists absolute local "
               "displacements, so the chord (end-node) movement is subtracted "
               "to match this app's chord-relative check. The 4.1 "
               "internal-forces export alone carries no deflections."
               .format(model.checks.beam_defl_limit_ratio))
    try:
        defl = rc.beam_deflection_comparison(model, cases, rfem_defl=rfem_defl,
                                             co_for=co_for)
        if defl:
            if not rfem_defl:
                st.info("No RSTAB deformation table found in the workbook — "
                        "showing this app's deflections. Export RSTAB's "
                        "'Members - Local Deformations' into the same workbook "
                        "to fill the RSTAB column.")
            st.dataframe(defl, width="stretch", hide_index=True)
        else:
            st.info("No SLS results to report beam deflections (run an SLS "
                    "combination).")
    except Exception as exc:
        st.warning(f"Deflection comparison unavailable: {exc}")

    with st.expander("Every member × every load combination (single quantity)"):
        rows = rc.comparison_rows(comps)
        combos = sorted({r["combination"] for r in rows},
                        key=lambda s: (len(s), s))
        pick = st.multiselect("Load combinations", combos, default=combos,
                              key="rstab_cmp_combos")
        qs = sorted({r["quantity"] for r in rows})
        qpick = st.multiselect("Quantities", qs, default=qs,
                               key="rstab_cmp_quant")
        shown = [r for r in rows if r["combination"] in pick
                 and r["quantity"] in qpick]
        st.caption(f"{len(shown)} of {len(rows)} compared values")
        st.dataframe(sorted(shown, key=lambda r: -r["rel diff %"]),
                     width="stretch", hide_index=True)

    dc = st.columns(2)
    md = rc.summarize(comps)
    dc[0].download_button("⬇ Comparison report (markdown)", md,
                          f"{conf.id}_rstab_comparison.md",
                          mime="text/markdown", width="stretch",
                          key="dl_rstab_cmp_md")
    xlsx_path = os.path.join(cdir, "rstab_comparison.xlsx")
    try:
        rc.write_comparison_workbook(model, cases, rfem, xlsx_path,
                                     co_for=co_for)
        with open(xlsx_path, "rb") as f:
            dc[1].download_button(
                "⬇ Comparison workbook (xlsx)", f.read(),
                f"{conf.id}_rstab_comparison.xlsx",
                mime="application/vnd.openxmlformats-officedocument."
                     "spreadsheetml.sheet",
                width="stretch", key="dl_rstab_cmp_xlsx")
    except Exception as exc:
        dc[1].caption(f"Workbook export unavailable: {exc}")


def _sap2000_import_panel(cdir, conf):
    """Upload SAP2000 database-tables workbook(s) — model and (optionally)
    results — read 1:1, verify, run, compare member forces, re-export."""
    st.markdown("#### SAP2000 model — import, verify 1:1, compare, re-export")
    st.caption("Drop the SAP2000 CSi database-tables Excel export(s) (File → "
               "Export → SAP2000 MS Excel Spreadsheet). A SAP export is often "
               "split across several files — upload all of them together. The "
               "model is read using SAP's OWN section properties (Frame Props "
               "01) and stiffness modifiers, auto-meshed at joints exactly as "
               "SAP does, checked 1:1, and — if an 'Element Forces - Frames' "
               "results table is present — compared member-by-member.")
    ups = st.file_uploader("SAP2000 workbook(s) (.xlsx)", type=["xlsx"],
                           accept_multiple_files=True, key="sap_model_ref")
    if not ups:
        return
    paths = []
    for i, up in enumerate(ups):
        p = os.path.join(cdir, f"_sap2000_{i}.xlsx")
        with open(p, "wb") as f:
            f.write(up.getbuffer())
        paths.append(p)
    path = paths                              # load_sap2000 accepts a list
    from rack15512.sap2000 import (load_sap2000, to_sap2000,
                                   verify_sap2000_import)
    try:
        sm = load_sap2000(path)
    except Exception as exc:
        st.error(f"Could not read the SAP2000 workbook(s): {exc}")
        return
    c = st.columns(4)
    c[0].metric("Nodes", len(sm.nodes))
    c[1].metric("Members (meshed)", len(sm.members))
    c[2].metric("Sections", len({m.section for m in sm.members.values()}))
    c[3].metric("Combinations", len(sm.combinations))

    st.markdown("**1:1 verification — imported model vs SAP2000 file**")
    try:
        checks = verify_sap2000_import(sm, path)
        st.dataframe(checks, width="stretch", hide_index=True)
        if all(ch["status"] == "ok" for ch in checks):
            st.success("Read 1:1 — geometry, SAP section properties, supports, "
                       "loads and combinations all match.")
        else:
            st.warning("Some items differ — see the `review` rows.")
    except Exception as exc:
        st.warning(f"Verification unavailable: {exc}")

    with st.expander("Section properties used (as SAP computed them)"):
        rows = []
        for name in sorted({m.section for m in sm.members.values()}):
            s = sm.sections[name]
            rows.append({"section": name, "role": s.role,
                         "material": s.material, "A [mm²]": round(s.A, 1),
                         "Iz=I33 [mm⁴]": round(s.Iz, 0),
                         "Iy=I22 [mm⁴]": round(s.Iy, 0),
                         "J [mm⁴]": round(s.J, 0)})
        st.dataframe(rows, width="stretch", hide_index=True)
        st.caption(f"Materials: E scaled per SAP frame modifiers — "
                   + ", ".join(f"{m.name} E={m.E:.0f} fy={m.fy:.0f}"
                               for m in sm.materials.values()
                               if m.name in {sm.sections[x].material
                                             for x in {mm.section for mm in
                                                       sm.members.values()}}))

    from rack15512.sap2000 import (read_sap_element_forces,
                                   read_sap_base_reactions, compare_sap_forces)
    sap_forces = {}
    try:
        sap_forces = read_sap_element_forces(path)
    except Exception:
        sap_forces = {}
    if sap_forces:
        st.info("SAP 'Element Forces - Frames' results found — output cases: "
                + ", ".join(sap_forces) + ". Run below to compare.")

    rc = st.columns(2)
    if rc[0].button("▶ Run & compare vs SAP2000 (OpenSees)", key="run_sap",
                    width="stretch"):
        from rack15512.analysis import run_all
        from rack15512.combos import assemble
        from rack15512.engine.opensees import OpenSeesEngine
        from rack15512.model import Combination
        try:
            with st.spinner("Running the imported SAP2000 model…"):
                cases = list(run_all(sm))
                # DEAD is a load case (self-weight), not a combination -
                # compare it directly when SAP exported a DEAD result
                if "DEAD" in sap_forces and "DEAD" in sm.load_cases:
                    dc = Combination("DEAD", "SLS", {"DEAD": 1.0},
                                     imperfection=False, order=1)
                    cases.append(OpenSeesEngine().run_case(
                        sm, assemble(sm, dc), name="DEAD", combo="DEAD",
                        kind="SLS", order=1))
            ok = sum(1 for cc in cases if cc.converged)
            st.success(f"Ran {ok}/{len(cases)} cases.")
            if sap_forces:
                comp = compare_sap_forces(sm, cases, sap_forces)
                if comp:
                    rev = [r for r in comp if r["status"] == "review"]
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Frames compared", len(comp))
                    m2.metric("Within tolerance", f"{len(comp)-len(rev)}"
                              f"/{len(comp)}")
                    m3.metric("To review", len(rev))
                    st.caption("Member forces per SAP frame (this app "
                               "auto-meshes each frame; both sides are "
                               "enveloped back to the SAP frame). SAP M3→our "
                               "Mz, M2→our My. Only load cases whose loads are "
                               "fully defined in the upload are comparable "
                               "(DEAD self-weight always; live/seismic need "
                               "their load definitions).")
                    st.dataframe(sorted(comp, key=lambda r: -r["max Δ%"]),
                                 width="stretch", hide_index=True)
                    only = [c for c in sap_forces
                            if c not in {r["case"] for r in comp}]
                    if only:
                        st.caption("SAP cases not reproduced here (loads not "
                                   "in the upload, or seismic/modal): "
                                   + ", ".join(only))
                else:
                    st.warning("No frames matched — check the combo/case "
                               "names line up with the SAP output cases.")
            # joint displacements (deflection / sway)
            from rack15512.sap2000 import (read_sap_joint_displacements,
                                           compare_sap_displacements)
            try:
                sap_disp = read_sap_joint_displacements(path)
            except Exception:
                sap_disp = {}
            if sap_disp:
                dcmp = compare_sap_displacements(sm, cases, sap_disp)
                if dcmp:
                    drev = [r for r in dcmp if r["status"] == "review"]
                    st.markdown("**Joint displacements — app vs SAP** "
                                "(global U1/U2/U3 [mm]; U3 = vertical "
                                "deflection, U1/U2 = sway)")
                    st.caption(f"{len(dcmp)} nodes compared, "
                               f"{len(dcmp)-len(drev)} within tolerance. "
                               "Node numbering is shared (SAP joint ids).")
                    st.dataframe(sorted(dcmp, key=lambda r: -r["max Δ%"]),
                                 width="stretch", hide_index=True)
            # base reactions
            try:
                br = read_sap_base_reactions(path)
                if "DEAD" in br:
                    ours = sum(abs(ml.qz) * sm.member_length(sm.members[
                        ml.member]) for ml in sm.load_cases["DEAD"].member_loads)
                    st.caption(f"DEAD base reaction ΣFZ: ours "
                               f"{ours/1e3:.1f} kN vs SAP "
                               f"{br['DEAD']['FZ']/1e3:.1f} kN.")
            except Exception:
                pass
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")
            st.exception(exc)
    sap_out = os.path.join(cdir, "SAP2000_reexport.xlsx")
    if rc[1].button("⬇ Re-export this SAP model (round-trip)", key="reexp_sap",
                    width="stretch"):
        to_sap2000(sm, sap_out)
        st.rerun()
    if os.path.exists(sap_out):
        with open(sap_out, "rb") as f:
            st.download_button(
                "Download SAP2000 re-export", f.read(),
                f"{conf.id}_SAP2000_reexport.xlsx",
                mime="application/vnd.openxmlformats-officedocument."
                     "spreadsheetml.sheet", key="dl_sap_reexp")


# view_config section selector (state-driven so we can jump to a tab)
_VC_TABS = ["🧱 Model", "📊 Results", "📄 Report", "⚙️ Parameters"]


def _run_or_poll(cdir, label, *, on_done=None):
    """If a background run (started via rack15512.background_run.start_run)
    is in progress for this configuration, render its live status; the run
    keeps executing in its own OS process regardless of what the user clicks
    elsewhere on the page, and this resumes watching it on the next
    rerun/page-load - a click no longer loses the run.  Returns False when
    nothing is in progress, so the caller renders its own Run button (which
    should call background_run.start_run() + st.rerun()).

    The completion popup/message is LEVEL-triggered, not edge-triggered: a
    "watching" flag is set in session_state as soon as this session observes
    the run in progress (whether it started it or just opened the page while
    someone else's run was live), and is only consumed - firing on_done /
    the cancelled-or-error message exactly once - once poll_status() shows
    done.  A naive "only react on the exact rerun that first sees done" was
    tried first and silently dropped the popup whenever that specific rerun
    got interrupted (e.g. a dropped websocket) before finishing - the run
    itself was unaffected (separate process), only the UI's one-shot
    reaction was lost.  This version re-checks on every later page visit
    too, so a missed rerun just means the popup appears on the next one
    instead of never.  Deliberately does NOT fire for a run that was already
    done before this session ever looked at it (no watch flag set), so
    opening an old, previously-run configuration doesn't surprise-popup."""
    watch_key = f"_run_watch_{cdir}"
    status = background_run.poll_status(cdir)
    if status is None:
        return False
    if not status.get("done", True):
        ss[watch_key] = True
        ui.run_in_background(cdir, label=label)     # aborts via st.rerun()
        status = background_run.poll_status(cdir) or status  # only if done
    if ss.pop(watch_key, False) and status.get("done", True):
        if status.get("cancelled"):
            st.warning("⛔ Analysis cancelled.")
        elif status.get("error"):
            if status.get("error_type") == "UnstableModelError":
                st.error("🛑 Model not stable — run stopped. "
                        f"{status.get('error')}")
            else:
                st.error(f"Analysis failed: {status.get('error')}")
        elif on_done:
            on_done(status.get("summary"))
    return False


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
        bc = st.columns(2)
        if bc[0].button("📊 Check Results →", type="primary", width="stretch"):
            ss.project_id, ss.system_id, ss.config_id = target
            ss["vc_jump"] = _VC_TABS[1]           # Results (applied pre-widget)
            goto("view_config")
        if bc[1].button("↩ Back to parameters", width="stretch"):
            ss.project_id, ss.system_id, ss.config_id = target
            ss["vc_jump"] = _VC_TABS[3]           # Parameters
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
                 width="stretch")
    st.markdown("**Analysis cases — convergence**")
    st.dataframe([{"case": c["name"], "kind": c["kind"],
                   "converged": "✅" if c["converged"] else "❌ NO",
                   "sway X [mm]": c["max_sway_x"],
                   "sway Y [mm]": c["max_sway_y"]}
                  for c in rs.get("cases", [])], width="stretch")
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
    stored.sort(key=lambda m: ((m.company or "~").lower(), m.name.lower()))
    labels = [f"{(m.company or '(no company)')} · {m.name} [{m.id}]"
              for m in stored]
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

    def gn(field, default, lo, hi):
        """g() for number inputs: a stale/edited value outside [lo, hi] falls
        back to the default (so e.g. a corrupt accidental_height of 0.05 shows
        the 400 default, not the 100 minimum), and never crashes the form."""
        try:
            v = float(g(field, default))
        except (TypeError, ValueError):
            v = float(default)
        if v < lo or v > hi:
            v = float(default)
        return min(max(v, lo), hi)

    up_names = lib.names("upright") or lib.names()
    br_names = lib.names("bracing") or lib.names()
    beam_names = lib.names("beam") or lib.names()
    other_names = lib.names("others")          # rails / connectors / shuttle
    # sections selectable for rails, arms and other drive-in members: the
    # 'others' products first, then the beams
    rail_names = list(other_names) + list(beam_names)

    # apply a section picked in the upright suggester on the PREVIOUS run, before
    # the Upright selectbox (key 'cfg_upright') is instantiated below
    _pending_up = st.session_state.pop("_pending_upright", None)
    if _pending_up is not None and _pending_up in up_names:
        st.session_state["cfg_upright"] = _pending_up

    _FAM = ["Selective pallet racking",
            "Drive-in / Drive-through / Radio shuttle",
            "Structural mezzanine"]
    _st0 = g("system_type", "selective")
    di_fam = st.radio(
        "Rack family", _FAM,
        index=2 if _st0 == "mezzanine" else (0 if _st0 == "selective" else 1),
        horizontal=True)
    is_di = di_fam.startswith("Drive")
    is_mz = di_fam.startswith("Structural")
    di_kw: dict = {}
    mz_kw: dict = {}

    if is_mz:
        from rack15512.mezzanine import FLOOR_TYPES
        with st.container(border=True):
            ui.section("🏢", "Structural mezzanine — grid, floors & framing")
            st.caption("Column grid with primary → secondary → (optional) "
                       "joist framing and a flooring deck. The generic rack "
                       "sections further down (bays, levels, frame bracing, "
                       "pallet loads) are **ignored** for a mezzanine — only "
                       "materials, load factors, imperfections and analysis "
                       "settings apply.")
            c = st.columns(4)
            mzbx = c[0].number_input("Bays X", 1, 20,
                                     int(gn("mz_bays_x", 3, 1, 20)))
            mzlx = c[1].number_input("Bay size X [mm]", 1000.0, 12000.0,
                                     gn("mz_bay_x", 5000.0, 1000.0, 12000.0),
                                     50.0)
            mzby = c[2].number_input("Bays Y", 1, 20,
                                     int(gn("mz_bays_y", 2, 1, 20)))
            mzly = c[3].number_input("Bay size Y [mm]", 1000.0, 12000.0,
                                     gn("mz_bay_y", 4000.0, 1000.0, 12000.0),
                                     50.0)
            c = st.columns(4)
            mznf = c[0].number_input("Floors", 1, 6,
                                     int(gn("mz_n_floors", 1, 1, 6)))
            mzfh = c[1].number_input("Storey height [mm]", 1500.0, 8000.0,
                                     gn("mz_floor_height", 3000.0, 1500.0,
                                        8000.0), 50.0)
            _dirs = ["X", "Y"]
            mzdir = c[2].selectbox("Primary beams run along", _dirs,
                                   index=_idx(_dirs, g("mz_primary_dir",
                                                       "X")))
            mzsp = c[3].number_input("Secondary spacing [mm]", 300.0, 3000.0,
                                     gn("mz_secondary_spacing", 1250.0,
                                        300.0, 3000.0), 25.0)
            col_names = list(up_names) + [n for n in beam_names
                                          if n not in up_names]
            c = st.columns(4)
            mzcol = c[0].selectbox("Column section", col_names,
                                   index=_idx(col_names,
                                              g("mz_column_section",
                                                col_names[0])))
            mzpb = c[1].selectbox("Primary beam", beam_names,
                                  index=_idx(beam_names,
                                             g("mz_primary_section",
                                               beam_names[0])))
            mzsb = c[2].selectbox("Secondary beam", beam_names,
                                  index=_idx(beam_names,
                                             g("mz_secondary_section",
                                               beam_names[0])))
            _jopts = ["(none)"] + list(beam_names)
            mzjo = c[3].selectbox(
                "Joist beam (optional)", _jopts,
                index=_idx(_jopts, g("mz_joist_section", None) or "(none)"),
                help="A third pin-ended layer between the secondaries; the "
                     "flooring then rests on the joists.")
            st.caption("**Or type section codes** (override the dropdowns): "
                       "`SHS100x100x4` / `RHS120x60x3` columns · "
                       "`1C200x60x20x2.5` (h×b×lip×t, optional `r4` corner "
                       "radius) · `2C…` two channels **back-to-back, "
                       "stitch-bolted every 500 mm** (bolt row at 50 mm "
                       "pitch, count per beam height; open torsion — enter a "
                       "welded box in the master for closed J), `2C…B` boxed "
                       "· `2x2C…` four channels. Master-library names always "
                       "win over codes.")
            c = st.columns(4)
            mzcol_c = c[0].text_input("Column code", g("mz_column_section", "")
                                      if str(g("mz_column_section", "")
                                             ).upper().startswith(("SHS",
                                                                   "RHS"))
                                      else "", key="mz_col_code")
            mzpb_c = c[1].text_input("Primary code", "", key="mz_pb_code")
            mzsb_c = c[2].text_input("Secondary code", "", key="mz_sb_code")
            mzjo_c = c[3].text_input("Joist code", "", key="mz_jo_code")
            c = st.columns(4)
            mzjsp = c[0].number_input("Joist spacing [mm]", 200.0, 2000.0,
                                      gn("mz_joist_spacing", 600.0, 200.0,
                                         2000.0), 25.0)
            mzpan = c[3].text_input(
                "Floor panel 1C code (optional)",
                g("mz_panel_section", "") or "", key="mz_panel_code",
                help="1C panels laid FLAT (minor-axis bending): their "
                     "self-weight (A·γ / web width) is added to the floor "
                     "dead load and a representative panel strip is modelled "
                     "and checked per floor.")
            _fts = list(FLOOR_TYPES)
            mzft = c[1].selectbox("Flooring type", _fts,
                                  index=_idx(_fts, g("mz_floor_type",
                                                     _fts[0])),
                                  help="Sets the deck dead weight per m².")
            mzfd = c[2].number_input("Extra dead [kN/m²]", 0.0, 10.0,
                                     gn("mz_floor_dead_extra", 0.0, 0.0,
                                        10.0), 0.05,
                                     help="Services, screed, finishes …")
            mzll = c[3].number_input("Live load [kN/m²]", 0.5, 20.0,
                                     gn("mz_live_load", 5.0, 0.5, 20.0),
                                     0.25)
            c = st.columns(4)
            _conns = ["moment", "pinned", "semi"]
            mzconn = c[0].selectbox(
                "Primary-to-column connection", _conns,
                index=_idx(_conns, g("mz_primary_conn", "moment")),
                help="With bracing OFF the frame must be a moment frame — "
                     "pinned/semi is then overridden to moment.")
            mzk = c[1].number_input(
                "Semi-rigid k [kNm/rad]", 0.0, 1.0e6,
                gn("mz_conn_k", 0.0, 0.0, 1.0e9) / 1.0e6, 10.0,
                help="Only used when the connection is 'semi'.") * 1.0e6
            mzbase = c[2].checkbox("Fixed column bases",
                                   value=bool(g("mz_base_fixed", False)))
            mzbrace = c[3].checkbox("Vertical bracing",
                                    value=bool(g("mz_bracing", True)))
            c = st.columns(4)
            mzbrsec = c[0].selectbox("Brace section", br_names,
                                     index=_idx(br_names,
                                                g("mz_brace_section",
                                                  br_names[0])))
            mzbrn = c[1].number_input("Braced bays per corner", 1, 5,
                                      int(gn("mz_braced_bays", 1, 1, 5)))
            mz_kw = dict(
                mz_bays_x=int(mzbx), mz_bay_x=mzlx, mz_bays_y=int(mzby),
                mz_bay_y=mzly, mz_n_floors=int(mznf), mz_floor_height=mzfh,
                mz_primary_dir=mzdir, mz_secondary_spacing=mzsp,
                mz_column_section=mzcol_c.strip() or mzcol,
                mz_primary_section=mzpb_c.strip() or mzpb,
                mz_secondary_section=mzsb_c.strip() or mzsb,
                mz_joist_section=(mzjo_c.strip() or
                                  (None if mzjo == "(none)" else mzjo)),
                mz_joist_spacing=mzjsp, mz_floor_type=mzft,
                mz_floor_dead_extra=mzfd, mz_live_load=mzll,
                mz_panel_section=mzpan.strip() or None,
                mz_primary_conn=mzconn,
                mz_conn_k=mzk if mzk > 0 else None,
                mz_base_fixed=bool(mzbase), mz_bracing=bool(mzbrace),
                mz_brace_section=mzbrsec, mz_braced_bays=int(mzbrn))

    with st.container(border=True):
        ui.section("📐", "Geometry")
        c = st.columns(4)
        name = c[0].text_input("Configuration name", g("name", "Config 1"))

        def _sec_label(nm):
            """'CODE — description' for a section dropdown (falls back to dims)."""
            try:
                sec = lib.get(nm)
                desc = (getattr(sec, "description", "") or "").strip()
                if not desc and getattr(sec, "depth_h", None):
                    desc = (f"{sec.depth_h:g}x{getattr(sec,'width_b',0):g}"
                            f"x{getattr(sec,'t',0):g}")
                return f"{nm} — {desc}" if desc else str(nm)
            except Exception:
                return str(nm)

        up_sec = c[1].selectbox(
            "Upright", up_names, key="cfg_upright",
            index=_idx(up_names, g("upright_section", "UP0010")),
            format_func=_sec_label,
            help="Shows the section code and its description (size / lip).")
        # default bracing: the saved value when editing, else the last-used
        # bracing (remembered across new configs in this session), else fallback
        _brace_default = (g("brace_section", None)
                          or st.session_state.get("_last_brace")
                          or "C 36X21X1.2")
        br_sec = c[2].selectbox(
            "Bracing", br_names, index=_idx(br_names, _brace_default))
        st.session_state["_last_brace"] = br_sec     # remember for next new cfg
        if is_di:
            # drive-in plan geometry (lanes / depth) is set in the Multi-deep
            # section below; these selective-rack fields are not used.
            module = g("module", "single")
            n_bays = int(gn("n_bays", 1, 1, 20))
            bay_width = gn("bay_width", 2700.0, 1000.0, 4500.0)
            depth = gn("depth", 1000.0, 600.0, 2000.0)
            b2b_gap = gn("b2b_gap", 250.0, 50.0, 600.0)
            spacer_section = None          # drive-in has no row spacers
            stiffener_section, reinforce_height, stiffener_offset = None, 0.0, 30.0
            stiffener_type, stiffener_shear_k = 1, None
            stiffener_bolt_d, stiffener_bolt_grade = 8.0, "8.8"
            stiffener_bolt_pitch = 600.0
            stiffener_modelling = "monolithic"
        else:
            module = c[3].radio(
                "Module", ["single", "back-to-back"],
                index=0 if g("module", "back-to-back") == "single" else 1)
            c = st.columns(4)
            n_bays = c[0].number_input("Bays", 1, 20,
                                       int(gn("n_bays", 5, 1, 20)))
            bay_width = c[1].number_input("Beam span [mm]", 1000.0, 4500.0,
                                          gn("bay_width", 2700.0, 1000.0, 4500.0),
                                          50.0)
            depth = c[2].number_input("Frame depth [mm]", 600.0, 2000.0,
                                      gn("depth", 1000.0, 600.0, 2000.0), 50.0)
            b2b_gap = c[3].number_input("Back-to-back gap [mm]", 50.0, 600.0,
                                        gn("b2b_gap", 250.0, 50.0, 600.0), 10.0,
                                        disabled=module == "single")
            # back-to-back row-spacer (tie) section — any bracing OR beam section
            _spacer_opts = (["(frame brace)"]
                            + list(br_names) + list(beam_names))
            _spacer_opts = list(dict.fromkeys(_spacer_opts))   # dedupe, keep order
            spacer_sec = st.selectbox(
                "Row-spacer / tie section (back-to-back)", _spacer_opts,
                index=_idx(_spacer_opts, g("spacer_section", None)
                           or "(frame brace)"),
                disabled=module == "single",
                help="Section for the row-spacer ties between the two back-to-"
                     "back racks (a simply-supported truss tie). Any bracing or "
                     "beam section; default = the frame brace section.")
        spacer_section = (None if (module == "single"
                                   or spacer_sec == "(frame brace)")
                          else spacer_sec)
        # upright stiffener: bolted parallel reinforcement over a lower zone.
        # offer the uprights plus the "other" category (every section that is
        # not an upright, beam or bracing - rails / connectors / shuttle / RHS)
        _stiff_excl = set(up_names) | set(beam_names) | set(br_names)
        _stiff_other = [n for n in lib.names() if n not in _stiff_excl]
        _stiff_opts = list(dict.fromkeys(["(none)"] + list(up_names)
                                         + _stiff_other))
        _stiff_cur = g("stiffener_section", None) or "(none)"
        stiff_sel = st.selectbox(
            "Upright stiffener section (lower-zone reinforcement)", _stiff_opts,
            index=_idx(_stiff_opts, _stiff_cur),
            help="A bolted parallel member added alongside each upright segment "
                 "up to the reinforce height; shares the upright end nodes "
                 "(stiffnesses add). Uprights and other (non-beam/bracing) "
                 "sections are selectable. '(none)' disables.")
        reinforce_height = st.number_input(
            "Reinforce height [mm] (stiffener up to this elevation)",
            0.0, 30000.0, float(g("reinforce_height", 0.0)), 50.0,
            disabled=(stiff_sel == "(none)"))
        _sc = st.columns(3)
        stiffener_offset = _sc[0].number_input(
            "Stiffener offset [mm]", 0.0, 200.0,
            float(g("stiffener_offset", 30.0)), 5.0,
            disabled=(stiff_sel == "(none)"),
            help="Fallback upright↔stiffener centroid gap (cross-aisle); captures "
                 "the CG shift. Used only when the selected stiffener has no "
                 "mount_offset in the master (the master value takes precedence).")
        stiffener_type = _sc[1].selectbox(
            "Stiffener type", [1, 2],
            index=0 if int(g("stiffener_type", 1)) == 1 else 1,
            disabled=(stiff_sel == "(none)"),
            help="1 = C closing the open face (inside, closed-section torsion "
                 "credit); 2 = C on the outer face.")
        _pitch_opts = [300.0, 600.0]
        _cur_p = float(g("stiffener_bolt_pitch", 600.0))
        stiffener_bolt_pitch = _sc[2].selectbox(
            "M8 8.8 bolt interval [mm]", _pitch_opts,
            index=_idx(_pitch_opts, _cur_p) if _cur_p in _pitch_opts else 1,
            disabled=(stiff_sel == "(none)"),
            help="Pitch of the M8 8.8 bolts tying the stiffener to the upright; "
                 "the interface stiffness (and the non-50% axial split) is "
                 "auto-derived (EN 1993-1-8). Closer bolts = more composite.")
        _mods = ["monolithic", "separate"]
        stiffener_modelling = st.selectbox(
            "Stiffener modelling", _mods,
            index=_idx(_mods, g("stiffener_modelling", "monolithic")),
            disabled=(stiff_sel == "(none)"),
            help="monolithic (default, the industry assumption): the "
                 "reinforced upright segments carry the composite equivalent "
                 "section (A summed, cross-aisle Iy by parallel axis, "
                 "closed-torsion credit for type 1) on one member line. "
                 "separate: the stiffener is its own offset member tied by "
                 "bolt-shear links (partial composite — conservative).")
        stiffener_bolt_d, stiffener_bolt_grade = 8.0, "8.8"   # always M8 8.8
        stiffener_shear_k = None       # auto-derive from the bolt + pitch
        stiffener_section = None if stiff_sel == "(none)" else stiff_sel

    if is_di:
        with st.container(border=True):
            ui.section("🏗", "Multi-deep geometry (drive-in / shuttle)")
            _VARS = ["drive_in", "drive_through", "shuttle_lifo", "shuttle_fifo"]
            c = st.columns(4)
            di_variant = c[0].selectbox(
                "Variant", _VARS, index=_idx(_VARS, g("di_variant", "drive_in")))
            n_lanes = c[1].number_input("Lanes", 1, 20,
                                        int(gn("n_lanes", 3, 1, 20)))
            lane_width = c[2].number_input("Lane width [mm]", 800.0, 2000.0,
                                           gn("lane_width", 1350.0, 800.0, 2000.0),
                                           10.0)
            n_deep = c[3].number_input("Pallets deep", 1, 30,
                                       int(gn("n_deep", 6, 1, 30)))
            c = st.columns(4)
            pallet_depth = c[0].number_input("Pallet depth [mm]", 600.0, 1600.0,
                                             gn("pallet_depth", 1200.0, 600.0,
                                                1600.0), 10.0)
            deep_clear = c[1].number_input("Deep clearance [mm]", 0.0, 200.0,
                                           gn("deep_clearance", 50.0, 0.0, 200.0),
                                           5.0)
            wt_pallet = c[2].number_input(
                "Weight / pallet [kN]", 1.0, 30.0,
                gn("weight_per_pallet", 10000.0, 1000.0, 30000.0) / 1e3, 0.5)
            spine_pos = c[3].selectbox(
                "Spine", ["auto", "rear", "centre", "none"],
                index=_idx(["auto", "rear", "centre", "none"],
                           g("spine_position", "auto")))
            c = st.columns(4)
            frame_depth = c[0].number_input(
                "Frame depth (leg spacing) [mm]", 300.0, 2000.0,
                gn("frame_depth", 1100.0, 300.0, 2000.0), 50.0,
                help="Depth (Y) of one 2-leg upright frame.")
            n_frames = c[1].number_input(
                "Number of frames", 1, 30, int(gn("n_frames", 2, 1, 30)),
                help="2-leg depth frames distributed over the lane depth; the "
                     "gap between them is auto-computed. Independent of the "
                     "pallets-deep count.")
            arm_len = c[2].number_input(
                "Rail arm offset [mm]", 0.0, 600.0,
                gn("arm_length", 200.0, 0.0, 600.0), 10.0,
                help="Cantilever-arm offset of the rail into the lane.")
            rail_sec = c[3].selectbox(
                "Rail section", ["Drivein Rail (default)"] + list(rail_names),
                index=_idx(["Drivein Rail (default)"] + list(rail_names),
                            g("rail_section", None)),
                help="Default = the RSTAB drive-in rail profile (with shear "
                     "areas / It); pick an 'others' or beam section to override.")
            ca = st.columns(2)
            arm_sec = ca[0].selectbox(
                "Cantilever arm / connector section",
                ["Arm (default)"] + list(rail_names),
                index=_idx(["Arm (default)"] + list(rail_names),
                            g("arm_section", None)),
                help="Default = the RSTAB cantilever arm; pick an 'others' "
                     "(e.g. CONN_*) or beam section to override.")
            plan_every = ca[1].checkbox("Plan bracing every level (shuttle)",
                                        bool(g("plan_every_level", False)))
            st.caption("Forklift impact (1.25 kN down-aisle / 2.5 kN cross-aisle "
                       "at ~400 mm), placement, pattern loads and per-direction "
                       "imperfections are set in the “Loads, imperfection & "
                       "factors” expander; seismic in the “Seismic” expander.")
            lane_deep = pallet_depth * n_deep + (n_deep + 1) * deep_clear
            n_fr = int(n_frames)
            _gap = ((lane_deep - n_fr * frame_depth) / (n_fr - 1)
                    if n_fr >= 2 else 0.0)
            _rail_udl = ((n_deep * wt_pallet / 2.0) / (lane_deep / 1000.0)
                         if lane_deep > 0 else 0.0)
            if n_fr >= 2 and _gap < 0:
                st.warning(f"{n_fr} frames of {frame_depth:.0f} mm exceed the "
                           f"lane depth {lane_deep:.0f} mm — reduce the frame "
                           f"count or the frame depth.")
            st.caption(f"Lane deep = {lane_deep:.0f} mm (pallet "
                       f"{pallet_depth:.0f}×{n_deep} + {n_deep + 1}×"
                       f"{deep_clear:.0f} clearance) · {n_fr} frames + "
                       f"{max(n_fr - 1, 0)} gaps of {_gap:.0f} mm · "
                       f"load/lane = {n_deep * wt_pallet:.1f} kN · "
                       f"rail UDL ≈ {_rail_udl:.2f} kN/m.")
            end3 = st.checkbox(
                "3-upright end frame (only when the deep length can't be met "
                "with the frame + gaps)", bool(g("end_frame_3upright", False)),
                help="Optional optimisation: an extra reinforcing upright at the "
                     "end frame to make up a leftover gap in the deep length.")
            boxed = st.checkbox(
                "Boxed / built-up end columns (EN 1993-1-1 §6.4)",
                bool(g("built_up_end_columns", False)),
                help="Treat the two end frames as battened/laced two-chord "
                     "columns and verify them with the BUILT_UP check instead "
                     "of the single-section stress/buckling checks.")
            if boxed:
                bc = st.columns(3)
                bu_arr = bc[0].selectbox(
                    "Built-up arrangement", ["battened", "laced"],
                    index=_idx(["battened", "laced"],
                               g("built_up_arrangement", "battened")))
                bu_h0 = bc[1].number_input(
                    "Chord spacing h0 [mm]", 40.0, 600.0,
                    gn("built_up_h0", 120.0, 40.0, 600.0), 10.0)
                bu_panel = bc[2].number_input(
                    "Batten / lacing panel [mm]", 100.0, 2000.0,
                    gn("built_up_panel", 600.0, 100.0, 2000.0), 50.0)
            else:
                bu_arr, bu_h0, bu_panel = "battened", 120.0, 600.0
            di_kw = dict(
                di_variant=di_variant, n_lanes=int(n_lanes), lane_width=lane_width,
                n_deep=int(n_deep), pallet_depth=pallet_depth,
                deep_clearance=deep_clear, frame_depth=frame_depth,
                n_frames=int(n_frames),
                arm_length=arm_len, weight_per_pallet=wt_pallet * 1e3,
                spine_position=spine_pos, end_frame_3upright=bool(end3),
                built_up_end_columns=bool(boxed), built_up_arrangement=bu_arr,
                built_up_h0=bu_h0, built_up_panel=bu_panel,
                rail_section=(None if rail_sec.startswith("Drivein Rail")
                              else rail_sec),
                arm_section=(None if arm_sec.startswith("Arm (default)")
                             else arm_sec),
                plan_every_level=bool(plan_every))

            # ---- top plan bracing + spine sections (drive-in) ----------------
            from rack15512.cf_sections import STD_1C
            _libbr = [n for n in br_names if n not in STD_1C]
            brace_opts = ["(frame brace)"] + STD_1C + _libbr
            st.markdown("**Top plan bracing & rear spine** — the spine is placed "
                        "automatically per the variant; both are selectable by "
                        "module pattern or specific bays (lane indices).")
            _mods = ["all", "alternate", "every_3rd"]

            def _bays(txt):
                return [int(s) for s in txt.replace(" ", "").split(",")
                        if s.lstrip("-").isdigit()] or None

            bc = st.columns(4)
            sp_sec = bc[0].selectbox(
                "Spine section", brace_opts,
                index=_idx(brace_opts,
                           g("spine_bracing_section", None) or "(frame brace)"))
            sp_mod = bc[1].selectbox(
                "Spine modules", _mods,
                index=_idx(_mods, g("spine_bracing_modules", "alternate")),
                help="Rear-spine bays. 'alternate' matches the RSTAB model.")
            pl_default = g("plan_bracing_section", "1C36x21x6x1.2")
            pl_sec = bc[2].selectbox(
                "Plan section", brace_opts,
                index=_idx(brace_opts,
                           pl_default if pl_default in brace_opts
                           else "(frame brace)"))
            pl_mod = bc[3].selectbox(
                "Plan modules", _mods,
                index=_idx(_mods, g("plan_bracing_modules", "all")))
            bc2 = st.columns([1, 2, 2])
            pl_type = bc2[0].selectbox(
                "Plan bracing type", ["D", "X"],
                index=_idx(["D", "X"], g("plan_bracing_type", "D")),
                help="D = single diagonal per cell; X = crossed.")
            sp_specific = bc2[1].text_input(
                "Specific spine bays (e.g. 0,2 — overrides modules)",
                value=",".join(str(i) for i in (g("spine_bracing_module_list",
                                                  None) or [])))
            pl_specific = bc2[2].text_input(
                "Specific plan bays (e.g. 0,2 — overrides modules)",
                value=",".join(str(i) for i in (g("plan_bracing_module_list",
                                                  None) or [])))
            sp_list, pl_list = _bays(sp_specific), _bays(pl_specific)
            sp_on = False
            pl_on = True

            # ---- top & back beams (connector stiffness auto from the section) -
            st.markdown("**Top & back beams** — the top (frame-top) and back "
                        "(rear, per-level) beams are independent; each beam "
                        "connector stiffness is taken automatically from the "
                        "selected section's test data (master).")
            tb = st.columns(3)
            _beamopt = ["(default)"] + list(beam_names)
            top_sec = tb[0].selectbox(
                "Top beam section", _beamopt,
                index=_idx(_beamopt, g("portal_section", None) or "(default)"))
            _backopt = ["(= top beam)"] + list(beam_names)
            back_sec = tb[1].selectbox(
                "Back beam section", _backopt,
                index=_idx(_backopt, g("back_beam_section", None) or "(= top beam)"))
            arm_kc = tb[2].number_input(
                "Cantilever (arm→upright) connector [kNm/rad]", 0.0, 5000.0,
                gn("arm_connector_stiffness", 1.0e6, 0.0, 5.0e9) / 1e6, 0.5,
                help="Arm-to-upright bracket rotational stiffness. RSTAB "
                     "Konsole hinge = 1.0 kNm/rad (100 kN·cm/rad).")

            def _conn_label(secname):
                # resolve the connector stiffness the builder will use for a beam
                # section: the section's test value, else the generic default
                if secname and secname in lib.sections:
                    k = lib.get(secname).connector_k
                    if k:
                        return f"{k / 1e6:.0f} kNm/rad (from section)"
                return "default 100 kNm/rad (no test data in master)"

            _back_name = top_sec if back_sec == "(= top beam)" else back_sec
            st.caption(
                f"Auto beam connector — top: {_conn_label(top_sec)}; "
                f"back: {_conn_label(_back_name)}.")
            di_kw.update(
                portal_section=None if top_sec == "(default)" else top_sec,
                back_beam_section=None if back_sec == "(= top beam)" else back_sec,
                top_connector_stiffness=None, back_connector_stiffness=None,
                arm_connector_stiffness=arm_kc * 1e6)

    with st.container(border=True):
        levels0 = g("levels", None)
        _beam0 = beam_names[0] if beam_names else None
        if is_di:
            # drive-in: vertical spacing is pallet-driven. Each bay (rail) level
            # gap defaults to pallet height + clearance (200 mm for the beam);
            # the top beam / plan-bracing level sits a user-set gap above the
            # last bay level (so the top is not mis-placed). The per-level beam
            # section / load are not used (load = pallets-deep x weight/pallet).
            ui.section("🪜", "Storage levels — bay (rail) levels & top beam")
            pc = st.columns(2)
            pallet_h = pc[0].number_input(
                "Pallet height [mm]", 300.0, 3000.0,
                gn("pallet_height", 1200.0, 300.0, 3000.0), 50.0)
            lvl_clear = pc[1].number_input(
                "Level clearance per beam [mm]", 50.0, 600.0,
                gn("level_clearance", 200.0, 50.0, 600.0), 10.0,
                help="Added to the pallet height for each bay-level gap "
                     "(pallet height + clearance).")
            dflt_gap = pallet_h + lvl_clear
            n_levels = st.number_input("Number of bay (rail) levels", 1, 20,
                                       len(levels0) if levels0 else 3)
            levels, elev = [], 0.0
            for k in range(int(n_levels)):
                l0 = levels0[k] if levels0 and k < len(levels0) else None
                gap = st.number_input(
                    f"L{k+1} bay gap [mm] (pallet + clearance)", 300.0, 4000.0,
                    float(l0.gap if l0 else dflt_gap), 50.0, key=f"g{k}")
                bs = (l0.beam_section if l0 and l0.beam_section else _beam0)
                ld = float(l0.pallet_load if l0 else 20000.0)
                levels.append(LevelSpec(gap=gap, beam_section=bs, pallet_load=ld))
                elev += gap
            top_gap = st.number_input(
                "Top beam gap above last bay level [mm]", 100.0, 3000.0,
                gn("top_beam_gap", dflt_gap, 100.0, 3000.0), 50.0,
                help="The final top beam / plan-bracing / top-tie level sits "
                     "this gap above the last bay level.")
            frame_h = elev + top_gap
            st.caption(f"Last bay level = {elev:.0f} mm · **top beam level "
                       f"(frame height) = {frame_h:.0f} mm** "
                       f"= {elev:.0f} + {top_gap:.0f} (top gap).")
            di_kw.update(pallet_height=pallet_h, level_clearance=lvl_clear,
                         top_beam_gap=top_gap)
        else:
            ui.section("🪜", "Beam levels  ·  gap · section · load, per level")
            from rack15512 import presize
            BEAM_SF = 1.2

            def _beam_fy_of(name):
                if master is not None:
                    try:
                        return master.fy.get(name) or 355.0
                    except Exception:
                        return 355.0
                return 355.0

            n_levels = st.number_input("Number of beam levels", 1, 20,
                                       len(levels0) if levels0 else 3)
            levels, elev = [], 0.0
            for k in range(int(n_levels)):
                l0 = levels0[k] if levels0 and k < len(levels0) else None
                cc = st.columns([1, 1, 1.6])
                gap = cc[0].number_input(f"L{k+1} gap [mm]", 300.0, 4000.0,
                                         float(l0.gap if l0 else 1500.0), 50.0,
                                         key=f"g{k}")
                # load is read BEFORE the beam widget below is created, so the
                # auto-suggested section can be written into its session_state
                # key this same run (no rerun needed, unlike the deferred-
                # apply trick the upright suggester uses further down) - and
                # shown first (left of the beam column) since it drives it.
                ld_kg = cc[1].number_input(
                    f"L{k+1} load [kg]", 0.0, 10000.0,
                    float((l0.pallet_load if l0 else 20000.0) / G_ACC), 50.0,
                    key=f"l{k}",
                    help=f"Converted to N via × g ({G_ACC:g} m/s²) for the "
                         f"analysis, not the ×10 shortcut.")
                cc[1].caption(f"= {ld_kg * G_ACC / 1e3:.2f} kN")

                # auto-suggest the beam section (closed-form simply-supported
                # UDL bending check, safety factor 1.2) whenever the bay span
                # or this level's load actually changes during editing.
                # Seeded from the saved value so opening an existing config
                # doesn't silently override a deliberate prior beam choice -
                # a manual override survives unrelated reruns (e.g. touching
                # the gap field) since the basis only changes with span/load.
                basis_key = f"_beam_auto_basis_{k}"
                basis_now = (bay_width, ld_kg)
                if basis_key not in ss:
                    ss[basis_key] = ((bay_width, float(l0.pallet_load) / G_ACC)
                                     if l0 else None)
                if ss[basis_key] != basis_now and beam_names:
                    sugg = presize.suggest_beams(
                        lib, _beam_fy_of, span=bay_width,
                        load_per_bay=ld_kg * G_ACC, safety_factor=BEAM_SF)
                    rec = next((r["name"] for r in sugg if r["recommended"]),
                              None)
                    if rec:
                        ss[f"b{k}"] = rec
                    ss[basis_key] = basis_now

                bs = cc[2].selectbox(f"L{k+1} beam", beam_names,
                                     index=_idx(beam_names,
                                                l0.beam_section if l0 else None),
                                     key=f"b{k}")
                try:
                    u = presize.beam_bending_utilisation(
                        lib.get(bs), _beam_fy_of(bs), bay_width,
                        ld_kg * G_ACC, safety_factor=BEAM_SF)
                    cc[2].caption(
                        f"SF {BEAM_SF:g} bending check: util {u['util']:.2f} "
                        + ("✅" if u["util"] <= 1.0
                           else "⚠️ overstressed — pick a heavier beam"))
                except (KeyError, ValueError):
                    pass

                levels.append(LevelSpec(gap=gap, beam_section=bs,
                                        pallet_load=ld_kg * G_ACC))
                elev += gap
            frame_h = st.number_input(
                "Frame height [mm] (>= top level)", min_value=elev,
                value=max(float(g("frame_height", None) or (elev + 500)), elev),
                step=50.0)

    with st.container(border=True):
        ui.section("◣", "Cross-aisle bracing")
        c = st.columns(4)
        btype = c[0].radio("Pattern", ["D", "X"],
                           index=0 if g("bracing_type", "D") == "D" else 1,
                           help="D = zigzag, X = crossed pairs")
        first_side = c[1].radio(
            "First diagonal connects to", ["outer", "inner"],
            index=0 if g("bracing_first_side", "inner") == "outer" else 1,
            help="The first diagonal above the bottom horizontal connects to "
                 "the OUTER (aisle-side) or INNER upright of each frame; both "
                 "frames of a back-to-back module are mirrored accordingly.")
        bstart = c[2].number_input("First horizontal [mm]", 50.0, 1000.0,
                                   float(g("bracing_start", 150.0)), 10.0)
        bpitch = c[3].number_input("Diagonal pitch [mm]", 200.0, 2000.0,
                                   float(g("bracing_pitch", 600.0)), 50.0)
        # X-bracing up to a chosen level: the lower frames use the X pattern
        # (up to that elevation), the Pattern above stays as selected.
        ca_x_height = None
        ca_brace_zones: tuple = ()
        if not is_di:
            elevs, _z = [], 0.0
            for ls in levels:
                _z += float(ls.gap or 0.0)
                elevs.append(_z)
            x_opts = ["(none)"] + [f"level {i + 1}  ({e:.0f} mm)"
                                   for i, e in enumerate(elevs)]
            _cur = g("ca_x_height", None)
            _idx_x = 0
            if _cur:
                _idx_x = next((i + 1 for i, e in enumerate(elevs)
                               if abs(e - float(_cur)) <= 1.0), 0)
            x_sel = st.selectbox(
                "X-brace lower frames up to level", x_opts, index=_idx_x,
                help="Use the X pattern from the floor up to ONE full bracing "
                     "panel above the selected level (so the level is fully "
                     "X-braced); the Pattern above stays as selected. "
                     "'(none)' = the Pattern applies the full height.")
            if x_sel != "(none)":
                ca_x_height = elevs[x_opts.index(x_sel) - 1]
            # CA bracing zones (seismic): more cross-aisle diagonals per panel
            # in the lower frames; extras are real members offset 100 mm
            import pandas as pd
            st.caption("CA bracing zones (seismic) — extra cross-aisle "
                       "diagonals per panel up to a height; the base X is at "
                       "offset 0 and each extra pair is a real X offset 100 mm. "
                       "Leave empty to use the single Pattern / X setting above.")
            _zrows = [{"Up to height [mm]": float(z),
                       "Diagonals per panel": int(c)}
                      for z, c in (g("ca_brace_zones", ()) or ())]
            _zedit = st.data_editor(
                pd.DataFrame(_zrows, columns=["Up to height [mm]",
                                              "Diagonals per panel"]),
                num_rows="dynamic", hide_index=True, width="stretch",
                # per-config key: a static key would keep a previous config's
                # (possibly empty) editor state when switching configurations,
                # making the saved zones appear to vanish
                key=f"ca_zones_editor_{st.session_state.get('edit_cfg') or 'new'}")
            _zones = []
            for _, _row in _zedit.iterrows():
                try:
                    _h = float(_row["Up to height [mm]"])
                    _c = int(_row["Diagonals per panel"])
                except (TypeError, ValueError):
                    continue
                if _h > 0 and _c >= 1:
                    _zones.append((_h, _c))
            ca_brace_zones = tuple(sorted(_zones))
        zone1 = "same"             # 'different pattern below level 1' removed

    with st.expander("🔩  Material & brace connections" if is_di
                     else "🔩  Connections, base & checks"):
        # beam (connector) stiffness source - defaults; the selective branch
        # exposes the selector below (drive-in rails use their own handling)
        connector_stiffness_source = g("connector_stiffness_source", "master")
        connector_calc_factor = float(g("connector_calc_factor", 2.0))
        connector_stiffness_val = float(g("connector_stiffness", 1.0e8))
        # connector moment bolts (defaults; the selective form may override)
        connector_bolt_count = int(g("connector_bolt_count", 0))
        _cbl0 = g("connector_bolt_lever", None)
        connector_bolt_lever = float(_cbl0) if _cbl0 else None
        # per-role material (fy) overrides: entered value wins over the master
        # per-section fy; 0 keeps the master / default grade
        ui.section("🧪", "Material per member type (0 = master / default)")
        cm = st.columns(3)
        fy_up_in = cm[0].number_input(
            "fy Upright [MPa]", 0.0, 700.0,
            float(g("fy_upright", None) or 0.0), 5.0,
            help="Overrides the master fy for every UPRIGHT section "
                 "(e.g. 250 for IS 2062 E250). 0 = keep the master value.")
        fy_bm_in = cm[1].number_input(
            "fy Beam [MPa]", 0.0, 700.0,
            float(g("fy_beam", None) or 0.0), 5.0,
            help="Overrides the master fy for every BEAM section "
                 "(e.g. 350 for E350). 0 = keep the master value (270/310...).")
        fy_br_in = cm[2].number_input(
            "fy Bracing [MPa]", 0.0, 700.0,
            float(g("fy_bracing", None) or 0.0), 5.0,
            help="Overrides the master fy for every BRACING section. "
                 "0 = keep the master value.")
        # per-SECTION yield strength: an entered value overrides the master fy
        # (and the role inputs above) for that one section; 0 = master default
        _sel_secs: list = []
        for _nm in ([up_sec] +
                    [getattr(_ls, "beam_section", None) for _ls in levels] +
                    [br_sec, stiffener_section]):
            if _nm and _nm not in _sel_secs:
                _sel_secs.append(_nm)
        _saved_fys = g("fy_sections", {}) or {}
        st.caption("Per-section YS override [MPa] — 0 = master default "
                   "(shown per section); an entered value overrides the "
                   "master and the per-type inputs above for that section.")
        fy_sections: dict = {}
        _fy_cols = st.columns(min(max(len(_sel_secs), 1), 4))
        for _i, _nm in enumerate(_sel_secs):
            _mfy = (master.fy.get(_nm) if master is not None else None)
            _v = _fy_cols[_i % len(_fy_cols)].number_input(
                f"YS {_nm}", 0.0, 700.0,
                float(_saved_fys.get(_nm, 0.0) or 0.0), 5.0,
                key=f"fy_sec_{_nm}",
                help=f"Master default: {_mfy:g} MPa. 0 = use it." if _mfy
                     else "Master default not set (uses the global fy). "
                          "0 = default.")
            if _v:
                fy_sections[_nm] = float(_v)
        core_checks = st.checkbox(
            "Verdict from core checks only — deflection, stress & buckling",
            bool(g("core_checks_only", True)),
            help="PASS/FAIL is decided by the DEFLECTION, STRESS and BUCKLING "
                 "checks (plus frame sway and convergence). The connector, "
                 "shear, brace-bolt, splice, anchorage and base-plate checks "
                 "are still computed and shown, but as informative only.")
        if is_di:
            # drive-in: steel grade, semi-rigid base, and the brace bolt
            # connection (no footplate / anchor check).
            c = st.columns(3)
            fy = c[0].number_input("Default fy [MPa]", 200.0, 700.0,
                                   gn("steel_fy", 355.0, 200.0, 700.0), 5.0)
            fy_override = c[0].checkbox(
                "Apply fy to all sections (override master)",
                bool(g("fy_override", False)),
                help="Use this fy for every section, ignoring any per-section "
                     "fy stored in the master (e.g. RFEM-imported masters).")
            _bs = g("base_stiffness", "auto")
            _bmodes = ["Master table (tested)", "Calculated (R899 formula)",
                       "Manual value"]
            _bidx = (1 if _bs == "derived"
                     else 2 if not isinstance(_bs, str) else 0)
            base_mode = c[1].selectbox(
                "Base stiffness source", _bmodes, index=_bidx,
                help="Down-aisle floor connection (rotational spring). "
                     "'Master table' = tested EN 15512 values (falls back to "
                     "the R899 calculation if the upright has no table); "
                     "'Calculated' = R899 formula from the upright properties "
                     "(k_b Eq43 in series with k_h Eq46); "
                     "'Manual value' = the value entered below.")
            kbase = c[2].number_input(
                "Floor stiffness [kNm/rad] (Manual)", 0.0, 5000.0,
                float(_bs / 1e6 if not isinstance(_bs, str) else 500.0),
                disabled=(base_mode != "Manual value"),
                help="Used only with the 'Manual value' source; 0 = pinned.")
            base_stiff = ("auto" if base_mode == _bmodes[0]
                          else "derived" if base_mode == _bmodes[1]
                          else kbase * 1e6)
            c = st.columns(3)
            bolt = c[0].selectbox("Brace bolt",
                                  ["M8", "M10", "M12", "M14", "M16"],
                                  index=_idx(["8", "10", "12", "14", "16"],
                                             str(int(g("bolt_d", 8.0)))))
            grade = c[1].selectbox(
                "Bolt grade", ["4.6", "4.8", "5.6", "5.8", "8.8", "10.9"],
                index=_idx(["4.6", "4.8", "5.6", "5.8", "8.8", "10.9"],
                           g("bolt_grade", "8.8")))
            brace_planes = c[2].number_input(
                "Brace shear planes (1 / 2)", 1, 2, int(g("brace_planes", 1)))
            # selective-only inputs default (unused by the drive-in model)
            brace_factor = gn("brace_area_factor", 0.15, 0.05, 1.0)
            fck = gn("concrete_fck", 25.0, 15.0, 60.0)
            plate_fy = gn("plate_fy", 310.0, 200.0, 460.0)
            pb = pd_ = pt = 0.0
            n_anch = int(g("n_anchors", 2))
            anch_d = "M" + str(int(g("anchor_d", 12.0)))
            anch_grade = g("anchor_grade", "5.6")
            anch_hef = gn("anchor_hef", 70.0, 30.0, 250.0)
            anch_s = anch_c = anch_np = anch_vc = 0.0
        else:
            c = st.columns(3)
            fy = c[0].number_input("Default fy [MPa]", 200.0, 700.0,
                                   gn("steel_fy", 355.0, 200.0, 700.0), 5.0)
            fy_override = c[0].checkbox(
                "Apply fy to all sections (override master)",
                bool(g("fy_override", False)),
                help="Use this fy for every section, ignoring any per-section "
                     "fy stored in the master (e.g. RFEM-imported masters).")
            _bs = g("base_stiffness", "auto")
            _bmodes = ["Master table (tested)", "Calculated (R899 formula)",
                       "Manual value"]
            _bidx = (1 if _bs == "derived"
                     else 2 if not isinstance(_bs, str) else 0)
            base_mode = c[1].selectbox(
                "Base stiffness source", _bmodes, index=_bidx,
                help="'Master table' = tested EN 15512 values (falls back to "
                     "5.0e8 with no master); 'Calculated' = R899 formula from "
                     "the upright properties; 'Manual value' = value below.")
            kbase = c[2].number_input("Floor stiffness [kNm/rad] (Manual)",
                                      0.0, 5000.0,
                                      float(_bs / 1e6 if not isinstance(_bs, str)
                                            else 500.0),
                                      disabled=(base_mode != "Manual value"))
            base_stiff = ("auto" if base_mode == _bmodes[0]
                          else "derived" if base_mode == _bmodes[1]
                          else kbase * 1e6)
            c = st.columns(3)
            _cmodes = ["Master import (tested)", "Calculated (E·I/L formula)",
                       "Manual value"]
            _cidx = {"master": 0, "calculated": 1,
                     "manual": 2}.get(connector_stiffness_source, 0)
            conn_mode = c[0].selectbox(
                "Beam stiffness source", _cmodes, index=_cidx,
                help="Beam-to-upright connector rotational spring. "
                     "'Master import' = tested per-upright-thickness values "
                     "(falls back to the connector default); 'Calculated' = "
                     "factor·E·I_b/L_b from the beam section, bounded by the "
                     "beam's own flexural stiffness; 'Manual value' = below.")
            conn_factor_in = c[1].number_input(
                "Beam stiffness factor (×E·I/L)", 1.0, 8.0,
                connector_calc_factor, 1.0,
                disabled=(conn_mode != _cmodes[1]),
                help="Calculated source only: 2 = far end pinned, 4 = fixed, "
                     "6 = double curvature (down-aisle sway, stiffest).")
            conn_manual_in = c[2].number_input(
                "Beam stiffness [kNm/rad] (Manual)", 0.0, 5000.0,
                connector_stiffness_val / 1e6,
                disabled=(conn_mode != _cmodes[2]),
                help="Used only with the 'Manual value' source.")
            connector_stiffness_source = {0: "master", 1: "calculated",
                                          2: "manual"}[_cmodes.index(conn_mode)]
            connector_calc_factor = float(conn_factor_in)
            connector_stiffness_val = float(conn_manual_in) * 1e6
            # moment bolts added to the beam-end connector to STRENGTHEN a
            # failing connector: the bolts resist the beam-end moment as a
            # tension couple (M_Rd += n·F_t,Rd·a).  The stiffness is NOT
            # calculated from the bolts (bracket / upright-face bending
            # governs and must be tested); a tested table raises it.
            cb = st.columns(2)
            connector_bolt_count = int(cb[0].number_input(
                "Connector moment bolts (per end)", 0, 6,
                int(g("connector_bolt_count", 0)), 1,
                help="Bolts added to the beam-end connector. 0 = bare tested "
                     "(hook) connector. Each bolt adds n·F_t,Rd·a to the "
                     "moment CAPACITY (tension couple, EN 1993-1-8 Table 3.4; "
                     "uses the brace bolt d/grade). The connector STIFFNESS is "
                     "not calculated from bolts — it is dominated by the "
                     "bracket/upright bending and must be measured (enter a "
                     "tested per-bolt-count table to raise it)."))
            _cbl = g("connector_bolt_lever", None)
            connector_bolt_lever = cb[1].number_input(
                "Bolt lever arm a [mm] (0 = beam depth)", 0.0, 400.0,
                float(_cbl or 0.0), 5.0,
                disabled=(connector_bolt_count == 0),
                help="Lever arm of the tension bolts from the compression "
                     "edge of the connector. 0 = use the beam section depth.")
            connector_bolt_lever = (float(connector_bolt_lever)
                                    if connector_bolt_lever > 0 else None)
            c = st.columns(3)
            brace_factor = c[0].number_input(
                "Bracing area factor", 0.05, 1.0,
                gn("brace_area_factor", 0.15, 0.05, 1.0), 0.05)
            bolt = c[1].selectbox("Brace bolt",
                                  ["M8", "M10", "M12", "M14", "M16"],
                                  index=_idx(["8", "10", "12", "14", "16"],
                                             str(int(g("bolt_d", 8.0)))))
            grade = c[2].selectbox(
                "Bolt grade", ["4.6", "4.8", "5.6", "5.8", "8.8", "10.9"],
                index=_idx(["4.6", "4.8", "5.6", "5.8", "8.8", "10.9"],
                           g("bolt_grade", "8.8")))
            brace_planes = st.number_input(
                "Brace shear planes (1 single C, 2 double / back-to-back C)",
                1, 2, int(g("brace_planes", 1)))
            c = st.columns(3)
            fck = c[0].number_input("Concrete f_ck [MPa]", 15.0, 60.0,
                                    gn("concrete_fck", 25.0, 15.0, 60.0), 5.0)
            plate_fy = c[1].number_input("Plate fy [MPa]", 200.0, 460.0,
                                         gn("plate_fy", 310.0, 200.0, 460.0), 5.0)
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
            anch_grade = c[2].selectbox(
                "Anchor grade", ["4.6", "5.6", "5.8", "8.8", "10.9"],
                index=_idx(["4.6", "5.6", "5.8", "8.8", "10.9"],
                           g("anchor_grade", "5.6")))
            anch_hef = c[3].number_input("Embedment hef [mm]", 30.0, 250.0,
                                         gn("anchor_hef", 70.0, 30.0, 250.0), 5.0)
            c = st.columns(4)
            anch_s = c[0].number_input("Anchor spacing [mm] (0=auto)", 0.0,
                                       500.0,
                                       float(g("anchor_spacing", None) or 0.0))
            anch_c = c[1].number_input("Edge distance [mm] (0=none)", 0.0, 500.0,
                                       float(g("anchor_edge", None) or 0.0))
            anch_np = c[2].number_input(
                "Pull-out N_Rk,p [kN] (0=default)", 0.0, 200.0,
                float((g("anchor_pullout_rk", None) or 0.0) / 1e3))
            anch_vc = c[3].number_input(
                "Shear V_Rk,c [kN] (0=default)", 0.0, 200.0,
                float((g("anchor_shear_rk", None) or 0.0) / 1e3))

    with st.expander("⬇  Loads, imperfection & factors"):
        c = st.columns(3)
        dead = c[0].number_input(
            "Additional beam dead load [N/mm]", 0.0, 1.0,
            float(g("dead_load_beam", 0.0)),
            help="Extra dead load on every beam per level (decking, panels, "
                 "services...). The beam SELF-WEIGHT is taken automatically "
                 "from the selected beam section (A·ρ·g) - do NOT enter it "
                 "here. 0 = self-weight only.")
        place = c[1].number_input(
            "Placement load [kN] (manual)", 0.0, 5.0,
            float(g("placement_load", 500.0) / 1e3),
            help="Used only when the EN 15512 automatic placement below is "
                 "OFF (single position at the top beam level).")
        placement_auto = c[1].checkbox(
            "Placement per EN 15512 6.3.4 (auto)",
            bool(g("placement_auto", True)),
            help="Magnitude by the height function (0.5 kN <= 3 m, linear to "
                 "0.25 kN at 6 m) and one combination per candidate position: "
                 "the top beam level plus the highest level <= 3 m.")
        phi_s = c[2].number_input(
            "Out-of-plumb down-aisle (1/x)", 100.0, 1000.0, 300.0,
            help="Down-aisle (X) sway imperfection 1/x. Drive-in default 1/300.")
        c = st.columns(4)
        phi_s_cross = c[0].number_input(
            "Out-of-plumb cross-aisle (1/x)", 100.0, 1000.0, 200.0,
            help="Cross-aisle (Y) sway imperfection 1/x. Drive-in default 1/200; "
                 "ignored for selective racking.")
        # Imperfections are handled ONE way (RSTAB basis, no user option):
        # the out-of-plumb values above are applied directly as a flat
        # EN 1993 inclination (default 1/300 down-aisle, 1/200 cross-aisle).
        c = st.columns(4)
        ax = c[1].number_input("Accidental X [kN]", 0.0, 10.0,
                               float(g("accidental_load_x", 1250.0) / 1e3))
        ay = c[2].number_input("Accidental Y [kN]", 0.0, 10.0,
                               float(g("accidental_load_y", 2500.0) / 1e3))
        ah = c[3].number_input("Accidental height [mm]", 100.0, 1000.0,
                               gn("accidental_height", 400.0, 100.0, 1000.0), 50.0)
        c = st.columns(3)
        inc_place = c[0].checkbox("Include placement loads",
                                  bool(g("include_placement", True)))
        inc_acc = c[1].checkbox("Include accidental loads",
                                bool(g("include_accidental", True)))
        inc_patt = c[2].checkbox(
            "Include pattern (checkerboard) pallet load",
            bool(g("include_pattern", True)),
            help="Alternate bays AND levels loaded — the unfavourable partial "
                 "loading that maximises differential column moments and sway. "
                 "Mandatory down-aisle per EN 15512 10.2.2.2.")
        patt_ca = c[2].checkbox(
            "Pattern in cross-aisle too",
            bool(g("pattern_cross_aisle", False)),
            help="EN 15512 10.2.2.3 Note 1 exempts the cross-aisle direction; "
                 "enable when imperfection + pattern is near-critical for the "
                 "upright checks.")
        c = st.columns(3)
        lf_max = int(n_lanes) if is_di else int(n_bays)
        _lf_default = lf_max // 2 if lf_max >= 2 else 0   # governing interior line
        _lf = g("load_frame", _lf_default)
        if _lf is None:                                   # None -> auto interior
            _lf = _lf_default
        load_frame = c[0].number_input(
            f"Load frame (upright line 0..{'n_lanes' if is_di else 'n_bays'})",
            0, lf_max, int(min(max(_lf, 0), lf_max)),
            help="Upright line (front face for drive-in) carrying the placement "
                 "& accidental loads. Default = the governing INTERIOR frame "
                 "(shared between two bays); 0 = end/corner frame.")
        beam_restrained = c[1].checkbox(
            "Rails/beams laterally restrained by the unit load" if is_di
            else "Beams laterally restrained by the unit load",
            bool(g("beam_laterally_restrained", True)),
            help="On = beams/rails held against LTB by the stored unit load "
                 "(EN 15512 §9.4); the LTB check records the assumption. Off = "
                 "compute χ_LT and verify lateral-torsional buckling.")
        c = st.columns(3)
        # drive-in ULS uses gamma_G = 1.35 (RSTAB); selective uses 1.3
        # separate ULS factor per action: gamma_G*DL + gamma_Q*LL + gamma_PL*PL
        gG = c[0].number_input(
            "gamma DL (ULS)", 1.0, 2.0,
            gn("gamma_G_uls" if is_di else "gamma_G",
               1.35 if is_di else 1.3, 1.0, 2.0),
            help="Dead-load ULS factor, applied to DL in every ULS combination.")
        gQ = c[1].number_input(
            "gamma LL (ULS)", 1.0, 2.0, gn("gamma_Q", 1.4, 1.0, 2.0),
            help="Live (pallet) load ULS factor, applied to LL in every ULS "
                 "combination (pay, placement and pattern).")
        _gpl_saved = g("gamma_PL", None)
        if _gpl_saved is None:
            _gpl_saved = g("pay_placement_factor", 1.26)   # legacy fallback
        gPL = c[2].number_input(
            "gamma Placement (ULS)", 1.0, 2.0,
            float(min(max(float(_gpl_saved or 1.26), 1.0), 2.0)),
            help="Placement-load ULS factor before the multi-variable "
                 "reduction: the placement combinations are gamma_DL*DL + "
                 "psi*gamma_LL*LL + psi*gamma_PL*PL.")
        psi_mv = c[2].number_input(
            "psi multi-variable (EN 15512 Eq 7)", 0.5, 1.0,
            float(g("multi_var_factor", 0.9)), 0.05,
            help="Reduction on SIMULTANEOUS variable actions (Q + placement): "
                 "0.9 x 1.4 = 1.26 per EN 15512 7.2 Eq (7). Set 1.0 to apply "
                 "the entered gammas unreduced (e.g. flat RSTAB 1.2/1.2).")
        # stiffness is NEVER reduced by a material factor: the analysis runs on
        # the full elastic E/G (gamma_M on stiffness = 1.0, no app option) -
        # material effects are already covered by the entered data
        stiffness_gamma_m_val = 1.0

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
            gn("seismic_importance", 1.0, 1.0, 1.5), 0.1,
            help="1.0 normal, 1.5 important / high-occupancy (Table 8)")
        s_kappa = c[3].number_input(
            "Imposed-load factor κ", 0.0, 1.0,
            gn("seismic_imposed_factor", 0.8, 0.0, 1.0), 0.05,
            help="Fraction of pallet (live) load in the seismic weight: "
                 "W = 1.0·DL + κ·LL. Default 0.8 (80% of service live load).")
        s_damp = st.slider("Damping ratio", 0.01, 0.10,
                           gn("seismic_damping", 0.05, 0.01, 0.10), 0.01,
                           help="5% typical for bolted steel racks")
        c = st.columns(2)
        pallet_sliding = c[0].checkbox(
            "EN 16681 unit-load sliding cap", bool(g("pallet_sliding", False)),
            help="Cap the horizontal seismic force a pallet transfers at "
                 "~1.5·μ·W_pallet (the pallet slides on the beam rather than "
                 "transferring full spectral force). Approximate.")
        pallet_mu = c[1].number_input(
            "Pallet friction μ", 0.05, 1.0,
            gn("pallet_mu", 0.37, 0.05, 1.0), 0.01,
            help="Design pallet-to-beam friction coefficient (wood-on-steel "
                 "≈0.37; verify per EN 16681 Annex B).")
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
            float(r_from_type) if r_from_type is not None
            else gn("seismic_response_reduction", 4.0, 1.0, 6.0), 0.5,
            disabled=r_from_type is not None)
        s_modes = cc[1].number_input(
            "Modes (min)", 1, 12, int(g("seismic_n_modes", 6)),
            help="Auto-increased until ≥90% mass per direction (Cl 7.7.5.2)")
        Z = ZONE_FACTORS[s_zone]
        sa_plateau = design_spectrum_sa_g(0.3, s_soil)
        ah_coeff = (Z / 2.0) * (s_I / s_R) * sa_plateau   # don't clobber `ah`
        st.caption(
            f"**Z = {Z}**, Sa/g(plateau) = {sa_plateau:.2f}, "
            f"**Ah = (Z/2)(I/R)(Sa/g) = {ah_coeff:.4f}** (R = {s_R:g}). "
            "Combinations 1.2(DL+IL±EL), 1.5(DL±EL), 0.9DL±1.5EL (IS 800 LSD); "
            "modal RSA, SRSS, base-shear scaling, directions 100%+30%.")
        if not is_di:
            # selective-rack seismic bracing (spine / plan). Drive-in sets its
            # spine (auto from variant) and top plan bracing in the Multi-deep
            # section above, so this selective block is hidden for drive-in.
            st.markdown("**Seismic bracing** (truss members)")
            c = st.columns(4)
            # include the standard 1C lipped-channel family (generated on the
            # fly by the builder) so the spine / plan dropdowns aren't limited
            # to the master-library bracing sections
            from rack15512.cf_sections import STD_1C
            _libbr = [n for n in br_names if n not in STD_1C]
            brace_opts = ["(frame brace)"] + STD_1C + _libbr
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
            pl_sec = c[0].selectbox(
                "Plan section", brace_opts,
                index=_idx(brace_opts,
                           pl_default if pl_default in brace_opts
                           else "(frame brace)"))
            pl_mod = c[1].selectbox("Plan modules", ["all", "alternate",
                                                     "every_3rd"],
                                    index=_idx(["all", "alternate", "every_3rd"],
                                               g("plan_bracing_modules", "all")))
            pl_type = c[2].selectbox(
                "Plan bracing type", ["D", "X"],
                index=_idx(["D", "X"], g("plan_bracing_type", "D")))
            pl_specific = c[3].text_input(
                "Specific plan modules (e.g. 0,2)",
                value=",".join(str(i) for i in (g("plan_bracing_module_list",
                                                  None) or [])))
            pl_list = [int(s) for s in pl_specific.replace(" ", "").split(",")
                       if s.lstrip("-").isdigit()] or None
            sp_list = None          # selective spine bays use the module pattern

    cfg = RackConfig(
        system_type=("mezzanine" if is_mz
                     else "drive_in" if is_di else "selective"),
        **di_kw, **mz_kw,
        name=name, module=module, n_bays=int(n_bays), bay_width=bay_width,
        depth=depth, b2b_gap=b2b_gap, levels=levels, frame_height=frame_h,
        bracing_first_side=first_side, bracing_type=btype,
        bracing_start=bstart, bracing_pitch=bpitch,
        bracing_type_zone1=None if zone1 == "same" else zone1,
        ca_x_height=ca_x_height, ca_brace_zones=ca_brace_zones,
        upright_section=up_sec, brace_section=br_sec, steel_fy=fy,
        fy_override=bool(fy_override), spacer_section=spacer_section,
        stiffener_section=stiffener_section,
        reinforce_height=float(reinforce_height),
        stiffener_offset=float(stiffener_offset),
        stiffener_type=int(stiffener_type),
        stiffener_shear_k=(None if stiffener_shear_k is None
                           else float(stiffener_shear_k)),
        stiffener_bolt_d=float(stiffener_bolt_d),
        stiffener_bolt_grade=str(stiffener_bolt_grade),
        stiffener_bolt_pitch=float(stiffener_bolt_pitch),
        stiffener_modelling=str(stiffener_modelling),
        base_stiffness=base_stiff,
        brace_area_factor=brace_factor, bolt_d=float(bolt[1:]),
        bolt_grade=grade, brace_planes=int(brace_planes),
        concrete_fck=fck, plate_fy=plate_fy,
        plate_b=pb or None, plate_d=pd_ or None, plate_t=pt or None,
        n_anchors=int(n_anch), anchor_d=float(anch_d[1:]),
        anchor_grade=anch_grade, anchor_hef=anch_hef,
        anchor_spacing=anch_s or None, anchor_edge=anch_c or None,
        anchor_pullout_rk=(anch_np * 1e3) or None,
        anchor_shear_rk=(anch_vc * 1e3) or None,
        dead_load_beam=dead, placement_load=place * 1e3,
        accidental_load_x=ax * 1e3, accidental_load_y=ay * 1e3,
        accidental_height=ah, include_placement=inc_place,
        include_accidental=inc_acc, include_pattern=inc_patt,
        pattern_cross_aisle=bool(patt_ca), placement_auto=bool(placement_auto),
        multi_var_factor=float(psi_mv),
        load_frame=int(load_frame),
        beam_laterally_restrained=bool(beam_restrained),
        pallet_sliding=bool(pallet_sliding), pallet_mu=float(pallet_mu),
        gamma_G=gG, gamma_G_uls=gG, gamma_Q=gQ, gamma_PL=float(gPL),
        fy_upright=float(fy_up_in) or None, fy_beam=float(fy_bm_in) or None,
        fy_bracing=float(fy_br_in) or None,
        fy_sections=fy_sections or None,
        core_checks_only=bool(core_checks),
        phi_s=1.0 / phi_s,
        phi_s_cross=1.0 / phi_s_cross,
        imperfection_standard="EN1993",     # single basis (RSTAB), no app option
        stiffness_gamma_m=stiffness_gamma_m_val,
        connector_stiffness=connector_stiffness_val,
        connector_stiffness_source=connector_stiffness_source,
        connector_calc_factor=connector_calc_factor,
        connector_bolt_count=connector_bolt_count,
        connector_bolt_lever=connector_bolt_lever,
        seismic=seismic, seismic_zone=s_zone, seismic_soil=s_soil,
        seismic_importance=s_I, seismic_response_reduction=s_R,
        seismic_structure_type=s_struct,
        seismic_damping=s_damp, seismic_imposed_factor=s_kappa,
        seismic_n_modes=int(s_modes),
        spine_bracing=sp_on,
        spine_bracing_section=None if sp_sec == "(frame brace)" else sp_sec,
        spine_bracing_modules=sp_mod, spine_bracing_module_list=sp_list,
        plan_bracing=pl_on,
        plan_bracing_section=None if pl_sec == "(frame brace)" else pl_sec,
        plan_bracing_modules=pl_mod, plan_bracing_type=pl_type,
        plan_bracing_module_list=pl_list)
    cfg.master = master
    _upright_suggester(cfg, lib, master, up_names)
    return cfg


def _upright_suggester(cfg, lib, master, up_names):
    """Pre-run, closed-form upright pre-sizing: rank the master upright sections
    for a given axial load + buckling length (drive-in is pinned-pinned, K=1.0)
    and one-click apply the chosen section to the configuration."""
    from rack15512 import presize
    if not up_names:
        return
    with st.expander("💡 Suggest upright section (closed-form, pre-run)"):
        # all four inputs are computed directly from the configuration so they
        # always track the current inputs (no stale manual values)
        est = presize.static_upright_demand(cfg)
        N = est["N_design"]
        lcy, lcz = est["Lcr_y"], est["Lcr_z"]   # Iy=cross-aisle, Iz=down-aisle
        fy = est["fy"]
        di = getattr(cfg, "system_type", "selective") != "selective"
        st.caption(
            f"Computed from the configuration: factored pallet load "
            f"≈ {est['P_total']/1e3:.0f} kN over {est['n_uprights']} uprights "
            f"→ ~{est['N_avg']/1e3:.1f} kN average · design load "
            f"= ×{est['k_dist']:g} worst/avg. Buckling lengths (K = 1.0, "
            "pinned-pinned): cross-aisle = bracing pitch; down-aisle = "
            + ("full frame height (uprights unbraced down-aisle)" if di
               else "largest beam-level gap") + ". fy per section from master.")
        c = st.columns(4)
        c[0].metric("Axial load N", f"{N/1e3:.1f} kN")
        c[1].metric("Lcr down-aisle", f"{est['Lcr_da']:.0f} mm")
        c[2].metric("Lcr cross-aisle", f"{est['Lcr_ca']:.0f} mm")
        c[3].metric("fy (default)", f"{fy:.0f} MPa")

        def _fy_of(name):
            if master is not None:
                try:
                    return master.fy.get(name) or fy
                except Exception:
                    return fy
            return fy

        rows = presize.suggest_uprights(lib, _fy_of, N=N, Lcr_y=lcy, Lcr_z=lcz)
        if not rows:
            st.info("No upright sections in the master.")
            return
        st.dataframe(
            [{"section": r["name"], "A [mm²]": round(r["area"]),
              "fy": round(r["fy"]), "χ_min": round(r["chi_min"], 3),
              "N_b,Rd [kN]": round(r["N_b_Rd"] / 1e3, 1),
              "utilisation": round(r["util"], 3),
              "status": ("✅ PASS" if r["passes"] else "❌ FAIL")
              + (" · lightest" if r["recommended"] else "")}
             for r in rows],
            hide_index=True, width="stretch")
        passing = [r["name"] for r in rows if r["passes"]]
        rec = next((r["name"] for r in rows if r["recommended"]), None)
        if passing:
            cc = st.columns([3, 1])
            pick = cc[0].selectbox("Apply upright section", passing,
                                   index=passing.index(rec) if rec else 0,
                                   key="sug_pick")
            if cc[1].button("Apply", key="sug_apply"):
                # defer to the next run (the Upright widget already exists this
                # run); the top of the form applies it before that widget
                st.session_state["_pending_upright"] = pick
                st.rerun()
        else:
            st.warning("No section passes — increase the section range or "
                       "reduce the load / buckling length.")


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
    if top[1].button("➕ Create new project", width="stretch",
                     type="primary"):
        goto("new_project")

    if not projects:
        ui.empty_state("📦", "No projects yet",
                       "Create your first project to start designing a rack.")
        if st.button("➕ Create your first project", type="primary"):
            goto("new_project")
        return

    query = st.text_input(
        "🔍 Search projects", ss.get("proj_search", ""),
        placeholder="Search by project name, project ID, SO no. or client…",
        key="proj_search")
    q = query.strip().lower()
    if q:
        def _hit(p):
            return q in " ".join((p.name, p.project_no, p.so_no, p.revision,
                                  p.client)).lower()
        projects = [p for p in projects if _hit(p)]

    _ROW_COLS = [2.2, 1.1, 1.1, 0.9, 0.9, 0.9, 1, 1.7]
    hdr = st.columns(_ROW_COLS)
    for h, label in zip(hdr, ("Project", "Project ID", "SO No.", "Rev",
                              "Systems", "Configs", "Status", "")):
        h.markdown(f"<span class='rnr-muted' style='font-size:.74rem;"
                   f"font-weight:700;text-transform:uppercase;"
                   f"letter-spacing:.05em'>{label}</span>",
                   unsafe_allow_html=True)
    st.divider()

    if not projects:
        ui.empty_state("🔍", "No matching projects",
                       f"Nothing matches '{query}'.")
        return

    for proj in projects:
        n_cfg = sum(len(s.configurations) for s in proj.systems)
        verdicts = [c.run_summary["verdict"]
                    for s in proj.systems for c in s.configurations
                    if c.run_summary]
        status = ("PASS" if verdicts and all(v == "PASS" for v in verdicts)
                  else ("FAIL" if any(v == "FAIL" for v in verdicts)
                        else "not run"))
        cc = st.columns(_ROW_COLS, vertical_alignment="center")
        meta = " · ".join(x for x in (proj.client, proj.location,
                                      proj.engineer) if x)
        cc[0].markdown(f"**{proj.name}**" + (f"  \n<span class='rnr-muted' "
                       f"style='font-size:.8rem'>{meta}</span>"
                       if meta else ""), unsafe_allow_html=True)
        cc[1].write(proj.project_no or "—")
        cc[2].write(proj.so_no or "—")
        cc[3].write(proj.revision or "—")
        cc[4].write(len(proj.systems))
        cc[5].write(n_cfg)
        cc[6].markdown(ui.pill(status), unsafe_allow_html=True)
        ac = cc[7].columns(2)
        if ac[0].button("Open →", key=f"open_{proj.id}", width="stretch",
                        type="primary"):
            goto("project", project_id=proj.id)
        if ac[1].button("🗑", key=f"delp_{proj.id}", width="stretch",
                        help="Delete project"):
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
        st.divider()


def render_new_project():
    if st.button("← Back to dashboard"):
        goto("dashboard")
    ui.hero("Create New Project", "Set up the job details and the first "
            "system.", eyebrow="New project")
    with st.form("newproj"):
        name = st.text_input("Project name *", "")
        c = st.columns(3)
        project_no = c[0].text_input("Project ID", "")
        so_no = c[1].text_input("SO No.", "")
        revision = c[2].text_input("Revision No.", "")
        c2 = st.columns(2)
        client = c2[0].text_input("Client", "")
        location = c2[1].text_input("Location", "")
        engineer = c2[0].text_input("Engineer", "")
        desc = st.text_area("Description", "")
        sysname = st.text_input("First system identifier", "Aisle 1")
        if st.form_submit_button("Create project", type="primary"):
            if not name.strip():
                st.error("Project name is required.")
            else:
                proj = PSTORE.create_project(name, client=client,
                                             location=location,
                                             engineer=engineer,
                                             description=desc,
                                             project_no=project_no,
                                             so_no=so_no, revision=revision)
                sysm = PSTORE.add_system(proj.id, sysname or "System 1")
                goto("project", project_id=proj.id, system_id=sysm.id)


SYSTEM_TYPES = ["Selective Pallet Racking",
                "Drive-In / Drive-Through / Radio Shuttle",
                "Structural Mezzanine",
                "EN 15512 manual check"]


def _member_forces_row(mr):
    """Governing axial (compression-positive convention preserved) plus the
    abs-max bending and shear of a member result."""
    n_gov = mr.N_min if abs(mr.N_min) > abs(mr.N_max) else mr.N_max
    return {"N [kN]": round(n_gov / 1e3, 2),
            "N_min [kN]": round(mr.N_min / 1e3, 2),
            "N_max [kN]": round(mr.N_max / 1e3, 2),
            "My,max [kNm]": round(mr.My_absmax / 1e6, 3),
            "Mz,max [kNm]": round(mr.Mz_absmax / 1e6, 3),
            "V,max [kN]": round(mr.V_absmax / 1e3, 2)}


def _manual_check_panel(proj, sysm):
    """EN 15512 manual check: pick a run configuration, a load case and a
    member; show the recovered N/My/Mz and every EN 15512 check that applies
    to that member (upright, beam, bracing, connector, splice, …)."""
    from rack15512.report_html import CLAUSES

    runnable = [c for c in sysm.configurations if c.run_summary]
    if not runnable:
        st.info("No analysed configuration in this system yet. Create a "
                "configuration and run it, then come back to do manual "
                "EN 15512 member checks.")
        return

    cc = st.columns([2, 2, 1.4])
    conf = cc[0].selectbox(
        "Configuration (run)", runnable, format_func=lambda c: c.name,
        key=f"mc_conf_{sysm.id}")
    cdir = PSTORE.config_dir(proj.id, sysm.id, conf.id)
    results = _load_results(cdir)
    if not results:
        st.warning("This configuration's results are missing on disk. "
                   "Re-run the analysis to refresh them.")
        return

    lib, master, _ = resolve_master(conf.master_id, conf.master_path)
    cfg = rackconfig_from_dict(conf.config, master=master)
    try:
        model = build_rack(cfg)
    except (ValueError, KeyError) as e:
        st.error(f"Could not rebuild the model: {e}")
        return

    cases, checks = results["cases"], results["checks"]
    case_names = [c.name for c in cases]
    case_name = cc[1].selectbox("Load case / combination", case_names,
                                key=f"mc_case_{sysm.id}")
    case = next(c for c in cases if c.name == case_name)

    sets = sorted({m.member_set for m in model.members.values()})
    set_filter = cc[2].selectbox("Member set filter", ["(all)"] + sets,
                                 key=f"mc_set_{sysm.id}")
    ids = sorted(mid for mid, m in model.members.items()
                 if set_filter == "(all)" or m.member_set == set_filter)
    if not ids:
        st.info("No members in that set.")
        return
    mid = st.selectbox("Member no.", ids, key=f"mc_mid_{sysm.id}")

    m = model.members[mid]
    sec = model.sections.get(m.section)
    st.markdown(
        f"**Member {mid}** · set **{m.member_set}** · type `{m.mtype}` · "
        f"section **{m.section}** · length {model.member_length(m):.0f} mm · "
        f"nodes {m.node_i}→{m.node_j}")
    if sec is not None:
        st.caption(
            f"Section: A={sec.A:.0f} mm² "
            f"(A_eff={ (sec.A_eff or sec.A):.0f}), Iy={sec.Iy:.3e}, "
            f"Iz={sec.Iz:.3e} mm⁴, Wely={sec.Wely:.0f}, Welz={sec.Welz:.0f} "
            f"mm³, material {sec.material}, role {sec.role or '-'}")

    mr = case.members.get(mid)
    if mr is None:
        st.warning("This member has no recovered result in the selected case.")
        return

    setl = m.member_set.lower()
    is_column = ("upright" in setl or "column" in setl or m.mtype == "column")
    st.markdown("##### Recovered internal forces (N, M_y, M_z)")
    st.caption("Down-aisle bending is M_z, cross-aisle bending is M_y; "
               "N is tension-positive." if is_column else
               "N is tension-positive; M_y/M_z are the local bending moments.")
    st.dataframe([_member_forces_row(mr)], hide_index=True, width="stretch")

    with st.expander("Station-by-station forces along the member"):
        rows = [{"x [mm]": round(s.x, 0),
                 "N [kN]": round(s.N / 1e3, 2),
                 "Vy [kN]": round(s.Vy / 1e3, 2),
                 "Vz [kN]": round(s.Vz / 1e3, 2),
                 "My [kNm]": round(s.My / 1e6, 3),
                 "Mz [kNm]": round(s.Mz / 1e6, 3),
                 "defl [mm]": round(s.defl, 2)} for s in mr.stations]
        st.dataframe(rows, hide_index=True, width="stretch")

    # EN 15512 checks that target this member in this case
    mchecks = [c for c in checks
               if c.case == case_name and c.target == f"member {mid}"]
    st.markdown("##### EN 15512 checks for this member")
    if not mchecks:
        st.info("No member-level checks were produced for this member/case "
                "(e.g. tension-only members skip buckling). Tighten the set "
                "filter or pick another case.")
    for c in mchecks:
        clause, descr = CLAUSES.get(c.check, ("", ""))
        icon = {"PASS": "🟢", "FAIL": "🔴", "INFO": "🔵"}.get(c.status, "•")
        with st.container(border=True):
            hc = st.columns([3, 1.2])
            hc[0].markdown(f"**{icon} {c.check}** — {clause}")
            hc[1].markdown(f"utilisation **{c.utilization:.3f}** "
                           f"({c.status})")
            if descr:
                st.caption(descr)
            if c.detail:
                st.code(c.detail, language=None)

    # uprights also carry the base-node checks (base plate / anchorage)
    if is_column:
        base = next((n for n in (m.node_i, m.node_j)
                     if any(s.node == n for s in model.supports)), None)
        if base is not None:
            ncks = [c for c in checks if c.case == case_name
                    and c.target == f"node {base}"]
            if ncks:
                st.markdown(f"##### Base checks at support node {base}")
                for c in ncks:
                    clause, descr = CLAUSES.get(c.check, ("", ""))
                    icon = {"PASS": "🟢", "FAIL": "🔴",
                            "INFO": "🔵"}.get(c.status, "•")
                    with st.container(border=True):
                        hc = st.columns([3, 1.2])
                        hc[0].markdown(f"**{icon} {c.check}** — {clause}")
                        hc[1].markdown(f"utilisation **{c.utilization:.3f}** "
                                       f"({c.status})")
                        if c.detail:
                            st.code(c.detail, language=None)


# ----------------------------------------------------------------- project
def render_project():
    proj = PSTORE.load(ss.project_id)
    if st.button("← Back to dashboard"):
        goto("dashboard")
    tags = " · ".join(x for x in (proj.project_no and f"ID {proj.project_no}",
                                  proj.so_no and f"SO {proj.so_no}",
                                  proj.revision and f"Rev {proj.revision}")
                      if x)
    meta = " · ".join(x for x in (tags, proj.client, proj.location,
                                  proj.engineer, proj.standard) if x)
    ui.hero(proj.name, meta, eyebrow="Project",
            crumbs=["Dashboard", proj.name])

    with st.expander("✏️ Edit project details"):
        with st.form("editproj"):
            ec = st.columns(3)
            e_no = ec[0].text_input("Project ID", proj.project_no)
            e_so = ec[1].text_input("SO No.", proj.so_no)
            e_rev = ec[2].text_input("Revision No.", proj.revision)
            ec2 = st.columns(2)
            e_client = ec2[0].text_input("Client", proj.client)
            e_loc = ec2[1].text_input("Location", proj.location)
            e_eng = ec2[0].text_input("Engineer", proj.engineer)
            e_desc = st.text_area("Description", proj.description)
            if st.form_submit_button("Save changes", type="primary"):
                proj.project_no, proj.so_no, proj.revision = e_no, e_so, e_rev
                proj.client, proj.location = e_client, e_loc
                proj.engineer, proj.description = e_eng, e_desc
                PSTORE.save(proj)
                st.rerun()

    n_total_cfg = sum(len(s.configurations) for s in proj.systems)
    hc = st.columns([3, 1])
    with hc[0].expander("➕ Add a system"):
        sn = st.text_input("System identifier", key="newsysname")
        if st.button("Add system") and sn.strip():
            sysm = PSTORE.add_system(proj.id, sn)
            goto("project", project_id=proj.id, system_id=sysm.id)
    if n_total_cfg >= 2 and hc[1].button("⚖️ Compare configurations",
                                         width="stretch"):
        goto("compare", project_id=proj.id)

    if not proj.systems:
        st.info("Add a system, then create a configuration in it.")
        return

    for sysm in proj.systems:
        sc = st.columns([6, 2])
        sc[0].subheader(f"System: {sysm.name}")
        if sc[1].button("🗑 Delete system", key=f"dsys_{sysm.id}",
                        width="stretch"):
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

        systype = st.selectbox(
            "System type", SYSTEM_TYPES, key=f"systype_{sysm.id}",
            help="Selective Pallet Racking = the parametric design flow. "
                 "EN 15512 manual check = verify a single member by load case "
                 "and member number (N, M_y, M_z + all EN 15512 checks).")
        if systype == "EN 15512 manual check":
            _manual_check_panel(proj, sysm)
            continue
        seed = (RackConfig(system_type="drive_in")
                if systype.startswith("Drive-In")
                else RackConfig(system_type="mezzanine")
                if systype.startswith("Structural") else None)

        if st.button("➕ New configuration", key=f"newcfg_{sysm.id}"):
            goto("configure", project_id=proj.id, system_id=sysm.id,
                 config_id=None, edit_cfg=seed)
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
                                width="stretch", type="primary"):
                    goto("view_config", project_id=proj.id,
                         system_id=sysm.id, config_id=conf.id)
                if cc[3].button("Edit", key=f"ec_{conf.id}",
                                width="stretch"):
                    cfg0 = rackconfig_from_dict(conf.config)
                    goto("configure", project_id=proj.id, system_id=sysm.id,
                         config_id=conf.id, edit_cfg=cfg0)
                if cc[4].button("🗑 Delete", key=f"dc_{conf.id}",
                                width="stretch"):
                    ss[f"confirm_dc_{conf.id}"] = True
                if ss.get(f"confirm_dc_{conf.id}"):
                    if cc[4].button("Confirm delete", key=f"dcy_{conf.id}",
                                    type="primary", width="stretch"):
                        PSTORE.delete_configuration(proj.id, sysm.id, conf.id)
                        ss[f"confirm_dc_{conf.id}"] = False
                        goto("project", project_id=proj.id)
                    if cc[4].button("Cancel", key=f"dcn_{conf.id}",
                                    width="stretch"):
                        ss[f"confirm_dc_{conf.id}"] = False
                        st.rerun()


def _failed_member_sets(checks, case_names):
    """Member ids that fail any check, and that fail BUCKLING, over the given
    set of analysis-case names (utilisation > 1.0, excluding informative)."""
    failed, buckling = set(), set()
    for c in checks:
        if (c.case in case_names and c.target.startswith("member")
                and not c.informative and c.utilization > 1.0):
            mid = int(c.target.split()[1])
            failed.add(mid)
            if c.check == "BUCKLING":
                buckling.add(mid)
    return failed, buckling


def _load_case_magnitude_rows(lc):
    """Magnitudes of the loads DEFINED in a load case (not factored): grouped
    nodal forces/moments and member UDLs.  Units: kN, kNm, kN/m (a member UDL
    qz in N/mm equals kN/m numerically)."""
    from collections import Counter
    rows = []
    nod = Counter()
    for nl in lc.nodal_loads:
        nod[(nl.fx, nl.fy, nl.fz, nl.mx, nl.my, nl.mz)] += 1
    for vals, cnt in nod.items():
        for comp, v, unit in (("Fx", vals[0], "kN"), ("Fy", vals[1], "kN"),
                              ("Fz", vals[2], "kN"), ("Mx", vals[3], "kNm"),
                              ("My", vals[4], "kNm"), ("Mz", vals[5], "kNm")):
            if abs(v) > 1e-9:
                rows.append({"kind": "nodal", "component": comp,
                             "magnitude": round(v / (1e3 if unit == "kN"
                                                      else 1e6), 3),
                             "unit": unit, "count": cnt})
    mem = Counter()
    for ml in lc.member_loads:
        mem[(round(ml.qx, 6), round(ml.qy, 6), round(ml.qz, 6))] += 1
    for (qx, qy, qz), cnt in mem.items():
        for comp, v in (("qx", qx), ("qy", qy), ("qz", qz)):
            if abs(v) > 1e-12:
                rows.append({"kind": "member UDL", "component": comp,
                             "magnitude": round(v, 3), "unit": "kN/m",
                             "count": cnt})
    return rows


def _section_governing_rows(model, checks):
    """Per SECTION: the max member utilisation for each check type, the
    governing check / member / case, sorted by the governing utilisation."""
    import collections
    order = ["STRESS", "BUCKLING", "SHEAR", "LTB", "BRACE_BUCKLING",
             "CONNECTOR", "DEFLECTION"]
    best = collections.defaultdict(dict)        # section -> {check: (u, mid, case)}
    role = {}
    for c in checks:
        if c.informative or not c.target.startswith("member"):
            continue
        try:
            mid = int(c.target.split()[1])
        except (ValueError, IndexError):
            continue
        m = model.members.get(mid)
        if m is None:
            continue
        role[m.section] = m.member_set
        cur = best[m.section].get(c.check)
        if cur is None or c.utilization > cur[0]:
            best[m.section][c.check] = (c.utilization, mid, c.case)
    rows = []
    for sec, d in best.items():
        gov = max(d, key=lambda k: d[k][0])
        u, mid, case = d[gov]
        row = {"section": sec, "set": role.get(sec, ""),
               "gov check": gov, "gov util": round(u, 3),
               "member": mid, "case": case}
        for chk in order:
            if chk in d:
                row[chk] = round(d[chk][0], 3)
        rows.append(row)
    rows.sort(key=lambda r: -r["gov util"])
    return rows


def _case_governing_rows(model, checks):
    """Per LOAD CASE / combination: the governing (highest-utilisation) member."""
    best = {}
    for c in checks:
        if c.informative or not c.target.startswith("member"):
            continue
        cur = best.get(c.case)
        if cur is None or c.utilization > cur[1]:
            try:
                mid = int(c.target.split()[1])
            except (ValueError, IndexError):
                mid = None
            m = model.members.get(mid)
            best[c.case] = (c.case, c.utilization, c.check, mid,
                            m.member_set if m else "", m.section if m else "")
    rows = [{"case": x[0], "util": round(x[1], 3), "check": x[2],
             "member": x[3], "set": x[4], "section": x[5]}
            for x in best.values()]
    rows.sort(key=lambda r: -r["util"])
    return rows


def _load_check_viewer(model, key: str):
    """Interactive 3D view that overlays the applied loads of a selected load
    case / combination, so the user can verify the loads were defined right."""
    cases = list(model.load_cases.keys())
    combos = [c.name for c in model.combinations]
    if not cases and not combos:
        return
    with st.container(border=True):
        ui.section("🧭", "Load check — applied loads on the model")
        opts = ([f"Combination: {c}" for c in combos]
                + [f"Load case: {c}" for c in cases])
        cc = st.columns([3, 1])
        sel = cc[0].selectbox("Load case / combination", opts,
                              key=f"loadsel_{key}")
        show = cc[1].toggle("Show loads", value=True, key=f"loadtog_{key}")
        name = sel.split(": ", 1)[1]
        st.plotly_chart(figure_for_loads(model, name, show_loads=show),
                        width="stretch")
        st.caption("Red arrows are the applied loads (combination factors "
                   "included); hover an arrow for its magnitude. Toggle them "
                   "off to inspect the bare geometry.")
        # magnitudes of the loads DEFINED — load cases only (not combinations)
        if sel.startswith("Load case:") and name in model.load_cases:
            rows = _load_case_magnitude_rows(model.load_cases[name])
            if rows:
                st.markdown(f"**Defined load magnitudes — {name}**")
                st.dataframe(rows, width="stretch", hide_index=True)
            else:
                st.caption("This load case defines no loads.")


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
    # a pending jump (set by the run-summary dialog) is applied BEFORE the
    # radio is instantiated, so we never modify a live widget's state
    jump = ss.pop("vc_jump", None)
    if jump in _VC_TABS:
        ss["vc_tab"] = jump
    if ss.get("vc_tab") not in _VC_TABS:
        ss["vc_tab"] = _VC_TABS[0]
    active = st.radio("Section", _VC_TABS, key="vc_tab", horizontal=True,
                      label_visibility="collapsed")

    if active == _VC_TABS[0]:
        c = st.columns(2)
        c[0].pyplot(plot_model(model))
        c[1].pyplot(plot_frame_elevation(model, 0.0))
        st.caption(f"{len(model.nodes)} nodes · {len(model.members)} members "
                   f"· bracing first diagonal: {cfg.bracing_first_side}")
        _load_check_viewer(model, key="vc")

    if active == _VC_TABS[1]:
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
                res_mids = {mid for c in cases for mid in c.members}
                if res_mids and not res_mids <= set(model.members):
                    st.warning("⚠ The saved results are from a different "
                               "configuration (the geometry has changed since "
                               "the last run). Re-run the analysis to refresh "
                               "the results and report.")
                envs = build_envelopes(model, cases, checks)

                # member-failure counts per envelope / case, for the selector
                # labels and the "where are the failures" guidance below
                env_nf = {e.name: len(_failed_member_sets(
                    checks, {c.name for c in e.cases})[0]) for e in envs}
                case_nf = {c.name: len(_failed_member_sets(
                    checks, {c.name})[0]) for c in cases}

                def _opt(prefix, name, nf):
                    return f"{prefix}: {name}" + (f"  ⚠ {nf} failed" if nf
                                                  else "")

                opts = ([_opt("Envelope", e.name, env_nf[e.name])
                         for e in envs]
                        + [_opt("Case", c.name, case_nf[c.name])
                           for c in cases])
                with st.container(border=True):
                    ui.section("🧊", "Interactive model — coloured by "
                                     "utilisation")
                    cc = st.columns([3, 2])
                    sel = cc[0].selectbox("View envelope / case", opts,
                                          label_visibility="collapsed")
                    scale = cc[1].slider("Deformation scale ×", 0, 200, 30, 5)
                    # orthographic directional views (no perspective)
                    view = st.radio("Projection", VIEW_OPTIONS, horizontal=True,
                                    key="iview_proj",
                                    help="3D perspective, or an orthographic "
                                         "DA / CA elevation or top (plan) view.")

                    # resolve the selection (labels are index-aligned to opts)
                    idx = opts.index(sel)
                    if idx < len(envs):
                        env = envs[idx]
                        sel_case_names = {c.name for c in env.cases}
                    else:
                        env = None
                        case = cases[idx - len(envs)]
                        sel_case_names = {case.name}
                    failed, buckled = _failed_member_sets(checks,
                                                          sel_case_names)

                    fc = st.columns(2)
                    only_failed = fc[0].checkbox(
                        f"Show only failed members ({len(failed)})",
                        key="flt_failed", disabled=not failed)
                    only_buck = fc[1].checkbox(
                        f"Show only buckling failures ({len(buckled)})",
                        key="flt_buckling", disabled=not buckled)
                    show_only = (buckled if only_buck
                                 else failed if only_failed else None)

                    # if this view has no member failures, point to where they
                    # are (another envelope) or explain non-member failures
                    if not failed:
                        fail_views = [e.name for e in envs if env_nf[e.name]]
                        if fail_views:
                            st.info("No member failures in this view — switch "
                                    "to **" + "** / **".join(fail_views)
                                    + "** to isolate the failing members.")
                        else:
                            nonmem = sorted({c.check for c in checks
                                             if not c.informative
                                             and c.utilization > 1.0
                                             and not c.target.startswith(
                                                 "member")})
                            if nonmem:
                                st.info("No member-level failures. The failing "
                                        "checks are not on members: "
                                        + ", ".join(nonmem) + " — see the "
                                        "Report for storey drift / P-Δ / base "
                                        "details.")

                    if env is not None:
                        st.plotly_chart(
                            apply_view(figure_for_envelope(
                                model, env, scale=scale, show_only=show_only),
                                view),
                            width="stretch")
                        if env.governing:
                            st.markdown(
                                f"<span class='rnr-muted'>Governing: "
                                f"<b>{env.governing.check}</b> on "
                                f"{env.governing.target} = "
                                f"{env.governing.utilization:.3f}</span>",
                                unsafe_allow_html=True)
                    else:
                        st.plotly_chart(
                            apply_view(figure_for_case(
                                model, case, checks, scale=scale,
                                show_only=show_only), view),
                            width="stretch")
                        if not case.converged:
                            st.error("This case did NOT converge.")
                    cap = ("Hover a member for its forces, a ◆ support for its "
                           "reactions. Failed members are isolated against the "
                           "faint full wireframe."
                           if show_only is not None else
                           "Hover a member for its forces, a ◆ support for its "
                           "reactions.")
                    st.caption(cap)

                # ---- per-member ULS & SLS envelope summary -------------------
                with st.container(border=True):
                    ui.section("🔎", "Member envelope summary — ULS & SLS")
                    sets = sorted({mm.member_set
                                   for mm in model.members.values()})
                    fcol = st.columns([1.2, 2.4])
                    mset = fcol[0].selectbox("Member set", ["(all)"] + sets,
                                             key="mes_set")
                    mids = [mid for mid, mm in sorted(model.members.items())
                            if mset == "(all)" or mm.member_set == mset]
                    if mids:
                        msec = {mid: model.members[mid].section for mid in mids}

                        # top 10 members by utilisation (within the set filter)
                        _u = {mid: max((e.member_util.get(mid, 0.0)
                                        for e in envs), default=0.0)
                              for mid in mids}
                        top = sorted(_u.items(), key=lambda kv: -kv[1])[:10]
                        st.markdown("**Top 10 members by utilisation**")
                        st.dataframe(
                            [{"member": mid, "set": model.members[mid].member_set,
                              "section": msec[mid], "max util": round(u, 3),
                              "status": "FAIL" if u > 1.0 + 1e-9 else "ok"}
                             for mid, u in top],
                            width="stretch", hide_index=True)

                        def _mlbl(mid):
                            mm = model.members[mid]
                            u = max((e.member_util.get(mid, 0.0) for e in envs),
                                    default=0.0)
                            flag = "  ⚠" if u > 1.0 else ""
                            return (f"member {mid} · {mm.member_set} · "
                                    f"{msec[mid]} · util {u:.2f}{flag}")

                        mid_sel = fcol[1].selectbox("Member", mids,
                                                    format_func=_mlbl,
                                                    key="mes_member")
                        uls_env = next((e for e in envs if e.kind == "ULS"),
                                       None)
                        sls_env = next((e for e in envs if e.kind == "SLS"),
                                       None)
                        sec = model.sections.get(model.members[mid_sel].section)
                        if sec is not None:
                            st.caption(
                                f"Section **{sec.name}** (role "
                                f"{sec.role or '—'}): A_eff = "
                                f"{sec.area_eff:.0f} mm² · I_y = {sec.Iy:.3e} "
                                f"mm⁴ · I_z = {sec.Iz:.3e} mm⁴ · W_y,eff = "
                                f"{sec.mod_y_eff:.0f} mm³ · W_z,eff = "
                                f"{sec.mod_z_eff:.0f} mm³")
                        ec = st.columns(2)
                        ec[0].markdown("**ULS envelope**")
                        ec[0].markdown(member_envelope_summary_md(
                            uls_env, checks, mid_sel))
                        ec[1].markdown("**SLS envelope**")
                        ec[1].markdown(member_envelope_summary_md(
                            sls_env, checks, mid_sel))

                # ---- governing summary: per section + per load case ----------
                with st.container(border=True):
                    ui.section("🏆", "Governing summary — by section & by case")
                    st.markdown("**Maximum utilisation per section** "
                                "(governing member, stress / buckling / shear / "
                                "deflection)")
                    sec_rows = _section_governing_rows(model, checks)
                    if sec_rows:
                        st.dataframe(sec_rows, width="stretch", hide_index=True)
                    else:
                        st.caption("No member-level checks available.")
                    st.markdown("**Governing member per load case / combination**")
                    case_rows = _case_governing_rows(model, checks)
                    if case_rows:
                        st.dataframe(case_rows, width="stretch", hide_index=True)
                    from rack15512.checks.en15512 import (
                        upright_set_buckling_rows)
                    uset_rows = upright_set_buckling_rows(model, checks)
                    if uset_rows:
                        st.markdown(
                            "**Upright buckling by member-set** — each "
                            "continuous upright as storey segments (base→L1, "
                            "L1→L2, …); the set length is Lcr in the down-aisle "
                            "direction; the governing element represents the set")
                        st.dataframe(
                            [{"set": r["set"], "Lcr,DA (mm)": r["Lcr_DA_mm"],
                              "Lcr,CA (mm)": r["Lcr_CA_mm"],
                              "N (kN)": r["N_kN"], "My (kNm)": r["My_kNm"],
                              "Mz (kNm)": r["Mz_kNm"],
                              "gov elem": f"member {r['member']}",
                              "util": r["util"], "case": r["case"],
                              "status": r["status"]}
                             for r in uset_rows],
                            width="stretch", hide_index=True)
                    from rack15512.checks.en15512 import (
                        suggest_splice_positions)
                    sug = suggest_splice_positions(model, cases)
                    if sug["n_needed"] > 0 and sug["candidates"]:
                        st.markdown(
                            f"**Suggested upright splice positions** — frame "
                            f"{sug['H']:.0f} mm needs ≥ {sug['n_needed']} splice"
                            f"(s) for a {sug['max_length']:.0f} mm max length; "
                            "place just above a beam level near low down-aisle "
                            "moment (EN 1993-1-8 §6.2.7.1)")
                        st.dataframe(
                            [{"elevation (mm)": c["z"], "Mz (kNm)": c["Mz_kNm"],
                              "suggest": "✓" if c["recommended"] else "",
                              "note": c["note"]}
                             for c in sug["candidates"]],
                            width="stretch", hide_index=True)
                    elif sug["candidates"]:
                        st.caption(
                            f"No upright splice required — frame {sug['H']:.0f} "
                            f"mm ≤ {sug['max_length']:.0f} mm max length.")
                    sway = sorted(
                        ({"case": c.case, "axis": c.target,
                          "util": round(c.utilization, 3), "detail": c.detail}
                         for c in checks if c.check == "SWAY"),
                        key=lambda r: -r["util"])
                    if sway:
                        st.markdown("**Frame sway** (H / limit)")
                        st.dataframe(sway[:10], width="stretch", hide_index=True)
            else:
                st.info("Re-run to enable the interactive viewer / envelopes.")
            with st.container(border=True):
                ui.section("📊", "Maximum utilisation by check")
                st.dataframe([rs.get("max_utilization_by_check", {})],
                             width="stretch")
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
        def _on_run_done(summary):
            ui.toast_verdict(summary["verdict"])
            _run_summary_dialog(summary, target=(proj.id, sysm.id, conf.id))

        if not _run_or_poll(cdir, "OpenSees second-order analysis",
                            on_done=_on_run_done):
            rc = st.columns(3)
            if rc[0].button("▶ Run / re-run analysis", type="primary",
                            width="stretch"):
                ui.log(f"Run invoked: {proj.name} · {sysm.name} · {conf.name}")
                background_run.start_run(
                    PSTORE.root, "masters", proj.id, sysm.id, conf.id,
                    label="OpenSees second-order analysis")
                st.rerun()
            if rc[1].button("🌐 Seismic design (IS 1893)",
                            width="stretch"):
                goto("seismic_study", project_id=proj.id, system_id=sysm.id,
                     config_id=conf.id)
            if rc[2].button("🔩 Anchor & footplate designer",
                            width="stretch",
                            disabled=not _load_results(cdir),
                            help="Design the anchor + footplate against the "
                                 "governing ULS / seismic base reactions "
                                 "(after a run)."):
                goto("anchor_designer", project_id=proj.id, system_id=sysm.id,
                     config_id=conf.id)

    if active == _VC_TABS[2]:
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
                             width="stretch"):
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
                                width="stretch", type="primary",
                                key=f"dl_{fname}")
                    else:
                        st.button(f"Download {label}", disabled=True,
                                  width="stretch", key=f"dlx_{fname}")
        if not any_file:
            if res:
                st.info("Press *Generate / refresh report files* above.")
            else:
                st.info("Run the configuration to generate the report.")
        rp = os.path.join(cdir, "report.md")
        if os.path.exists(rp):
            with st.expander("Preview check report (text)"):
                st.markdown(open(rp, encoding="utf-8").read())

        st.markdown("#### Solver export — re-run this model in RSTAB / STAAD "
                    "/ SAP2000")
        st.caption("RSTAB 8 table workbook (File → Import → Microsoft Excel): "
                   "nodes, materials and cross-sections with RSTAB library "
                   "names, member hinges, supports with the axial-dependent "
                   "base stiffness diagram, sets of members, load cases + "
                   "sway-imperfection cases, all loads and the generated "
                   "load combinations. The STAAD .std deck declares its own "
                   "units (mm, N). The SAP2000 workbook (File → Import → "
                   "SAP2000 MS Excel Spreadsheet .xlsx) writes the CSi "
                   "database tables — joints, frames + section assignments, "
                   "section properties (our Iz→I33, Iy→I22), materials, "
                   "member releases + partial-fixity connector springs, "
                   "restraints, loads and combinations.")
        uref = st.file_uploader(
            "Match units to your RSTAB (optional): drop ANY Excel export "
            "made by your RSTAB — the workbook adopts its unit settings "
            "automatically. Without it, the company default RSTAB units "
            "are used (mm, kN/cm², cm⁴, kNcm/rad, kN, line loads kN/cm).",
            type=["xlsx"], key="rstab_units_ref")
        ec = st.columns(2)
        if ec[0].button("⚙ Generate RSTAB 8 / STAAD export",
                        width="stretch", key="gen_solver_exp"):
            from rack15512.export_solvers import (rstab_units_from_export,
                                                  to_rstab8_xlsx, to_staad)
            units = None
            if uref is not None:
                ref_path = os.path.join(cdir, "_units_ref.xlsx")
                with open(ref_path, "wb") as f:
                    f.write(uref.getbuffer())
                try:
                    units = rstab_units_from_export(ref_path)
                    st.info("Units matched to the uploaded RSTAB export: "
                            + ", ".join(f"{k} {v}"
                                        for k, v in sorted(units.items())))
                except ValueError as exc:
                    st.error(f"{exc} — exporting in RSTAB factory units.")
            to_rstab8_xlsx(model, os.path.join(cdir, "RSTAB8_export.xlsx"),
                           units=units)
            to_staad(model, os.path.join(cdir, "STAAD_export.std"))
            from rack15512.sap2000 import to_sap2000
            to_sap2000(model, os.path.join(cdir, "SAP2000_export.xlsx"))
            st.rerun()
        for fname, mime in (("RSTAB8_export.xlsx",
                             "application/vnd.openxmlformats-officedocument"
                             ".spreadsheetml.sheet"),
                            ("SAP2000_export.xlsx",
                             "application/vnd.openxmlformats-officedocument"
                             ".spreadsheetml.sheet"),
                            ("STAAD_export.std", "text/plain")):
            fp = os.path.join(cdir, fname)
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    ec[1].download_button(
                        f"Download {fname}", f.read(),
                        f"{conf.id}_{fname}", mime=mime,
                        width="stretch", key=f"dl_{fname}")

        rp = os.path.join(cdir, "RSTAB8_export.xlsx")
        if os.path.exists(rp):
            with st.expander("✅ Verify the RSTAB export is an exact replica "
                             "of the OpenSees model"):
                st.caption("Reads the generated workbook back and checks node "
                           "coordinates, member geometry, section mapping, "
                           "hinge stiffnesses, supports, sets of members, load "
                           "cases and combinations against the analysis model. "
                           "Node numbering, Z-down orientation, the two native "
                           "imperfection load cases and the per-direction "
                           "combination expansion are RSTAB conventions, so "
                           "the check compares by coordinate/geometry, not id.")
                from rack15512.rfem_compare import verify_rstab_export
                try:
                    checks = verify_rstab_export(model, rp)
                    st.dataframe(checks, width="stretch", hide_index=True)
                    if all(c["status"] == "ok" for c in checks):
                        st.success("Exact replica — every item matches.")
                    else:
                        st.warning("Some items differ — see the `review` rows.")
                except Exception as exc:
                    st.warning(f"Verification unavailable: {exc}")

        _rstab_results_compare(model, res, cdir, conf)
        _sap2000_import_panel(cdir, conf)

    if active == _VC_TABS[3]:
        ui.section("⚙️", "Configuration — edit the inputs and re-run")
        st.caption("Change any input below, then *Update & re-run*. Use this "
                   "to iterate when a check fails (e.g. heavier upright, "
                   "tighter bracing, lower pallet load).")
        cfg_edit = configuration_form(lib, master, cfg)
        notes = st.text_input("Notes", conf.notes or "", key="param_notes")
        for lvl, msg in _config_warnings(cfg_edit, lib):
            (st.error if lvl == "error" else st.warning)(msg)
        def _on_update_run_done(summary):
            ui.toast_verdict(summary["verdict"])
            _run_summary_dialog(summary, target=(proj.id, sysm.id, conf.id))

        if not _run_or_poll(cdir, "OpenSees second-order analysis",
                            on_done=_on_update_run_done):
            pc = st.columns(2)
            if pc[0].button("💾 Update configuration", width="stretch",
                            key="param_save"):
                if _save_config(proj.id, sysm.id, cfg_edit, conf.master_id,
                                notes):
                    st.rerun()
            if pc[1].button("💾▶ Update & re-run analysis", type="primary",
                            width="stretch", key="param_run"):
                if _save_config(proj.id, sysm.id, cfg_edit, conf.master_id,
                                notes, silent=True):
                    ui.log(f"Re-run invoked: {conf.name}")
                    background_run.start_run(
                        PSTORE.root, "masters", proj.id, sysm.id, conf.id,
                        label="OpenSees second-order analysis")
                    st.rerun()
        with st.expander("Raw configuration JSON"):
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

    from rack15512.cf_sections import STD_1C
    lib, master, master_id = resolve_master(conf.master_id, conf.master_path)
    cfg0 = rackconfig_from_dict(conf.config, master=master)
    blevels = _beam_levels(cfg0)
    _libbr = [n for n in (lib.names("bracing") or lib.names())
              if n not in STD_1C]
    # spine: full 1C family; plan: the 1C60x40-1C80x40 family (heavier)
    spine_opts = ["(frame brace)"] + STD_1C + _libbr
    plan_opts = [n for n in STD_1C if "60x40" in n or "80x40" in n] + _libbr
    ca_opts = [f"(keep: {cfg0.brace_section})"] + STD_1C + _libbr

    ui.section("📋", "Seismic parameters (IS 1893:2016)")
    seis_on = st.toggle(
        "Run seismic analysis (IS 1893 modal RSA)",
        value=bool(cfg0.seismic) if cfg0.seismic else True,
        help="Off = standard EN 15512 (non-seismic) run — plan / spine bracing "
             "not required. On = modal RSA; spine and plan bracing are still "
             "optional (you can run seismic on the bare frame).")
    if not seis_on:
        st.info("Seismic is **OFF** — this runs a standard EN 15512 "
                "(non-seismic) analysis. Plan / spine bracing are not required; "
                "any bracing you set below is still built but optional.")
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

    # ---- drift / P-Delta limits (rack-specific, EN 1998-1 / EN 16681) -------
    DRIFT_OPTS = {
        "EN 1998-1 §4.4.3.2 / EN 16681 — racks, no brittle attachments "
        "(0.010 h)": 0.010,
        "EN 1998-1 — ductile non-structural (0.0075 h)": 0.0075,
        "EN 1998-1 — brittle non-structural (0.005 h)": 0.005,
        "IS 1893 Cl 7.11.1 — buildings (0.004 h)": 0.004,
    }
    cur = next((k for k, v in DRIFT_OPTS.items()
                if abs(v - float(cfg0.seismic_drift_limit)) < 1e-6),
               list(DRIFT_OPTS)[0])
    c = st.columns([3, 1])
    drift_lbl = c[0].selectbox("Storey-drift limit Δ/h", list(DRIFT_OPTS),
                               index=list(DRIFT_OPTS).index(cur))
    s_drift = DRIFT_OPTS[drift_lbl]
    s_theta = c[1].number_input("P-Δ θ cap", 0.10, 0.30,
                                float(cfg0.seismic_theta_max), 0.05,
                                help="EN 1998-1 §4.4.2.2: θ>0.30 not permitted "
                                     "(racks). θ≤0.10 negligible.")
    s_scale = st.checkbox(
        "Scale RSA up to the empirical-period base shear (IS 1893 Cl 7.7.3)",
        value=bool(getattr(cfg0, "seismic_scale_base_shear", True)),
        help="On = code-compliant (pins base shear to V_static at the "
             "empirical Ta, which for short racks sits on the Sa/g=2.5 "
             "plateau). Off = use the lower modal-period base shear directly "
             "(realises the long-period saving; departs from the strict "
             "clause — engineer's call).")
    # rack-suitability validation against EN 16681 (only relevant when seismic)
    notes = []
    if seis_on and s_R > 4.0:
        notes.append(f"R = {s_R:g} is high for a rack: EN 16681 behaviour "
                     "factors are typically q ≈ 1.5–2 (down-aisle moment "
                     "frame) and 2–4 (braced). Use a lower R unless justified.")
    if seis_on and s_drift <= 0.004:
        notes.append("0.004 h is the IS building limit; racks without brittle "
                     "attachments may use up to 0.010 h (EN 16681).")
    if seis_on and s_I < 1.0:
        notes.append("Importance I < 1.0 is unusual; use ≥ 1.0.")
    for nt in notes:
        st.warning("⚠ " + nt)

    ui.section("◫", "Bracing specification (truss members) — optional, "
                    "runs exactly this")
    c = st.columns(3)
    da_on = c[0].checkbox("Spine X bracing (down-aisle)",
                          bool(cfg0.spine_bracing))
    da_sec = c[1].selectbox("Spine section (1C family)", spine_opts,
                            index=_idx(spine_opts, cfg0.spine_bracing_section
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
    st.markdown("**Cross-aisle (CA) frame bracing** — overrides the whole frame")
    c = st.columns(3)
    Hmax = float(cfg0.frame_height or (blevels[-1] if blevels else 3000.0))
    ca_h = c[0].number_input("CA X up to height [mm] (0 = none)", 0.0, Hmax,
                             float(cfg0.ca_x_height or 0.0), 50.0)
    ca_sec = c[1].selectbox("CA bracing section (overrides full frame)",
                            ca_opts, index=0)
    ca_planes = c[2].number_input("Brace shear planes", 1, 2,
                                  int(getattr(cfg0, "brace_planes", 1)),
                                  help="1 = single C, 2 = double / back-to-back "
                                       "C (affects bolt-shear / bearing).")
    st.caption("Changing the CA section replaces the cross-aisle diagonal "
               "member for the whole frame (not added on top).")
    c = st.columns(3)
    pl_on = c[0].checkbox("Plan bracing (in spine modules)",
                          bool(cfg0.plan_bracing))
    pl_sec = c[1].selectbox("Plan section (1C 60x40–80x40)", plan_opts,
                            index=_idx(plan_opts, cfg0.plan_bracing_section
                                       or plan_opts[0]))
    # current level mode from the saved config
    _alt = blevels[::2]
    _cur = cfg0.plan_bracing_levels
    if _cur and len(_cur) == len(blevels):
        _mode0 = "All levels"
    elif not _cur or {round(z) for z in _cur} == {round(z) for z in _alt}:
        _mode0 = "Alternate levels"
    else:
        _mode0 = "Specific levels"
    pl_mode = c[2].selectbox("Plan bracing levels",
                             ["All levels", "Alternate levels",
                              "Specific levels"],
                             index=["All levels", "Alternate levels",
                                    "Specific levels"].index(_mode0))
    if pl_mode == "Specific levels":
        pl_levels = st.multiselect(
            "Select beam levels", blevels,
            default=(_cur or _alt), format_func=lambda z: f"{z:.0f} mm")
    elif pl_mode == "Alternate levels":
        pl_levels = _alt
    else:                                       # All levels
        pl_levels = list(blevels)
    spacer_opts = list(dict.fromkeys(
        ["(frame brace)"] + list(lib.names("bracing") or [])
        + list(lib.names("beam") or lib.names())))
    _sp_def = cfg0.spacer_section or "(frame brace)"
    sp_sec = st.selectbox(
        "Frame / row spacer section (bracing or beam; simply-supported truss tie)",
        spacer_opts, index=_idx(spacer_opts, _sp_def))

    ca_brace = cfg0.brace_section if ca_sec.startswith("(keep") else ca_sec
    cfg = dataclasses.replace(
        cfg0, seismic=seis_on, seismic_zone=zone, seismic_soil=soil,
        seismic_importance=s_I, seismic_response_reduction=s_R,
        seismic_damping=s_damp, seismic_drift_limit=s_drift,
        seismic_theta_max=s_theta, seismic_scale_base_shear=s_scale,
        brace_section=ca_brace, brace_planes=int(ca_planes),
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
    cc2 = st.columns(2)
    cc2[0].pyplot(plot_side_elevation(model))     # side (cross-aisle) view
    cc2[1].pyplot(plot_plan(model))               # top view
    st.caption(f"{len(model.nodes)} nodes · {len(model.members)} members · "
               f"spine {_n('spine bracing')} (truss) · frame spacers "
               f"{_n('frame spacer')} (beam) · plan {_n('plan bracing')} (truss)")

    run_lbl = ("▶ Run seismic analysis (this specification)" if seis_on
               else "▶ Run standard (non-seismic) analysis")
    if st.button(run_lbl, type="primary", width="stretch"):
        cfg_save = RackConfig(**{k: v for k, v in cfg.__dict__.items()
                                 if k not in ("library", "master")})
        cfg_save.levels = cfg.levels
        PSTORE.update_configuration(proj.id, sysm.id, conf.id, conf.name,
                                    cfg_save, master_id=master_id,
                                    notes=conf.notes or "")
        ui.log(f"Seismic run invoked (zone {zone}): {conf.name}")
        background_run.start_run(
            PSTORE.root, "masters", proj.id, sysm.id, conf.id,
            label="Seismic + EN 15512 analysis")
        # land on the Results tab, which picks up and shows the run's live
        # progress - it survives navigating away from here (separate process)
        ss["vc_jump"] = _VC_TABS[1]
        goto("view_config", project_id=proj.id, system_id=sysm.id,
             config_id=conf.id)


# ------------------------------------------------ anchor & footplate designer
def render_anchor_designer():
    import math
    from rack15512.checks.en15512 import (_anchor_capacities, _anchorage_checks,
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

    ui.section("📐", "Footplate / anchor layout (check the input dimensions)")
    up_sec = next((model.section_of(m) for m in model.members.values()
                   if m.member_set == "uprights"), None)
    try:
        st.pyplot(plot_footplate(bp, up_sec))
    except Exception as e:
        st.caption(f"(diagram unavailable: {e})")

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

    # Profis-style per-anchor breakdown for the governing anchorage case
    cap = _anchor_capacities(bp)
    if worst_an and cap:
        gov_case = next((c for c in uls + seis if c.name == worst_an.case),
                        None)
        try:
            node_id = int(worst_an.target.split()[1])
        except (ValueError, IndexError):
            node_id = None
        if gov_case and node_id in (gov_case.reactions if gov_case else {}):
            r = gov_case.reactions[node_id]
            n = max(int(bp.n_anchors), 1)
            s_lever = cap["s"]
            uplift = max(-r[2], 0.0)
            M = math.hypot(r[3], r[4])
            V = math.hypot(r[0], r[1])
            n_ed = uplift / n + (M / s_lever if s_lever > 0 else 0.0)
            v_ed = V / n
            bN = n_ed / cap["n_rd"] if cap["n_rd"] else 99.0
            bV = v_ed / cap["v_rd"] if cap["v_rd"] else 99.0
            comb = (min(bN, 1.0) ** 1.5 + min(bV, 1.0) ** 1.5
                    if bN <= 1 and bV <= 1 else bN ** 1.5 + bV ** 1.5)
            ui.section("📊", f"Per-anchor design — governing {worst_an.case} "
                             f"({worst_an.target}), {n}×M{bp.anchor_d:.0f} "
                             f"{bp.anchor_grade}")
            st.caption(f"Per anchor: N_Ed = uplift/n + M/lever = "
                       f"{n_ed/1e3:.2f} kN · V_Ed = V/n = {v_ed/1e3:.2f} kN "
                       f"(lever s = {s_lever:.0f} mm)")

            def _row(ls, dem, capk):
                return {"limit state": ls, "demand [kN]": round(dem / 1e3, 2),
                        "capacity [kN]": round(capk / 1e3, 2),
                        "utilisation": round(dem / capk, 2) if capk else None}
            rows = [
                _row("Tension — steel (A_s·f_uk/γMs)", n_ed, cap["n_rd_s"]),
                _row("Tension — pull-out (N_Rk,p/γMc)", n_ed, cap["n_rd_p"]),
                _row("Tension — concrete cone (N_Rk,c/γMc)", n_ed, cap["n_rd_c"]),
                _row("Shear — steel (0.5·A_s·f_uk/γMs)", v_ed, cap["v_rd_s"]),
                _row("Shear — concrete (V_Rk,c/γMc)", v_ed, cap["v_rd_c"]),
                {"limit state": "Combined (βN^1.5+βV^1.5 ≤ 1)",
                 "demand [kN]": None, "capacity [kN]": 1.0,
                 "utilisation": round(comb, 2)},
            ]
            st.dataframe(rows, width="stretch")
            st.caption("Tension governed by "
                       + ("steel" if cap["n_rd"] == cap["n_rd_s"]
                          else "pull-out" if cap["n_rd"] == cap["n_rd_p"]
                          else "concrete cone")
                       + f" ({cap['n_rd']/1e3:.1f} kN); shear by "
                       + ("steel" if cap["v_rd"] == cap["v_rd_s"]
                          else "concrete")
                       + f" ({cap['v_rd']/1e3:.1f} kN).")

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
    preview = c[0].button("👁 Preview model", width="stretch")
    save_label = ("💾 Update configuration" if ss.config_id
                  else "💾 Save configuration")
    save = c[1].button(save_label, width="stretch")
    run = c[2].button("💾▶ Save & run", type="primary", width="stretch")

    if preview:
        st.session_state["_preview"] = True
    # the preview persists across parameter edits (it is rebuilt from the live
    # config each rerun), so it stays visible while you keep editing
    if st.session_state.get("_preview"):
        with st.container(border=True):
            hc = st.columns([6, 1])
            hc[0].markdown("**Model preview** (updates as you edit)")
            if hc[1].button("✕ Hide preview", key="hide_preview"):
                st.session_state["_preview"] = False
                st.rerun()
            try:
                model = build_rack(cfg)
                cc = st.columns(2)
                cc[0].pyplot(plot_model(model))
                cc[1].pyplot(plot_frame_elevation(model, 0.0))
                st.caption(f"{len(model.nodes)} nodes · {len(model.members)} "
                           f"members · first diagonal: {cfg.bracing_first_side}")
            except (ValueError, KeyError) as e:
                st.error(str(e))

    if save:
        conf = _save_config(proj.id, sysm.id, cfg, master_id, notes)
        if conf:
            ss.config_id = conf.id        # subsequent saves update this one
    if run:
        conf = _save_config(proj.id, sysm.id, cfg, master_id, notes,
                            silent=True)
        if conf:
            ss.config_id = conf.id
            ui.log(f"Save & run invoked: {conf.name}")
            background_run.start_run(
                PSTORE.root, "masters", proj.id, sysm.id, conf.id,
                label="OpenSees second-order analysis")
            # land on the Results tab, which picks up and shows the run's
            # live progress - it survives navigating away from here
            ss["vc_jump"] = _VC_TABS[1]
            goto("view_config", project_id=proj.id, system_id=sysm.id,
                 config_id=conf.id)


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
    ui.hero("Section Masters", "Masters are grouped by company — sections are "
            "company-specific. Add a company, then import its masters.",
            eyebrow="Section library")

    # ---- company master (registry of company names) ----------------------
    companies = MSTORE.companies()
    with st.expander("🏢  Company master", expanded=not companies):
        cc = st.columns([3, 1])
        new_co = cc[0].text_input("Add company name", key="new_company")
        if cc[1].button("Add company") and new_co.strip():
            MSTORE.add_company(new_co)
            st.success(f"Added company '{new_co.strip()}'.")
            st.rerun()
        if companies:
            st.caption("Registered companies: " + ", ".join(companies))
            dc = st.columns([3, 1])
            drop = dc[0].selectbox("Remove company (keeps its masters)",
                                   companies, key="del_company")
            if dc[1].button("Remove") and drop:
                MSTORE.delete_company(drop)
                st.rerun()

    # ---- import a master (company mandatory) -----------------------------
    st.subheader("Import a master")
    from rack15512.master_template import template_bytes
    st.download_button(
        "⬇ Download the consolidated template (all sections + base & beam "
        "stiffness)", data=template_bytes(), file_name="Master_Template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="One workbook: SECTIONS (uprights/beams/bracings/others), "
             "BASE_STIFFNESS and BEAM_STIFFNESS. Fill it and import it here.")
    up = st.file_uploader("Master file (.xlsx / .csv / .json)",
                          type=["xlsx", "xlsm", "csv", "json"])
    ic = st.columns(2)
    nm = ic[0].text_input("Store as", up.name if up else "")
    # company is mandatory: pick a registered one (or add via the company master)
    co_opts = companies or []
    company = ic[1].selectbox("Company (required)",
                              ["— select —"] + co_opts, key="imp_company")
    if up and st.button("Import"):
        if company == "— select —":
            st.error("Select a company first (add one in the Company master "
                     "above). The company name is mandatory.")
        else:
            suffix = os.path.splitext(up.name)[1] or ".xlsx"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(up.getvalue())
            tmp.close()
            m = MSTORE.import_xlsx(tmp.name, name=nm or up.name, company=company)
            st.success(f"Imported '{m.id}' ({len(m.sections)} sections) for "
                       f"'{company}'.")
            st.rerun()

    grouped = MSTORE.by_company()
    if not grouped:
        st.info("No masters yet — add a company and import its masters above.")
    for company in sorted(grouped, key=lambda c: (c == "", c.lower())):
        st.markdown(f"### 🏢 {company or '(no company)'}")
        for sm in grouped[company]:
            _render_master(sm)


def _render_master(sm):
    with st.expander(f"{sm.name}  ({sm.id}) — {len(sm.sections)} sections"):
            cc = st.columns([4, 1])
            cc[0].caption(f"roles: {', '.join(sm.roles())} · base tables: "
                          f"{len(sm.base_tables)} · updated {sm.updated}")
            if cc[1].button("🗑 Delete master", key=f"dm_{sm.id}"):
                MSTORE.delete(sm.id)
                st.rerun()

            # merge supplementary data into this master, matched by section
            # name: a geometry sheet (Section / Thickness / depth / edges) sets
            # the thickness & edge distances; a beam-connector sheet
            # (Section / M_Rd / Kb @ UPL ...) sets the connector stiffness; a
            # BASE_STIFFNESS sheet adds upright base tables.
            stf = st.file_uploader(
                "Merge section data (thickness / connector Kb / base stiffness)",
                type=["xlsx", "xlsm"], key=f"stf_{sm.id}")
            if stf and st.button("Merge data", key=f"mstf_{sm.id}"):
                t = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
                t.write(stf.getvalue())
                t.close()
                try:
                    nb, nbt = MSTORE.merge_stiffness(sm.id, t.name)
                    st.success(f"Updated {nb} beam connector(s); added {nbt} "
                               f"base-stiffness table(s).")
                    if nb == 0 and nbt == 0:
                        st.warning("No sections matched by name — check the "
                                   "section names in the sheet.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Merge failed: {e}")

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
                    st.dataframe(data, width="stretch")
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

            # show every role present in the master (upright / beam / bracing /
            # others — rails, connectors, shuttle parts, ...)
            _roles = sm.roles() or ["upright", "beam", "bracing"]
            role = st.selectbox("Role", _roles, key=f"r_{sm.id}")
            names = sm.names(role)
            if names:
                # full property spectrum (mm/N units); blank cells = not set
                _cols = ["A", "A_eff", "Iy", "Iz", "J", "Wely", "Welz",
                         "Avy", "Avz", "It_gross", "Iw_gross", "y0",
                         "depth_h", "width_b", "t",
                         "buckling_curve_y", "buckling_curve_z", "connector_k"]
                rows = []
                for n in names:
                    d = sm.sections[n]
                    row = {"name": n, "fy": sm.fy.get(n)}
                    row.update({c: d.get(c) for c in _cols})
                    rows.append(row)
                st.dataframe(rows, width="stretch")
                st.caption("Units: mm, mm² (A), mm⁴ (I, J/It), mm³ (W), mm⁶ "
                           "(Iw), MPa (fy), N·mm/rad (connector_k). Scroll the "
                           "table sideways to see every column.")
                e = st.columns([2, 1.5, 1.5, 1])
                edit = e[0].selectbox("Section", names, key=f"s_{sm.id}")
                fld = e[1].selectbox(
                    "Field",
                    ["A", "A_eff", "Iy", "Iz", "J", "Wely", "Welz", "fy",
                     "Avy", "Avz", "It_gross", "Iw_gross", "y0",
                     "depth_h", "width_b", "t", "e1", "e2", "connector_k"],
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

            # ---- CUFSM import: update an upright from a CUFSM run -----------
            ups = sm.names("upright")
            if ups:
                st.divider()
                st.markdown("**CUFSM import** — update an upright's section "
                            "properties (J, Cw, y0) and buckling data "
                            "(Pcrl/Pcrd → A_eff + DSM) from a CUFSM output, and "
                            "store it in this master.")
                from rack15512 import cufsm as _cufsm
                ci = st.columns([2, 1])
                ctarget = ci[0].selectbox("Upright section", ups,
                                          key=f"cufup_{sm.id}")
                _sd = sm.sections[ctarget]
                canet = ci[1].number_input(
                    "A_net [mm²] (perforations)",
                    value=float(_sd.get("A_eff") or _sd.get("A") or 0.0),
                    key=f"cufanet_{sm.id}",
                    help="Net cross-section through a perforation; defaults to "
                         "the current A_eff / A.")
                cf = st.columns(2)
                cmodel = cf[0].file_uploader(
                    "CUFSM model (nodes + elements) → J, Cw, y0",
                    type=["txt", "csv", "dat"], key=f"cufmdl_{sm.id}")
                csig = cf[1].file_uploader(
                    "CUFSM signature curve → Pcrl, Pcrd",
                    type=["csv", "txt"], key=f"cufsig_{sm.id}")
                cref = st.number_input(
                    "signature reference × (1.0 if the curve is in load units)",
                    value=1.0, key=f"cufref_{sm.id}")
                if st.button("Import CUFSM & update master",
                             key=f"cufgo_{sm.id}",
                             disabled=not (cmodel or csig), type="primary"):
                    model_path = sig_path = None
                    try:
                        if cmodel is not None:
                            tf = tempfile.NamedTemporaryFile(suffix=".txt",
                                                             delete=False)
                            tf.write(cmodel.getvalue())
                            tf.close()
                            model_path = tf.name
                        if csig is not None:
                            sf = tempfile.NamedTemporaryFile(suffix=".csv",
                                                             delete=False)
                            sf.write(csig.getvalue())
                            sf.close()
                            sig_path = sf.name
                        data = _cufsm.CufsmData(
                            model=model_path, signature=sig_path,
                            reference=float(cref),
                            Anet=float(canet) or None)
                        report = sm.apply_cufsm(ctarget, data, overwrite=True)
                        MSTORE.save(sm)
                        st.success(f"Updated '{ctarget}' and saved the master.")
                        upd = sm.sections[ctarget]
                        dsm = upd.get("dsm") or {}
                        st.write({
                            "It_gross (J)": upd.get("It_gross"),
                            "Iw_gross (Cw)": upd.get("Iw_gross"),
                            "y0": upd.get("y0"),
                            "A_eff": upd.get("A_eff"),
                            "Pcrl": dsm.get("Pcrl"),
                            "Pcrd": dsm.get("Pcrd")})
                        if report is not None:
                            st.caption("CUFSM vs the master values before "
                                       "the import:")
                            st.markdown(_cufsm.validation_markdown(report))
                    except Exception as e:
                        st.error(f"CUFSM import failed: {e}")
                    finally:
                        for _p in (model_path, sig_path):
                            if _p and os.path.exists(_p):
                                os.remove(_p)


def render_user_access():
    """Admin-only: who can sign in, and with which role.  A non-admin can
    never reach this view (see the _ADMIN_ONLY_VIEWS guard in the router)."""
    ui.hero("User Access", "Admins can manage section masters and user "
            "access; everyone else only sees the projects dashboard.",
            eyebrow="Admin")

    users = USTORE.list_users()
    ui.stat_strip([("Users", len(users)),
                   ("Admins", sum(u.is_admin for u in users))])

    st.subheader("Add a user")
    with st.form("add_user_form", clear_on_submit=True):
        cc = st.columns([2, 2, 2, 1.4])
        new_username = cc[0].text_input("Username")
        new_name = cc[1].text_input("Full name")
        new_password = cc[2].text_input("Temporary password", type="password")
        new_role = cc[3].selectbox("Role", ["user", "admin"])
        if st.form_submit_button("➕ Add user", type="primary"):
            if not new_username.strip() or not new_password:
                st.error("Username and a temporary password are required.")
            elif USTORE.exists(new_username):
                st.error(f"'{new_username.strip().lower()}' already exists.")
            else:
                USTORE.add_user(new_username, new_name, new_password, new_role)
                st.success(f"Added '{new_username.strip().lower()}' "
                           f"({new_role}). Share the temporary password with "
                           f"them directly — it is not stored or shown again.")
                st.rerun()

    st.subheader("Existing users")
    me = ss.user["username"]
    last_admin = USTORE.admin_count() <= 1
    for u in users:
        with st.container(border=True):
            cc = st.columns([3, 2, 2, 2, 1.6])
            cc[0].markdown(f"**{u.name}**  \n"
                           f"<span class='rnr-muted'>@{u.username}"
                           f"{' · you' if u.username == me else ''}</span>",
                           unsafe_allow_html=True)
            cc[1].markdown(ui.role_badge(u.is_admin), unsafe_allow_html=True)
            # role toggle - never let the last admin demote themselves out
            can_demote = not (u.is_admin and last_admin)
            new_r = cc[2].selectbox(
                "Role", ["user", "admin"], index=0 if u.role == "user" else 1,
                key=f"role_{u.username}", label_visibility="collapsed",
                disabled=not can_demote)
            if new_r != u.role:
                if can_demote:
                    USTORE.set_role(u.username, new_r)
                    st.rerun()
                else:
                    cc[2].caption("⚠️ at least one admin is required")
            new_pw = cc[3].text_input("Reset password", key=f"pw_{u.username}",
                                      label_visibility="collapsed",
                                      placeholder="new password…")
            if cc[3].button("🔑 Reset", key=f"rpw_{u.username}",
                            width="stretch"):
                if new_pw:
                    USTORE.reset_password(u.username, new_pw)
                    st.success(f"Password reset for @{u.username}.")
                else:
                    st.error("Enter a new password first.")
            can_delete = u.username != me and not (u.is_admin and last_admin)
            if cc[4].button("🗑 Delete", key=f"del_{u.username}",
                            width="stretch", disabled=not can_delete):
                ss[f"confirm_deluser_{u.username}"] = True
            if u.username == me:
                cc[4].caption("can't delete yourself")
            elif u.is_admin and last_admin:
                cc[4].caption("last admin")
            if ss.get(f"confirm_deluser_{u.username}"):
                st.warning(f"Remove @{u.username}'s access? They will no "
                           f"longer be able to sign in.")
                wc = st.columns(2)
                if wc[0].button("Yes, remove access",
                                key=f"delu_y_{u.username}", type="primary"):
                    USTORE.delete_user(u.username)
                    ss[f"confirm_deluser_{u.username}"] = False
                    st.rerun()
                if wc[1].button("Cancel", key=f"delu_n_{u.username}"):
                    ss[f"confirm_deluser_{u.username}"] = False
                    st.rerun()


# ------------------------------------------------------------------- router
is_admin = ss.user.get("role") == "admin"

with st.sidebar:
    if os.path.exists(B.LOGO_PATH):
        st.image(B.LOGO_PATH, width="stretch")
    st.markdown(f"<div style='font-weight:800;font-size:1.02rem;margin-top:2px'>"
                f"{B.PRODUCT}</div>"
                f"<div class='rnr-muted' style='font-size:.8rem'>{B.TAGLINE}"
                f"</div>", unsafe_allow_html=True)
    st.divider()
    if st.button("🏠  Dashboard", width="stretch"):
        goto("dashboard")
    if is_admin:
        if st.button("📚  Section masters", width="stretch"):
            goto("masters")
        if st.button("👤  User access", width="stretch"):
            goto("user_access")
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
    role_badge = "Admin" if is_admin else "User"
    st.markdown(f"<div style='font-weight:700'>{ss.user.get('name') or ss.user['username']}"
                f"</div><div class='rnr-muted' style='font-size:.8rem'>"
                f"{role_badge} · @{ss.user['username']}</div>",
                unsafe_allow_html=True)
    if st.button("🚪  Log out", width="stretch"):
        ss.user = None
        ss.view = "dashboard"
        for k in ("project_id", "system_id", "config_id", "edit_cfg"):
            ss[k] = None
        st.rerun()
    st.divider()
    st.caption("OpenSees 2nd-order · semi-rigid")
    st.caption("Units: N, mm, MPa")
    st.caption(f"© {B.COMPANY} · {B.WEBSITE}")
    st.caption(f"v{B.VERSION} · {B.BUILD_DATE}")

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
    "user_access": render_user_access,
}
_ADMIN_ONLY_VIEWS = ("masters", "user_access")
if ss.view in _ADMIN_ONLY_VIEWS and not is_admin:
    ss.view = "dashboard"      # a non-admin can never land on an admin page
_VIEWS.get(ss.view, render_dashboard)()

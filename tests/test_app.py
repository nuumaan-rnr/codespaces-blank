"""Smoke tests for the Streamlit dashboard via AppTest (no analysis run)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

AppTest = pytest.importorskip(
    "streamlit.testing.v1", reason="streamlit not installed").AppTest

APP = os.path.join(os.path.dirname(__file__), "..", "app_streamlit.py")
MASTER = os.path.join(os.path.dirname(__file__), "..", "examples",
                      "Master.xlsx")


def _setss(at, **kw):
    for k, v in kw.items():
        at.session_state[k] = v


def test_dashboard_opens_on_load(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    # hero title rendered as branded markdown
    assert any("Storage Rack Design" in (m.value or "") for m in at.markdown)
    assert any("rnr-hero" in (m.value or "") for m in at.markdown)
    # left menu + create-new-project on the right
    assert any("Dashboard" in b.label for b in at.sidebar.button)
    assert any("Create new project" in b.label for b in at.button)
    # portfolio stat strip + empty state with no projects
    md = " ".join(m.value or "" for m in at.markdown)
    assert "rnr-statrow" in md
    assert "rnr-empty" in md


def test_new_project_and_configure_shows_first_side(tmp_path, monkeypatch):
    if not os.path.exists(MASTER):
        pytest.skip("Master.xlsx not present")
    monkeypatch.chdir(tmp_path)
    from rack15512.master_store import MasterStore
    from rack15512.project import ProjectStore
    MasterStore("masters").import_xlsx(MASTER, name="Standard")
    ps = ProjectStore("projects")
    proj = ps.create_project("Job")
    sysm = ps.add_system(proj.id, "Aisle 1")

    at = AppTest.from_file(APP, default_timeout=90)
    _setss(at, view="configure", project_id=proj.id, system_id=sysm.id,
           config_id=None, edit_cfg=None)
    at.run()
    assert not at.exception
    radios = {r.label: r for r in at.radio}
    # the bracing first-diagonal control is visible with outer/inner
    assert "First diagonal connects to" in radios
    assert list(radios["First diagonal connects to"].options) == ["outer",
                                                                  "inner"]


def test_drive_in_form_hides_selective_inputs(tmp_path, monkeypatch):
    """Selecting the drive-in family shows only drive-in / shuttle inputs and
    hides the selective-rack-only inputs (bays, beam span, footplate, anchors)."""
    if not os.path.exists(MASTER):
        pytest.skip("Master.xlsx not present")
    monkeypatch.chdir(tmp_path)
    from rack15512.master_store import MasterStore
    from rack15512.project import ProjectStore
    MasterStore("masters").import_xlsx(MASTER, name="Standard")
    ps = ProjectStore("projects")
    proj = ps.create_project("Job")
    sysm = ps.add_system(proj.id, "Aisle 1")

    at = AppTest.from_file(APP, default_timeout=120)
    _setss(at, view="configure", project_id=proj.id, system_id=sysm.id,
           config_id=None, edit_cfg=None)
    at.run()
    assert not at.exception
    fam = next(r for r in at.radio if r.label == "Rack family")
    fam.set_value("Drive-in / Drive-through / Radio shuttle").run()
    assert not at.exception
    labels = {w.label for w in (list(at.number_input) + list(at.selectbox)
                                + list(at.radio) + list(at.checkbox)
                                + list(at.text_input))}
    # drive-in / shuttle inputs present
    assert {"Lanes", "Pallets deep", "Plan bracing type"} <= labels
    # selective-only inputs hidden
    for sel_only in ("Bays", "Beam span [mm]", "Plate b [mm] (0=std)",
                     "Anchors / plate", "Floor stiffness [kNm/rad] (if not auto)"):
        assert sel_only not in labels, f"{sel_only!r} should be hidden for drive-in"


def test_view_saved_config_shows_results(tmp_path, monkeypatch):
    if not os.path.exists(MASTER):
        pytest.skip("Master.xlsx not present")
    monkeypatch.chdir(tmp_path)
    from rack15512.builder import LevelSpec, RackConfig
    from rack15512.master_store import MasterStore
    from rack15512.project import ProjectStore
    MasterStore("masters").import_xlsx(MASTER, name="Standard")
    ps = ProjectStore("projects")
    proj = ps.create_project("Job")
    sysm = ps.add_system(proj.id, "A1")
    cfg = RackConfig(n_bays=1,
                     levels=[LevelSpec(1500.0, "RHS 112x50x2.0", 20000.0)],
                     upright_section="UP0016", brace_section="C 36X21X1.5")
    conf = ps.add_configuration(proj.id, sysm.id, "Cfg", cfg,
                                master_id="standard")
    ps.update_run_summary(proj.id, sysm.id, conf.id, {
        "verdict": "PASS", "n_cases": 16,
        "governing": {"check": "STRESS", "target": "member 9",
                      "utilization": 0.77},
        "max_utilization_by_check": {"STRESS": 0.77}})
    at = AppTest.from_file(APP, default_timeout=90)
    _setss(at, view="view_config", project_id=proj.id, system_id=sysm.id,
           config_id=conf.id, vc_tab="📊 Results")
    at.run()
    assert not at.exception
    # results shown as branded tiles + verdict pill
    md = " ".join(m.value or "" for m in at.markdown)
    assert "rnr-pill" in md and "PASS" in md
    assert "Governing" in md and "STRESS" in md

    # a pending tab jump (set by the run dialog) lands on that tab without the
    # "modify a live widget" error, and the radio reflects it
    _setss(at, view="view_config", project_id=proj.id, system_id=sysm.id,
           config_id=conf.id, vc_jump="⚙️ Parameters")
    at.run()
    assert not at.exception
    assert at.session_state["vc_tab"] == "⚙️ Parameters"
    assert "vc_jump" not in at.session_state


def test_compare_view_shows_two_configs(tmp_path, monkeypatch):
    if not os.path.exists(MASTER):
        pytest.skip("Master.xlsx not present")
    monkeypatch.chdir(tmp_path)
    from rack15512.builder import LevelSpec, RackConfig
    from rack15512.master_store import MasterStore
    from rack15512.project import ProjectStore
    MasterStore("masters").import_xlsx(MASTER, name="Standard")
    ps = ProjectStore("projects")
    proj = ps.create_project("Job")
    sysm = ps.add_system(proj.id, "A1")
    for nm, util in (("Cfg A", 0.77), ("Cfg B", 1.10)):
        cfg = RackConfig(n_bays=1,
                         levels=[LevelSpec(1500.0, "RHS 112x50x2.0", 20000.0)],
                         upright_section="UP0016", brace_section="C 36X21X1.5")
        conf = ps.add_configuration(proj.id, sysm.id, nm, cfg,
                                    master_id="standard")
        ps.update_run_summary(proj.id, sysm.id, conf.id, {
            "verdict": "PASS" if util <= 1 else "FAIL", "n_cases": 16,
            "governing": {"check": "STRESS", "target": "member 9",
                          "utilization": util},
            "max_utilization_by_check": {"STRESS": util}})

    at = AppTest.from_file(APP, default_timeout=90)
    _setss(at, view="compare", project_id=proj.id)
    at.run()
    assert not at.exception
    md = " ".join(m.value or "" for m in at.markdown)
    assert "rnr-cmp" in md                 # comparison cards rendered
    assert "Cfg A" in md and "Cfg B" in md
    assert "util · STRESS" in md


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

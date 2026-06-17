"""Tests for the RFEM per-sheet upright property importer (one section per
sheet, columns Description|Symbol|Value|Unit|Comment) with the axis swap."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rack15512.checks.en15512 import _chi_ft
from rack15512.master_xlsx import (_infer_role, load_master,
                                   load_upright_properties)
from rack15512.model import Steel

HERE = os.path.dirname(__file__)
RFEM = os.path.join(HERE, "..", "examples", "Upright_Properties.xlsx")
MASTER = os.path.join(HERE, "..", "examples", "Master.xlsx")
needs = pytest.mark.skipif(not os.path.exists(RFEM),
                           reason="examples/Upright_Properties.xlsx not present")


@needs
def test_imports_all_sections_as_uprights():
    mw = load_upright_properties(RFEM)
    assert len(mw.library.sections) == 25
    assert all(s.role == "upright" for s in mw.library.sections.values())
    # auto-detection: plain load_master routes the per-sheet file here too
    assert len(load_master(RFEM).library.sections) == 25


@needs
def test_axis_swap_matches_existing_master():
    # RFEM major axis (Iy) maps to the model's local z; verify against the
    # existing examples/Master.xlsx which already encodes the swap
    new = load_upright_properties(RFEM).library.sections["UP0002"]
    assert abs(new.A - 318.0) < 1.0
    assert abs(new.Iz - 336500.0) < 1.0      # = RFEM Iy (major / down-aisle)
    assert abs(new.Iy - 105900.0) < 1.0      # = RFEM Iz (minor / cross-aisle)
    assert new.Welz > new.Wely               # strong-axis modulus is larger
    if os.path.exists(MASTER):
        old = load_master(MASTER).library.sections["UP0002"]
        assert abs(new.Iy - old.Iy) < 1.0 and abs(new.Iz - old.Iz) < 1.0


@needs
def test_full_property_spectrum_present():
    s = load_upright_properties(RFEM).library.sections["UP0016"]
    # shear areas (Timoshenko), warping + shear centre + torsion (FT buckling)
    assert s.Avy and s.Avz and s.Avy > 0 and s.Avz > 0
    assert s.It_gross and s.Iw_gross and s.y0
    assert s.depth_h and s.width_b            # parsed from the fibre distances
    assert s.buckling_curve_z in ("a0", "a", "b", "c", "d")


@needs
def test_ft_buckling_activates():
    mw = load_upright_properties(RFEM)
    s = mw.library.sections["UP0016"]
    mat = Steel("steel", fy=mw.fy["UP0016"])
    chi = _chi_ft(s, mat, length=3000.0, Ncr_y=1.0e5, beta_T=0.7)
    assert chi is not None and 0.0 < chi <= 1.0   # not skipped


@needs
def test_upright_wall_thickness_derived():
    # the upright sheet has no explicit thickness; it is estimated from A and U
    # (perforation-corrected) so the beam connector can resolve by UPL
    mw = load_upright_properties(RFEM)
    t = {n: mw.library.sections[n].t for n in mw.library.sections}
    assert all(v and 1.0 < v < 4.0 for v in t.values())   # sensible gauges
    # known gauges recovered (nearest standard): UP0002~1.6, UP0004~2.0, UP0014~2.5
    assert abs(t["UP0002"] - 1.6) < 0.15
    assert abs(t["UP0004"] - 2.0) < 0.15
    assert abs(t["UP0014"] - 2.5) < 0.15


@needs
def test_fy_recovered_from_npl():
    mw = load_upright_properties(RFEM)
    # fy = Npl,d / A, rounded to 5 MPa -> a sensible steel grade
    assert all(200.0 <= fy <= 700.0 for fy in mw.fy.values())
    assert abs(mw.fy["UP0002"] - 355.0) < 1e-6


BEAMS = os.path.join(HERE, "..", "examples", "Beam_Master.xlsx")
BRACES = os.path.join(HERE, "..", "examples", "Bracing_Master.xlsx")
OTHER = os.path.join(HERE, "..", "examples", "Other_Master.xlsx")
needs_all = pytest.mark.skipif(
    not all(os.path.exists(p) for p in (BEAMS, BRACES, OTHER)),
    reason="example beam/bracing/other masters not present")


@needs_all
def test_role_inference_per_master():
    # the role hint comes from the import/file name; sections take that role
    assert {s.role for s in
            load_master(BEAMS, role_hint="beam").library.sections.values()} \
        == {"beam"}
    assert {s.role for s in
            load_master(BRACES, role_hint="bracing").library.sections.values()} \
        == {"bracing"}
    # other master (rails + connectors) -> the catch-all 'others' role, both
    # via the file-name hint and via auto-detection (per-section heuristic)
    assert _infer_role("OTHER_MASTER.xlsx") == "others"
    assert {s.role for s in
            load_master(OTHER, role_hint="others").library.sections.values()} \
        == {"others"}
    assert {s.role for s in
            load_master(OTHER).library.sections.values()} == {"others"}


@needs_all
def test_bracing_blank_header_first_sheet_detected():
    # the bracing file's first sheet has a blank leading row; detection and
    # parsing must still pick it up
    mw = load_master(BRACES)
    assert len(mw.library.sections) >= 9
    s = next(iter(mw.library.sections.values()))
    assert s.A > 0 and s.Iz > 0


STIFF = os.path.join(HERE, "..", "examples", "Beam_Stiffness.xlsx")
needs_stiff = pytest.mark.skipif(
    not (os.path.exists(STIFF) and os.path.exists(BEAMS)),
    reason="beam stiffness / beam master example not present")


@needs_stiff
def test_beam_stiffness_parse_and_merge(tmp_path):
    from rack15512.master_xlsx import parse_beam_stiffness
    from rack15512.master_store import MasterStore, StoredMaster
    bs = parse_beam_stiffness(STIFF)
    assert bs and "RHS60X40X1.6" in bs                  # name normalised
    e = bs["RHS60X40X1.6"]
    assert len(e["kb"]) == 3 and e["m_rd"] > 0
    assert e["kb"][0][1] == pytest.approx(1566.0 * 1e4)  # kNcm/rad -> N*mm/rad

    store = MasterStore(str(tmp_path / "m"))
    mw = load_master(BEAMS, role_hint="beam")
    sm = StoredMaster.from_workbook(mw, "beam", "Beam")
    sm.company = "Acme"
    store.save(sm)
    nb, nbt = store.merge_stiffness("beam", STIFF)
    assert nb > 0                                        # beams updated
    cs = store.load("beam").library.get("RHS60X40X1.6")
    assert cs.connector_k_by_upl and cs.connector_m_rd
    # connector stiffness resolves by upright wall thickness (nearest UPL)
    assert cs.connector_k_for(1.6) < cs.connector_k_for(2.5)
    assert cs.connector_k_for(None) == cs.connector_k    # middle-UPL default


UPGEO = os.path.join(HERE, "..", "examples", "Upright_Geometry.xlsx")
BMGEO = os.path.join(HERE, "..", "examples", "Beam_Geometry.xlsx")
needs_geo = pytest.mark.skipif(
    not (os.path.exists(UPGEO) and os.path.exists(RFEM)),
    reason="geometry / upright example not present")


@needs_geo
def test_geometry_only_master_imports_standalone():
    # a geometry-only UPRIGHT_MASTER/BEAM_MASTER (Section + dims + thickness,
    # no A/I/W columns) must import without crashing, computing gross properties
    mu = load_master(UPGEO, role_hint="upright")
    assert len(mu.library.sections) >= 25
    u = mu.library.get("UP0002")
    assert u.A > 0 and u.Iz > u.Iy and u.t == 1.6        # strong axis = local z
    if os.path.exists(BMGEO):
        mb = load_master(BMGEO, role_hint="beam")
        b = mb.library.get("RHS 60x40x1.2")
        assert b.A > 0 and b.Iz > b.Iy and b.t == 1.2


@needs_geo
def test_geometry_parse_and_merge_thickness(tmp_path):
    from rack15512.master_xlsx import parse_section_geometry
    from rack15512.master_store import MasterStore, StoredMaster
    g = parse_section_geometry(UPGEO)
    assert g["UP0002"]["t"] == 1.6 and g["UP0004"]["t"] == 2.0   # explicit gauge
    assert g["UP0002"]["e1"] and g["UP0002"]["e2"]               # edge distances
    if os.path.exists(BMGEO):
        gb = parse_section_geometry(BMGEO)
        assert gb["RHS60X40X1.2"]["t"] == 1.2

    # merge the explicit thickness into the RFEM upright master (replaces the
    # imported gauge estimate)
    store = MasterStore(str(tmp_path / "m"))
    mw = load_master(RFEM, role_hint="upright")
    sm = StoredMaster.from_workbook(mw, "up", "Up")
    sm.company = "Acme"
    store.save(sm)
    n, _ = store.merge_stiffness("up", UPGEO)
    assert n >= 25
    up = store.load("up").library.get("UP0004")
    assert up.t == 2.0 and up.e1 and up.e2


def test_build_fixes_zero_torsion_constant():
    # an imported section with J = 0 (sheet blank / rounded) must not crash the
    # build: the solver needs J > 0, so it falls back to A*t^2/3
    from rack15512.builder import RackConfig, build_rack, LevelSpec
    from rack15512.library import SectionLibrary
    from rack15512.master_xlsx import MasterWorkbook
    from rack15512.model import CrossSection
    secs = {
        "UP": CrossSection("UP", "steel", A=400, Iy=1e5, Iz=3e5, J=200,
                           Wely=2e3, Welz=6e3, role="upright", t=2.0),
        "BM": CrossSection("BM", "steel", A=300, Iy=8e4, Iz=1.5e5, J=1e5,
                           Wely=4e3, Welz=5e3, role="beam", t=1.6),
        "1C26X21X1.2": CrossSection("1C26X21X1.2", "steel", A=65, Iy=4700,
                                    Iz=7100, J=0.0, Wely=410, Welz=540,
                                    role="bracing", t=1.2),
    }
    mw = MasterWorkbook(library=SectionLibrary(secs), base_tables={}, fy={})
    m = build_rack(RackConfig(
        n_bays=2, levels=[LevelSpec(1500.0, "BM", 20000.0)],
        upright_section="UP", beam_section="BM", brace_section="1C26X21X1.2",
        master=mw, base_stiffness=5e8))
    assert m.validate() == []
    assert m.sections["1C26X21X1.2"].J > 0


def test_consolidated_template_roundtrips(tmp_path):
    # the generated template imports as ONE master: all roles + base + beam
    # stiffness, with the labelled units converted to the model's N/mm
    from rack15512.master_template import build_master_template
    p = str(tmp_path / "tpl.xlsx")
    build_master_template(p)
    mw = load_master(p)
    assert {s.role for s in mw.library.sections.values()} == {
        "upright", "beam", "bracing", "others"}
    u = mw.library.get("UP0002")
    assert u.A == pytest.approx(318.0)        # 3.18 cm2 -> mm2
    assert u.Iz > u.Iy                        # major axis in local z
    assert u.Avy and u.Avz and u.It_gross and u.Iw_gross and u.y0
    assert u.t == 1.6 and mw.fy["UP0002"] == 355.0
    # base stiffness table parsed (kN, kNcm/rad, kNcm -> N, N*mm/rad, N*mm)
    assert mw.base_tables["UP0002"][0][0] == pytest.approx(30000.0)
    # beam connector stiffness resolves by upright thickness
    b = mw.library.get("RHS 60x40x1.6")
    assert b.connector_k_by_upl and b.connector_k_for(1.6) < b.connector_k_for(2.5)


@needs
def test_fy_override_uses_input_fy():
    # fy_override makes every section take the input steel_fy, ignoring master
    from rack15512.builder import RackConfig, build_rack
    mw = load_upright_properties(RFEM)
    base = dict(system_type="drive_in", di_variant="drive_in", n_lanes=2,
                n_deep=4, n_frames=3, beam_levels=[2400.0, 4900.0],
                frame_height=6000.0, master=mw, upright_section="UP0016",
                steel_fy=420.0, mesh_beam=1, mesh_upright=1)
    m_ov = build_rack(RackConfig(fy_override=True, **base))
    assert {round(mat.fy) for mat in m_ov.materials.values()} == {420}
    m_no = build_rack(RackConfig(fy_override=False, **base))
    assert any(round(mat.fy) != 420 for mat in m_no.materials.values())

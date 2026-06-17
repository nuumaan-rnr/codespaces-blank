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

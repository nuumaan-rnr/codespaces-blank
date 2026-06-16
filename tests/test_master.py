"""Tests for the .xlsx master importer and the D/X bracing arrangement."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rack15512.analysis import run_all
from rack15512.builder import RackConfig, bracing_elevations, build_rack
from rack15512.checks.en15512 import run_checks
from rack15512.master_xlsx import load_master

MASTER = os.path.join(os.path.dirname(__file__), "..", "examples",
                      "Master.xlsx")
needs_master = pytest.mark.skipif(not os.path.exists(MASTER),
                                  reason="examples/Master.xlsx not present")


@needs_master
def test_master_xlsx_units_and_axes():
    mw = load_master(MASTER)
    lib = mw.library
    assert len(lib.names("upright")) == 25
    assert len(lib.names("beam")) == 21
    assert len(lib.names("bracing")) == 4
    up = lib.get("UP0002")          # Aeff 3.18 cm2, Iyy 33.65 cm4, fy 35
    assert up.A == pytest.approx(318.0)
    assert up.Iz == pytest.approx(3.365e5)      # workbook Iyy -> local z
    assert up.Iy == pytest.approx(1.059e5)
    assert up.mod_z_eff == pytest.approx(7470.0)
    assert mw.fy["UP0002"] == pytest.approx(350.0)
    bm = lib.get("RHS 60x40x1.2")   # I 11.64 cm4, Z 3.88 cm3, fy 27
    assert bm.Iz == pytest.approx(1.164e5)
    assert bm.Welz == pytest.approx(3880.0)
    assert mw.fy[bm.name] == pytest.approx(270.0)
    assert bm.Iy < bm.Iz            # computed minor axis
    assert bm.J > 0
    # duplicate brace names are de-duplicated
    assert "C 34X34X2.0 #2" in lib.names("bracing")
    br = lib.get("C 36X21X1.2")     # IT 0.00372 cm4
    assert br.J == pytest.approx(37.2)


def test_beam_master_connector_columns(tmp_path):
    """Optional 'Connector ...' columns in BEAM_MASTER are detected by
    header text and converted (kNcm/rad, kNcm, mrad -> N*mm/rad, N*mm,
    rad); beams without values get None (cfg fallback applies)."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BEAM_MASTER"
    ws.append([])
    ws.append([None, "#", "SECTION", "Sec Height", "Sec Depth", "Sec Thick",
               "I", "Wel", "fy", "M_Rd", "EI",
               "Connector k\n(kNcm/rad)", "Connector M_Rd\n(kNcm)",
               "Connector looseness\n(mrad)"])
    ws.append([None, 1, "RHS-A", 100, 50, 1.6, 61.27, 12.25, 31, 379.75,
               0, 6573, 110, 4.0])
    ws.append([None, 2, "RHS-B", 80, 40, 1.6, 30.7, 7.67, 27, 207.09,
               0, None, None, None])
    p = tmp_path / "beams.xlsx"
    wb.save(p)
    mw = load_master(str(p))
    a = mw.library.get("RHS-A")
    assert a.connector_k == pytest.approx(6573.0 * 1e4)      # 65.73 kNm/rad
    assert a.connector_m_rd == pytest.approx(110.0 * 1e4)    # 1.10 kNm
    assert a.connector_looseness == pytest.approx(4.0e-3)
    b = mw.library.get("RHS-B")
    assert b.connector_k is None and b.connector_m_rd is None


def test_builder_uses_per_beam_connector_data(tmp_path):
    """Hinges take stiffness/M_Rd/looseness from the beam's master data,
    per level; beams without data use the cfg fallback; phi_l = max
    looseness in use."""
    from rack15512.builder import LevelSpec, RackConfig, build_rack
    from rack15512.library import SectionLibrary

    lib = SectionLibrary.bundled()
    sec_a = lib.get("BM-110x50x1.5")
    sec_a.connector_k = 6.573e7
    sec_a.connector_m_rd = 1.1e6
    sec_a.connector_looseness = 4.0e-3
    model = build_rack(RackConfig(
        n_bays=1, library=lib,
        levels=[LevelSpec(gap=1500.0, beam_section="BM-110x50x1.5"),
                LevelSpec(gap=1500.0, beam_section="BM-130x50x1.5")],
        connector_stiffness=1.0e8, connector_m_rd=2.5e6,
        connector_looseness=0.0))
    beams = sorted((m for m in model.members.values()
                    if m.member_set == "pallet beams"),
                   key=lambda m: model.nodes[m.node_i].z)
    l1, l2 = beams[0], beams[-1]
    assert l1.hinge_i.rz == pytest.approx(6.573e7)           # from master
    assert l1.hinge_i.m_rd_z == pytest.approx(1.1e6)
    assert l1.hinge_i.looseness == pytest.approx(4.0e-3)
    assert l2.hinge_i.rz == pytest.approx(1.0e8)             # cfg fallback
    assert l2.hinge_i.m_rd_z == pytest.approx(2.5e6)
    # imperfection includes the largest looseness in use
    assert model.imperfection.phi_l == pytest.approx(4.0e-3)


@needs_master
def test_base_stiffness_interpolation():
    mw = load_master(MASTER)
    assert len(mw.base_tables) == 25
    # UP0002: 30 kN -> 1823.198 kNcm/rad, 40 kN -> 3470.267 kNcm/rad
    k30, _ = mw.base_stiffness("UP0002", 30e3)
    k40, m40 = mw.base_stiffness("UP0002", 40e3)
    assert k30 == pytest.approx(1823.198 * 1e4, rel=1e-4)
    assert k40 == pytest.approx(3470.267 * 1e4, rel=1e-4)
    assert m40 == pytest.approx(172.709 * 1e4, rel=1e-4)
    k35, _ = mw.base_stiffness("UP0002", 35e3)
    assert k30 < k35 < k40
    # clamped outside the table
    klo, _ = mw.base_stiffness("UP0002", 1.0)
    assert klo == pytest.approx(k30)


def test_bracing_elevations():
    cfg = RackConfig(bracing_start=150.0, bracing_pitch=600.0)
    zs = bracing_elevations(cfg, 9898.0)
    assert zs[0] == 150.0
    assert zs[1] == 750.0
    assert zs[-1] == 9750.0                     # last fit below 9898
    assert zs[-1] + 600.0 > 9898.0
    assert len(zs) == 17


def _bracing_members(model):
    return [m for m in model.members.values() if m.member_set == "bracing"]


def test_d_frame_bracing_arrangement():
    cfg = RackConfig(n_bays=1, beam_levels=[2000.0, 4000.0],
                     frame_height=4500.0, bracing_type="D",
                     bracing_start=150.0, bracing_pitch=600.0)
    model = build_rack(cfg)
    zs = bracing_elevations(cfg, 4500.0)        # 150..4350, 8 points
    assert len(zs) == 8
    braces = _bracing_members(model)
    # per frame line: 7 zigzag diagonals + horizontals at 150 and 4350 only
    assert len(braces) == 2 * (7 + 2)
    horizontals = [b for b in braces
                   if model.nodes[b.node_i].z == model.nodes[b.node_j].z]
    assert sorted({model.nodes[b.node_i].z for b in horizontals}) == [150.0,
                                                                      4350.0]
    diagonals = [b for b in braces if b not in horizontals]
    for d in diagonals:                          # each spans exactly one pitch
        dz = abs(model.nodes[d.node_j].z - model.nodes[d.node_i].z)
        dy = abs(model.nodes[d.node_j].y - model.nodes[d.node_i].y)
        assert dz == pytest.approx(600.0)
        assert dy == pytest.approx(cfg.depth)
    # zigzag: consecutive diagonals alternate direction (per line)
    line0 = sorted((d for d in diagonals if model.nodes[d.node_i].x == 0),
                   key=lambda d: model.nodes[d.node_i].z)
    sides = [model.nodes[d.node_i].y for d in line0]
    assert all(a != b for a, b in zip(sides, sides[1:]))


def test_x_frame_bracing_arrangement():
    cfg = RackConfig(n_bays=1, beam_levels=[2000.0, 4000.0],
                     frame_height=4500.0, bracing_type="X")
    model = build_rack(cfg)
    braces = _bracing_members(model)
    # per line: 7 panels x 2 crossed diagonals + 2 horizontals
    assert len(braces) == 2 * (7 * 2 + 2)


def test_custom_pitch_and_per_level_beams():
    cfg = RackConfig(n_bays=1, beam_levels=[1200.0, 2900.0, 5100.0],
                     bracing_pitch=750.0, bracing_start=200.0)
    model = build_rack(cfg)
    beam_z = sorted({model.nodes[m.node_i].z
                     for m in model.members.values()
                     if m.member_set == "pallet beams"})
    assert beam_z == [1200.0, 2900.0, 5100.0]   # individual levels honoured
    zs = bracing_elevations(cfg, 5100.0)
    assert zs[0] == 200.0 and all(
        b - a == pytest.approx(750.0) for a, b in zip(zs, zs[1:]))


@needs_master
def test_full_run_with_xlsx_master():
    cfg = RackConfig(n_bays=2, beam_levels=[2000.0, 4000.0],
                     frame_height=4500.0, bracing_type="X",
                     master=load_master(MASTER),
                     upright_section="UP0008",
                     beam_section="RHS 100x50x1.6",
                     brace_section="C 36X21X1.5",
                     base_stiffness="auto")
    model = build_rack(cfg)
    # per-section fy materials from the workbook
    assert model.materials[model.sections["UP0008"].material].fy == 350.0
    assert model.materials[
        model.sections["RHS 100x50x1.6"].material].fy == 310.0
    sup = model.supports[0]
    # auto base stiffness applied in the down-aisle direction (ry) only;
    # cross-aisle (rx) base is pinned (braced frame)
    assert isinstance(sup.ry, float) and sup.ry > 0
    assert sup.rx is False
    cases = run_all(model)
    assert all(c.converged for c in cases)
    checks = run_checks(model, cases)
    assert checks


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

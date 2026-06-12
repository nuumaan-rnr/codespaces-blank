"""Tests for the section library, EN 15512 checks and the full 3D pipeline."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rack15512 import io_json
from rack15512.analysis import run_all
from rack15512.builder import RackConfig, build_rack
from rack15512.checks import buckling
from rack15512.checks.en15512 import all_ok, governing, run_checks
from rack15512.library import SectionLibrary
from rack15512.model import Imperfection


def test_buckling_curve_values():
    """Spot values of EN 1993-1-1 Table 6.2 (curve b)."""
    assert buckling.chi(0.2, "b") == pytest.approx(1.0)
    assert buckling.chi(1.0, "b") == pytest.approx(0.5970, abs=0.002)
    assert buckling.chi(1.5, "b") == pytest.approx(0.3422, abs=0.002)
    assert buckling.chi(0.5, "a") > buckling.chi(0.5, "d")


def test_imperfection_formula():
    imp = Imperfection(n_cols=4, phi_s=1 / 350.0, phi_l=0.0)
    # sqrt(0.5 + 1/4) * 2/350 = 0.004949
    assert imp.value() == pytest.approx(0.004949, abs=1e-5)
    assert Imperfection(phi=0.003).value() == 0.003
    assert Imperfection(n_cols=100, phi_s=1 / 5000.0).value() == 1 / 500.0
    with pytest.raises(ValueError):
        Imperfection().value()


def test_section_library():
    lib = SectionLibrary.bundled()
    assert set(lib.roles()) == {"upright", "beam", "bracing"}
    assert "UP-100x100x2.0" in lib.names("upright")
    up = lib.get("UP-100x100x2.0")
    assert up.A == 780 and up.A_eff == 660 and up.Iz == pytest.approx(1.2e6)
    assert up.buckling_curve_y == "b"
    bm = lib.get("BM-110x50x1.5")
    assert bm.A_eff is None and bm.area_eff == bm.A    # gross fallback
    with pytest.raises(KeyError):
        lib.get("NOPE")


def test_section_library_mapping(tmp_path):
    """A user master with custom column names loads via `mapping`."""
    p = tmp_path / "master.csv"
    p.write_text("Profile,Type,Area,IYY,IZZ,Torsion,WY,WZ\n"
                 "MY-UP,upright,500,4e5,6e5,800,8e3,1.2e4\n")
    lib = SectionLibrary.from_csv(str(p), mapping={
        "Profile": "name", "Type": "role", "Area": "A", "IYY": "Iy",
        "IZZ": "Iz", "Torsion": "J", "WY": "Wely", "WZ": "Welz"})
    s = lib.get("MY-UP")
    assert s.role == "upright" and s.J == 800 and s.Welz == pytest.approx(1.2e4)


def test_full_pipeline_and_json_roundtrip(tmp_path):
    model = build_rack(RackConfig(n_bays=2, beam_levels=[1800.0, 3600.0],
                                  depth=1100.0))
    # JSON round trip preserves the model
    p = tmp_path / "m.json"
    io_json.save(model, str(p))
    model2 = io_json.load(str(p))
    assert len(model2.members) == len(model.members)
    beams = [m for m in model2.members.values()
             if m.member_set == "pallet beams"]
    assert beams and beams[0].hinge_i.rz == 1.0e8
    braces = [m for m in model2.members.values() if m.member_set == "bracing"]
    assert braces and all(b.mtype == "truss" for b in braces)

    cases = run_all(model2)
    assert all(c.converged for c in cases)
    uls = [c for c in cases if c.kind == "ULS"]
    sls = [c for c in cases if c.kind == "SLS"]
    # 3 ULS combos x 4 imperfection directions, 2 SLS
    assert len(uls) == 12 and len(sls) == 2
    assert {c.imp_direction for c in uls} == {"+x", "-x", "+y", "-y"}
    # second-order sway exceeds first-order sway under gravity + EHF
    swayed = [c for c in uls if c.sway_first_order]
    assert swayed and all(c.max_sway > c.sway_first_order for c in swayed)
    # the down-aisle imperfection drives X sway; the braced cross-aisle
    # direction is far stiffer, so the Y imperfection produces only
    # sub-millimetre sway (the residual X value there is the symmetric
    # gravity-induced bulge, not sway)
    cx = next(c for c in uls if c.combo == "ULS1" and c.imp_direction == "+x")
    cy = next(c for c in uls if c.combo == "ULS1" and c.imp_direction == "+y")
    assert cx.max_sway_x > cx.max_sway_y
    assert cx.max_sway_x > 5.0 * cy.max_sway_y

    checks = run_checks(model2, cases)
    kinds = {c.check for c in checks}
    assert {"STRESS", "BUCKLING", "CONNECTOR", "DEFLECTION", "SWAY",
            "ALPHA_CR"} <= kinds
    gov = governing(checks)
    assert gov is not None and not gov.informative
    assert isinstance(all_ok(checks), bool)


def test_back_to_back_module_and_buckling_rules():
    cfg = RackConfig(module="back-to-back", n_bays=1, depth=1000.0,
                     b2b_gap=250.0, beam_levels=[1500.0, 3000.0],
                     frame_height=3300.0, bracing_type="D",
                     bracing_start=150.0, bracing_pitch=600.0)
    model = build_rack(cfg)
    # four upright lines across the CA direction
    assert {round(n.y) for n in model.nodes.values()} == {0, 1000, 1250, 2250}
    spacers = [m for m in model.members.values()
               if m.member_set == "row spacers"]
    assert len(spacers) == 2 * 2            # 2 levels x 2 frame lines
    assert all(m.mtype == "truss" for m in spacers)
    # 4 upright lines get supports
    assert len(model.supports) == 2 * 4
    # buckling restricted to the uprights
    assert model.checks.buckling_sets == ["uprights"]
    # major-axis buckling length = beam gap of the level band
    ups = [m for m in model.members.values() if m.member_set == "uprights"]
    def mid_z(m):
        return (model.nodes[m.node_i].z + model.nodes[m.node_j].z) / 2
    seg_low = next(m for m in ups if mid_z(m) < 1500)
    seg_up = next(m for m in ups if 1500 < mid_z(m) < 3000)
    assert seg_low.L_buckling_z == pytest.approx(1500.0)
    assert seg_up.L_buckling_z == pytest.approx(1500.0)
    # minor-axis = max unsupported between diagonal connections; D-pattern
    # touches each upright every other pitch -> 2 x 600
    assert seg_low.L_buckling_y == pytest.approx(1200.0)
    # X-pattern braces every pitch -> 600 (plus base/top gaps may govern)
    xmod = build_rack(RackConfig(module="single", n_bays=1,
                                 beam_levels=[1500.0, 3000.0],
                                 frame_height=3300.0, bracing_type="X",
                                 bracing_start=150.0, bracing_pitch=600.0))
    xups = [m for m in xmod.members.values() if m.member_set == "uprights"]
    assert xups[0].L_buckling_y == pytest.approx(600.0)


def test_buckling_only_on_uprights():
    model = build_rack(RackConfig(n_bays=1, beam_levels=[1800.0]))
    cases = run_all(model)
    checks = run_checks(model, cases)
    buckling = [c for c in checks if c.check == "BUCKLING"]
    assert buckling
    assert all(c.member_set == "uprights" for c in buckling)
    # beams still get stress + deflection
    assert any(c.check == "STRESS" and c.member_set == "pallet beams"
               for c in checks)
    assert any(c.check == "DEFLECTION" and c.member_set == "pallet beams"
               for c in checks)


def test_overloaded_rack_fails_checks():
    cfg = RackConfig(n_bays=2, beam_levels=[2500.0, 5000.0, 7500.0, 10000.0],
                     upright_section="UP-90x70x1.8",
                     pallet_load_per_level=60000.0)   # 6 t per bay per level
    model = build_rack(cfg)
    cases = run_all(model)
    checks = run_checks(model, cases)
    converged = [c for c in cases if c.kind == "ULS" and c.converged]
    # either the second-order analysis diverges (instability) or checks fail
    assert (not converged) or (not all_ok(checks))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

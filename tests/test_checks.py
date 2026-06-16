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


def test_shear_and_ltb_checks():
    m = build_rack(RackConfig(n_bays=2, beam_levels=[2000.0, 4000.0],
                              depth=1000.0, frame_height=4500.0))
    # give beam-type sections a web so SHEAR can evaluate (default master omits)
    for s in m.sections.values():
        if s.t is None:
            s.t = 2.0
        if s.depth_h is None:
            s.depth_h = 100.0
    checks = run_checks(m, run_all(m))
    shear = [c for c in checks if c.check == "SHEAR"]
    # SHEAR on beam-type members only, never on the truss bracing
    assert shear and "bracing" not in {c.member_set for c in shear}
    assert any(c.member_set == "pallet beams" for c in shear)
    numeric = [c for c in shear if not c.informative]
    assert numeric and all(0.0 <= c.utilization < 1.0 for c in numeric)
    # LTB: pallet beams, informative when laterally restrained (default)
    ltb = [c for c in checks if c.check == "LTB"]
    assert ltb and all(c.informative and c.member_set == "pallet beams"
                       for c in ltb)
    # unrestrained beams get a computed LTB utilisation
    m2 = build_rack(RackConfig(n_bays=1, beam_levels=[2000.0], depth=1000.0,
                               frame_height=2500.0,
                               beam_laterally_restrained=False))
    ltb2 = [c for c in run_checks(m2, run_all(m2)) if c.check == "LTB"]
    assert ltb2 and any(not c.informative and c.utilization > 0.0 for c in ltb2)


def test_shear_ltb_info_is_consolidated():
    # default master has no t/depth on uprights/beams, and beams are restrained:
    # the "not evaluated" / "restrained" notes must be consolidated (one per
    # case) rather than one per member, to avoid flooding the report
    m = build_rack(RackConfig(n_bays=3, beam_levels=[2000.0, 4000.0],
                              depth=1000.0))
    checks = run_checks(m, run_all(m))
    # no per-member informative SHEAR/LTB rows
    assert not any(c.check in ("SHEAR", "LTB") and c.informative
                   and c.target.startswith("member") for c in checks)
    shear_info = [c for c in checks if c.check == "SHEAR" and c.informative]
    ltb_info = [c for c in checks if c.check == "LTB" and c.informative]
    assert shear_info and all(c.target == "sections" for c in shear_info)
    assert ltb_info and all(c.target == "pallet beams" for c in ltb_info)
    # one consolidated note per case (≪ member count)
    assert len(shear_info) == len({c.case for c in shear_info})


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
    # 3 gravity ULS combos + 1 pattern (checkerboard) combo, each x 4
    # imperfection directions, + 2 accidental combos with a single direction
    # each; 2 SLS
    assert len(uls) == 18 and len(sls) == 2
    assert {c.imp_direction for c in uls} == {"+x", "-x", "+y", "-y"}
    acc = [c for c in uls if "acc" in c.combo]
    assert len(acc) == 2
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
               if m.member_set == "frame spacer"]
    assert len(spacers) == 2 * 2            # 2 levels x 2 frame lines
    assert all(m.mtype == "beam" for m in spacers)   # beam ties (in-plane)
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


def test_frame_spacers_and_downaisle_base():
    from rack15512.builder import frame_spacer_levels
    cfg = RackConfig(module="back-to-back", n_bays=1, depth=1000.0, b2b_gap=300.0,
                     beam_levels=[1500.0, 3000.0, 4500.0], frame_height=7500.0,
                     base_stiffness=8e8)
    # industry rule: a tie every 2400 mm + a mandatory tie 200 mm below the top
    assert frame_spacer_levels(cfg, 7500.0) == [2400.0, 4800.0, 7300.0]
    m = build_rack(cfg)
    sp_z = sorted({round(m.nodes[mm.node_i].z) for mm in m.members.values()
                   if mm.member_set == "frame spacer"})
    assert sp_z == [2400, 4800, 7300]          # not at every beam level
    # base spring is applied in the down-aisle direction (ry) only; the
    # cross-aisle (rx) base is pinned (braced frame)
    assert all(s.rx is False for s in m.supports)
    assert any(s.ry == 8e8 for s in m.supports)


def test_frame_spacer_minimum_two():
    from rack15512.builder import frame_spacer_levels
    cfg = RackConfig(frame_height=3000.0)
    lv = frame_spacer_levels(cfg, 3000.0)
    assert len(lv) >= 2 and lv[-1] == 2800.0   # min 2, mandatory top at H-200


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


def test_brace_area_factor_in_analysis_only():
    """Only 15% of the brace area acts in the analysis; the stress check
    still uses the full section."""
    model = build_rack(RackConfig(n_bays=1, beam_levels=[1800.0]))
    braces = [m for m in model.members.values() if m.member_set == "bracing"]
    assert braces and all(m.area_factor == 0.15 for m in braces)
    ups = [m for m in model.members.values() if m.member_set == "uprights"]
    assert all(m.area_factor == 1.0 for m in ups)


def test_brace_bolt_bearing_hand_calc():
    """M12 4.6 on C 36X21X1.5 (t=1.5, e1=e2=18, fu=350) against UP0016-like
    upright (t=2.0, e1=13.22, e2=15.15, fy=350 -> fu=385):
      bolt shear  = 0.6*400*84.3/1.25            = 16.19 kN
      brace ply   = 2.177*0.4615*350*12*1.5/1.25 =  5.06 kN
      upright ply = 1.563*0.339*385*12*2.0/1.25  =  3.92 kN  <- governs
    """
    from rack15512.checks.en15512 import BOLTS, BOLT_GRADES, _bearing
    from rack15512.model import CrossSection
    d0, As = BOLTS[12]
    fub, av = BOLT_GRADES["4.6"]
    Fv = av * fub * As / 1.25
    assert Fv == pytest.approx(16185.6, rel=1e-3)
    brace = CrossSection("b", "steel", A=102, Iy=1, Iz=1, J=1, Wely=1,
                         Welz=1, t=1.5, e1=18.0, e2=18.0, fu=350.0)
    upright = CrossSection("u", "steel", A=487, Iy=1, Iz=1, J=1, Wely=1,
                           Welz=1, t=2.0, e1=13.22, e2=15.15)
    Fb_brace = _bearing(12.0, d0, fub, brace, 350.0, 1.25)
    Fb_up = _bearing(12.0, d0, fub, upright, 385.0, 1.25)
    assert Fb_brace == pytest.approx(5063.0, rel=0.005)
    assert Fb_up == pytest.approx(3917.0, rel=0.005)
    assert min(Fv, Fb_brace, Fb_up) == Fb_up      # minimum governs


def test_brace_bolt_and_baseplate_checks_in_pipeline():
    cfg = RackConfig(n_bays=1, beam_levels=[1500.0, 3000.0],
                     master=__import__("rack15512.master_xlsx",
                                       fromlist=["load_master"]).load_master(
                         os.path.join(os.path.dirname(__file__), "..",
                                      "examples", "Master.xlsx")),
                     upright_section="UP0016",
                     beam_section="RHS 112x50x2.0",
                     brace_section="C 36X21X1.5",
                     base_stiffness="auto",
                     bolt_d=12.0, bolt_grade="4.6",
                     plate_b=150.0, plate_d=130.0, plate_t=4.0)
    model = build_rack(cfg)
    cases = run_all(model)
    checks = run_checks(model, cases)
    bolts = [c for c in checks if c.check == "BRACE_BOLT" and not c.informative]
    plates = [c for c in checks if c.check == "BASEPLATE"]
    assert bolts and all(c.member_set in ("bracing", "frame spacer")
                         for c in bolts)
    assert any("governs" in c.detail for c in bolts)
    # EN 15512 contact pressure: fj = 2.5 fck/gc and a typical 4 mm plate
    # verifies (the old 0.85 fck method wrongly failed it)
    assert plates and all(c.ok for c in plates)
    assert all("fj=2.5*fck" in c.detail and "Abas" in c.detail
               for c in plates)
    # base partial-restraint and anchorage checks present
    assert any(c.check == "BASE_RESTRAINT" for c in checks)
    assert any(c.check == "ANCHORAGE" for c in checks)
    # bracing members get their own buckling check
    bb = [c for c in checks if c.check == "BRACE_BUCKLING"]
    assert bb and all(c.member_set in ("bracing", "frame spacer") for c in bb)


def test_back_to_back_rear_bracing_mirrored():
    """The rear module's D-zigzag is inverted relative to the front frame
    (accidental-load path, per the frame drawing)."""
    cfg = RackConfig(module="back-to-back", n_bays=1, depth=1000.0,
                     b2b_gap=250.0, beam_levels=[1500.0, 3000.0],
                     frame_height=3300.0, bracing_type="D")
    model = build_rack(cfg)
    diags = [m for m in model.members.values()
             if m.member_set == "bracing"
             and abs(model.nodes[m.node_i].z - model.nodes[m.node_j].z) > 1]

    def first_panel_start_y(y_low_side, y_high_side):
        for d in diags:
            ni, nj = model.nodes[d.node_i], model.nodes[d.node_j]
            lo, hi = (ni, nj) if ni.z < nj.z else (nj, ni)
            if abs(lo.z - 150.0) < 1 and abs(ni.x) < 1 \
                    and lo.y in (y_low_side, y_high_side):
                return lo.y
        raise AssertionError("first panel diagonal not found")

    # front rack (y 0/1000): first diagonal starts at y=0
    assert first_panel_start_y(0.0, 1000.0) == 0.0
    # rear rack (y 1250/2250): mirrored -> first diagonal starts at y=2250
    assert first_panel_start_y(1250.0, 2250.0) == 2250.0


def test_ca_buckling_length_per_level_from_model():
    """X bracing up to the first beam level: level 1 band gets Lcr = pitch,
    the D zone above gets 2 x pitch - per level, from the actual model."""
    cfg = RackConfig(n_bays=1, beam_levels=[1350.0, 3150.0],
                     frame_height=3750.0, bracing_type="D",
                     bracing_type_zone1="X", bracing_start=150.0,
                     bracing_pitch=600.0)
    model = build_rack(cfg)
    ups = [m for m in model.members.values() if m.member_set == "uprights"]

    def mid_z(m):
        return (model.nodes[m.node_i].z + model.nodes[m.node_j].z) / 2

    band1 = [m for m in ups if mid_z(m) < 1350]
    band2 = [m for m in ups if 1350 < mid_z(m) < 3150]
    assert band1 and all(m.L_buckling_y == pytest.approx(600.0)
                         for m in band1)
    assert band2 and all(m.L_buckling_y == pytest.approx(1200.0)
                         for m in band2)
    # major axis still the beam gap of the band
    assert band1[0].L_buckling_z == pytest.approx(1350.0)
    assert band2[0].L_buckling_z == pytest.approx(1800.0)


def test_upright_splice_auto_and_check():
    """Frame height > 11 m: a splice is added automatically at H/2 and the
    bolt-group connection is verified per EN 1993-1-8."""
    master = __import__("rack15512.master_xlsx",
                        fromlist=["load_master"]).load_master(
        os.path.join(os.path.dirname(__file__), "..", "examples",
                     "Master.xlsx"))
    cfg = RackConfig(n_bays=1, beam_levels=[6000.0, 11000.0],
                     frame_height=12000.0, master=master,
                     upright_section="UP0022",
                     beam_section="RHS 122x61x2.0",
                     brace_section="C 34X34X2.0", base_stiffness="auto",
                     splice_rows=2, splice_cols=2, splice_p1=60.0,
                     splice_p2=40.0, splice_e1=30.0, splice_e2=20.0)
    model = build_rack(cfg)
    assert len(model.splices) == 1
    assert model.splices[0].z == pytest.approx(6000.0)
    # the splice elevation exists as a node line
    assert any(abs(n.z - 6000.0) < 1 for n in model.nodes.values())
    model.combinations = model.combinations[:1]
    model.imperfection.directions = ["+x"]
    cases = run_all(model)
    checks = run_checks(model, cases)
    sp = [c for c in checks if c.check == "SPLICE" and not c.informative]
    assert sp
    assert all("Fv=" in c.detail and "Fb=" in c.detail for c in sp)
    assert all(0.0 < c.utilization < 50.0 for c in sp)


def test_per_level_gap_section_and_load():
    """Every level takes its own beam gap, beam section and pallet load."""
    from rack15512.builder import LevelSpec
    model = build_rack(RackConfig(n_bays=1, levels=[
        LevelSpec(gap=1500.0, beam_section="BM-100x40x1.5",
                  pallet_load=15000.0),
        LevelSpec(gap=1700.0, beam_section="BM-130x50x1.5",
                  pallet_load=25000.0)]))
    beams = sorted((m for m in model.members.values()
                    if m.member_set == "pallet beams"),
                   key=lambda m: model.nodes[m.node_i].z)
    assert model.nodes[beams[0].node_i].z == pytest.approx(1500.0)
    assert model.nodes[beams[-1].node_i].z == pytest.approx(3200.0)
    assert beams[0].section == "BM-100x40x1.5"
    assert beams[-1].section == "BM-130x50x1.5"
    udl = {}
    for ml in model.load_cases["pallets"].member_loads:
        z = model.nodes[model.members[ml.member].node_i].z
        udl[round(z)] = abs(ml.qz)
    assert udl[1500] == pytest.approx(15000.0 / 2 / 2700.0)
    assert udl[3200] == pytest.approx(25000.0 / 2 / 2700.0)


def test_standard_footplate_defaults():
    master = __import__("rack15512.master_xlsx",
                        fromlist=["load_master"]).load_master(
        os.path.join(os.path.dirname(__file__), "..", "examples",
                     "Master.xlsx"))
    m90 = build_rack(RackConfig(n_bays=1, beam_levels=[1500.0], master=master,
                                upright_section="UP0002",
                                beam_section="RHS 60x40x1.2",
                                brace_section="C 36X21X1.2",
                                base_stiffness="auto"))
    assert (m90.base_plate.b, m90.base_plate.d, m90.base_plate.t) \
        == (100.0, 145.0, 4.0)
    m120 = build_rack(RackConfig(n_bays=1, beam_levels=[1500.0], master=master,
                                 upright_section="UP0022",
                                 beam_section="RHS 122x61x2.0",
                                 brace_section="C 34X34X2.0",
                                 base_stiffness="auto"))
    assert (m120.base_plate.b, m120.base_plate.d, m120.base_plate.t) \
        == (100.0, 176.0, 4.0)


def test_twenty_levels_scalability():
    from rack15512.builder import LevelSpec
    model = build_rack(RackConfig(
        module="back-to-back", n_bays=3,
        levels=[LevelSpec(gap=1000.0) for _ in range(20)],
        frame_height=20500.0))
    assert model.validate() == []
    ids = list(model.nodes)
    assert len(ids) == len(set(ids))            # node-id scheme holds
    beams = {round(model.nodes[m.node_i].z)
             for m in model.members.values()
             if m.member_set == "pallet beams"}
    assert len(beams) == 20
    assert model.splices and model.splices[0].z == pytest.approx(10250.0)


def test_accidental_load_case_and_factor_report():
    """EN 15512 accidental impact loads on the corner upright, combined at
    gamma = 1.0; the report lists every combination with its factors."""
    from rack15512.report import write_report
    model = build_rack(RackConfig(n_bays=1, beam_levels=[1500.0, 3000.0]))
    assert "accidental_x" in model.load_cases
    ax = model.load_cases["accidental_x"].nodal_loads[0]
    assert ax.fx == pytest.approx(1250.0)
    node = model.nodes[ax.node]
    assert (node.x, node.y, node.z) == (0.0, 0.0, 400.0)
    ay = model.load_cases["accidental_y"].nodal_loads[0]
    assert ay.fy == pytest.approx(2500.0)
    co4 = next(c for c in model.combinations if "accX" in c.name)
    assert co4.factors == {"dead": 1.0, "pallets": 1.0, "accidental_x": 1.0}
    assert co4.imp_directions == ["+x"]
    # disabling
    off = build_rack(RackConfig(n_bays=1, beam_levels=[1500.0],
                                accidental_load_x=0.0, accidental_load_y=0.0))
    assert "accidental_x" not in off.load_cases
    # the report names every combination with its load factors
    report = write_report(model, [], [])
    assert "## Load combinations" in report
    assert "1.3 x dead + 1.4 x pallets" in report
    assert "1 x dead + 1 x pallets + 1 x accidental_x" in report


def test_flexural_torsional_buckling_worked_example():
    """EN 15512 worked example upright U1 (100/75/2.5): Ncr,y=492.2 kN,
    Ncr,T=1162 kN (LeT=0.7x95cm), Ncr,FT=373 kN, Nb,Rd,FT=167.3 kN."""
    from rack15512.checks import buckling
    E, G, A, Aeff, fy = 210000.0, 80770.0, 700.0, 640.0, 355.0
    Iy, Iz, It, Iw, y0 = 880000.0, 330000.0, 1200.0, 1.3e9, 60.0
    i0_sq = (Iy + Iz) / A + y0 ** 2
    Ncr_y = buckling.n_cr(E, Iy, 1925.0)
    Ncr_T = buckling.n_cr_torsional(E, G, It, Iw, i0_sq, 0.7 * 950.0)
    Ncr_FT = buckling.n_cr_flex_tors(Ncr_y, Ncr_T, y0, i0_sq)
    chi = buckling.chi(buckling.lambda_bar(Aeff, fy, Ncr_FT), "b")
    Nb = chi * Aeff * fy
    assert Ncr_y / 1e3 == pytest.approx(492.2, rel=0.01)
    assert Ncr_T / 1e3 == pytest.approx(1162.0, rel=0.02)
    assert Ncr_FT / 1e3 == pytest.approx(373.0, rel=0.03)
    assert Nb / 1e3 == pytest.approx(167.3, rel=0.03)


def test_base_plate_en15512_contact_pressure():
    """EN 15512 9.10.1: fj = 2.5 fck/gc; a standard 100x176x4 footplate
    on a 120 upright verifies (the old 0.85 fck method failed it)."""
    master = __import__("rack15512.master_xlsx",
                        fromlist=["load_master"]).load_master(
        os.path.join(os.path.dirname(__file__), "..", "examples",
                     "Master.xlsx"))
    from rack15512.model import BasePlate
    assert BasePlate(f_ck=25.0).bearing_strength() == pytest.approx(41.67,
                                                                    rel=0.01)
    cfg = RackConfig(n_bays=2, beam_levels=[1500.0, 3000.0, 4500.0, 6000.0],
                     master=master, upright_section="UP0016",
                     beam_section="RHS 112x50x2.0",
                     brace_section="C 36X21X1.5", base_stiffness="auto")
    model = build_rack(cfg)
    assert model.base_plate.m_rd_n is not None      # base moment table
    cases = run_all(model)
    checks = run_checks(model, cases)
    plate = max((c for c in checks if c.check == "BASEPLATE"),
                key=lambda c: c.utilization)
    assert plate.ok                                 # 4 mm plate passes
    assert plate.utilization < 1.0


def _anchor_case(reactions, name="ULS1"):
    from rack15512.results import CaseResult
    return CaseResult(name=name, combo=name, kind="ULS", order=2,
                      converged=True, reactions=reactions)


def test_anchor_capacities_m12_5_6():
    """EN 1992-4 per-anchor design resistances for an M12 5.6 wedge anchor,
    hef=70, C25 (default tables): steel tension 21.1 kN, steel shear
    12.6 kN, pull-out 12/1.5=8 kN, concrete cone ~11.1 kN; tension governed
    by pull-out (8 kN), shear by concrete (17/1.5=11.3 kN)."""
    from rack15512.checks.en15512 import _anchor_capacities
    from rack15512.model import BasePlate
    cap = _anchor_capacities(BasePlate(f_ck=25.0, anchor_d=12.0,
                                       anchor_grade="5.6", anchor_hef=70.0))
    assert cap["n_rd_s"] / 1e3 == pytest.approx(21.075, rel=1e-3)
    assert cap["v_rd_s"] / 1e3 == pytest.approx(12.645, rel=1e-3)
    assert cap["n_rd_p"] / 1e3 == pytest.approx(8.0, rel=1e-2)
    assert cap["n_rd_c"] / 1e3 == pytest.approx(11.1, rel=0.02)
    assert cap["n_rd"] == cap["n_rd_p"]          # pull-out governs tension
    assert cap["v_rd"] == cap["v_rd_c"]          # concrete governs shear


def test_anchorage_demand_distribution_and_interaction():
    """2x M12 5.6: 10 kN uplift + 5 kN shear -> N_Ed=5 kN, V_Ed=2.5 kN per
    anchor; betaN=5/8=0.625 governs, combined betaN^1.5+betaV^1.5<betaN."""
    from rack15512.checks.en15512 import _anchorage_checks
    from rack15512.model import BasePlate, RackModel
    m = RackModel()
    m.base_plate = BasePlate(f_ck=25.0, anchor_d=12.0, anchor_grade="5.6",
                             anchor_hef=70.0, n_anchors=2)
    case = _anchor_case({1: (3000.0, 4000.0, -10000.0, 0.0, 0.0, 0.0)})
    res = _anchorage_checks(m, case)
    assert len(res) == 1 and res[0].check == "ANCHORAGE"
    assert res[0].utilization == pytest.approx(0.625, rel=1e-2)
    d = res[0].detail
    assert "M12 5.6 wedge" in d and "pull-out" in d and "betaN" in d
    assert res[0].ok


def test_anchorage_moment_couple_and_overload():
    """A base moment adds tension via M/lever; a large uplift fails the
    pull-out limit (util > 1)."""
    from rack15512.checks.en15512 import _anchorage_checks
    from rack15512.model import BasePlate, RackModel
    m = RackModel()
    m.base_plate = BasePlate(f_ck=25.0, anchor_d=12.0, anchor_grade="5.6",
                             anchor_hef=70.0, n_anchors=2, anchor_spacing=100.0)
    # 4 kN uplift / 2 = 2 kN, plus 0.5 kNm / 0.1 m = 5 kN -> 7 kN per anchor
    case = _anchor_case({1: (0.0, 0.0, -4000.0, 500000.0, 0.0, 0.0)})
    n_ed = 4000.0 / 2 + 500000.0 / 100.0
    assert _anchorage_checks(m, case)[0].utilization == pytest.approx(
        n_ed / 8000.0, rel=1e-2)
    big = _anchor_case({1: (0.0, 0.0, -40000.0, 0.0, 0.0, 0.0)})
    r = _anchorage_checks(m, big)[0]
    assert r.utilization > 1.0 and not r.ok


def test_anchorage_overrides_pull_out_and_shear():
    """User overrides for N_Rk,p / V_Rk,c replace the default table."""
    from rack15512.checks.en15512 import _anchor_capacities
    from rack15512.model import BasePlate
    cap = _anchor_capacities(BasePlate(
        f_ck=25.0, anchor_d=12.0, anchor_grade="5.6", anchor_hef=70.0,
        anchor_pullout_rk=30000.0, anchor_shear_rk=30000.0))
    assert cap["n_rd_p"] / 1e3 == pytest.approx(20.0, rel=1e-3)   # 30/1.5
    assert cap["v_rd_c"] / 1e3 == pytest.approx(20.0, rel=1e-3)


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

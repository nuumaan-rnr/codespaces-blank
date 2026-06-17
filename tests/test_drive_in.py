"""Tests for the multi-deep drive-in / drive-through / radio-shuttle builder
(RSTAB-derived geometry: depth-ladder frames, cantilever arms + rails, rear
spine, top beams, selective plan bracing)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collections import Counter

from rack15512.analysis import run_all
from rack15512.builder import RackConfig, build_rack
from rack15512.checks.en15512 import run_checks


def _cfg(variant, **kw):
    base = dict(system_type="drive_in", di_variant=variant, n_lanes=2, n_deep=3,
                lane_width=1440, pallet_depth=1000, deep_clearance=100,
                arm_length=200, beam_levels=[2400.0, 4900.0],
                frame_height=6000.0, mesh_beam=1, mesh_upright=1)
    base.update(kw)
    return RackConfig(**base)


def _sets(m):
    return Counter(x.member_set for x in m.members.values())


def test_dispatch_and_grid():
    m = build_rack(_cfg("drive_in"))
    up_lines = {(mm.node_i, ) for mm in m.members.values()
                if mm.member_set == "uprights"}
    s = _sets(m)
    assert s["uprights"] > 0 and s["rail beams"] > 0 and s["rail arms"] > 0


def test_spine_by_variant():
    assert _sets(build_rack(_cfg("drive_in")))["spine bracing"] > 0
    assert _sets(build_rack(_cfg("shuttle_lifo")))["spine bracing"] > 0
    assert _sets(build_rack(_cfg("drive_through")))["spine bracing"] == 0
    assert _sets(build_rack(_cfg("shuttle_fifo")))["spine bracing"] == 0


def test_spine_and_plan_bay_selection():
    # both the spine and the plan bracing are selectable by module pattern or
    # an explicit list of bays
    def spine(**kw):
        return _sets(build_rack(_cfg("drive_in", n_lanes=4, **kw)))["spine bracing"]

    def plan(**kw):
        return _sets(build_rack(_cfg("drive_in", n_lanes=4, **kw)))["plan bracing"]

    assert spine(spine_bracing_modules="all") \
        > spine(spine_bracing_modules="alternate") > 0
    assert spine(spine_bracing_module_list=[1]) \
        < spine(spine_bracing_modules="all")
    assert plan(plan_bracing_modules="all") \
        > plan(plan_bracing_module_list=[0]) > 0


def test_rails_on_arms_offset_into_lane():
    m = build_rack(_cfg("drive_in"))
    # rail nodes are offset from the upright lines by arm_length (200)
    up_x = {round(n.x) for nid, n in m.nodes.items()
            if any(mm.member_set == "uprights" and nid in (mm.node_i, mm.node_j)
                   for mm in m.members.values())}
    rail_x = set()
    for mm in m.members.values():
        if mm.member_set == "rail beams":
            rail_x.add(round(m.nodes[mm.node_i].x))
    assert rail_x and not (rail_x & up_x)        # rails are offset, not on uprights


def test_plan_bracing_selective():
    m = build_rack(_cfg("drive_in"))
    s = _sets(m)
    # selective: far fewer plan members than 2 per (lane x depth) cell
    assert 0 < s["plan bracing"] < 2 * 2 * 3


def test_gravity_runs_and_checks():
    m = build_rack(_cfg("drive_in"))
    cases = run_all(m)
    assert cases and all(c.converged for c in cases)
    checks = run_checks(m, cases)
    codes = {c.check for c in checks}
    assert {"STRESS", "BUCKLING", "DEFLECTION"} <= codes
    assert any("accidental" in c.name for c in m.combinations)
    # the rail (support beam) gets its own deflection check (EN 15620 L/200)
    assert any(c.check == "DEFLECTION" and c.member_set == "rail beams"
               for c in checks)


def test_pallet_load_smeared_over_full_rail():
    # the per-rail pallet load (n_deep * weight/2) is smeared as a UNIFORM UDL
    # over the full lane-deep rail length (frames no longer sit one-per-pallet)
    m = build_rack(_cfg("drive_in", n_lanes=2, n_deep=2, weight_per_pallet=8000.0,
                        frame_depth=1000.0, n_frames=2, pallet_depth=900.0,
                        deep_clearance=100.0, beam_levels=[2400.0, 4900.0]))
    lane_deep = 900.0 * 2 + 3 * 100.0                  # = 2100 mm
    w_udl = 2 * (8000.0 / 2) / lane_deep               # n_deep * wt/2 / lane_deep
    full = m.load_cases["pallets"].member_loads
    assert {round(abs(ml.qz), 4) for ml in full} == {round(w_udl, 4)}  # uniform
    # total applied load = every pallet's weight (n_lanes * n_deep * wt * levels)
    tot = sum(abs(ml.qz) * m.member_length(m.members[ml.member]) for ml in full)
    assert abs(tot - 2 * 2 * 8000.0 * 2) < 1.0


def test_base_springs_and_connectors():
    m = build_rack(_cfg("drive_in", base_stiffness=4.8e8))
    # semi-rigid floor connection in the down-aisle direction (ry) only; the
    # cross-aisle (rx) base is pinned (braced depth frames)
    assert m.supports and all(s.ry == 4.8e8 and s.rx is False
                              for s in m.supports)
    # cantilever rail-arm bracket connector = RSTAB Konsole hinge (1.0e6 N*mm/rad)
    arms = [mm for mm in m.members.values() if mm.member_set == "rail arms"]
    assert arms and all(a.hinge_i is not None and a.hinge_i.rz == 1.0e6
                        for a in arms)
    # top portal + rear down-aisle beams keep their semi-rigid connectors
    pb = [mm for mm in m.members.values() if mm.member_set == "portal beams"]
    assert pb and all(b.hinge_i is not None and b.hinge_j is not None
                      for b in pb)


def test_default_base_stiffness_calculated_from_r899():
    # with no master the drive-in floor connection is CALCULATED from the R899
    # formulas (concrete Eq43 in series with upright Eq46), applied down-aisle
    # (ry); cross-aisle (rx) stays braced.  No pinned fallback, no over-stiff
    # 5.0e8 default.  An explicit value still overrides.
    from rack15512.base_stiffness import derived_base_stiffness
    m = build_rack(_cfg("drive_in"))                 # default base_stiffness
    assert m.supports
    assert m.base_stiffness_source == "calculated (R899)"
    ups = [mm for mm in m.members.values() if mm.member_set == "uprights"]
    up = m.sections[ups[0].section]
    E = m.materials[up.material].E
    expect = derived_base_stiffness(up, E, 2400.0)   # first beam level of _cfg
    assert all(abs(s.ry - expect) < 1.0 and s.rx is False and s.rz is False
               for s in m.supports)
    assert 1.6e7 <= expect <= 2.4e8                  # in the measured band
    cases = run_all(m)
    assert all(c.converged for c in cases)           # still stable
    # an explicit numeric base stiffness is still honoured
    m2 = build_rack(_cfg("drive_in", base_stiffness=3.0e8))
    assert all(s.ry == 3.0e8 for s in m2.supports)
    assert m2.base_stiffness_source == "explicit"


def test_top_and_back_beams_independent():
    # the top (frame-top) and back (rear, per-level) beams are separate member
    # sets and can take different connector stiffness
    m = build_rack(_cfg("drive_in", di_variant="drive_in",
                        top_connector_stiffness=6.16e7,
                        back_connector_stiffness=3.0e7))
    top = [mm for mm in m.members.values() if mm.member_set == "portal beams"]
    back = [mm for mm in m.members.values() if mm.member_set == "back beams"]
    assert top and back                                   # both present (LIFO)
    assert all(b.hinge_i.rz == 6.16e7 for b in top)
    assert all(b.hinge_i.rz == 3.0e7 for b in back)


def test_beam_connector_auto_from_section():
    # with no explicit override, the beam connector stiffness is taken
    # automatically from the selected beam section's connector_k (master data)
    from rack15512.library import SectionLibrary
    lib = SectionLibrary.bundled()
    bn = lib.names("beam")[0]
    lib.get(bn).connector_k = 6.16e7
    m = build_rack(_cfg("drive_in", n_lanes=2, n_deep=2, portal_section=bn,
                        top_connector_stiffness=None, library=lib))
    top = [mm for mm in m.members.values() if mm.member_set == "portal beams"]
    assert top and all(b.hinge_i.rz == 6.16e7 for b in top)


def test_rstab_load_cases_and_combos():
    """The drive-in load scheme mirrors the client RSTAB model (sheets 2.1/2.5):
    full + alternate-lane + pattern + top pay-load cases, placement and forklift
    accidental cases, and a per-direction ULS proof + SLS combination set."""
    m = build_rack(_cfg("drive_in", n_lanes=3))
    lcs = set(m.load_cases)
    assert {"dead", "pallets", "pallets_alt1", "pallets_alt2", "pallets_pattern",
            "pallets_top", "placement", "placement_y", "impact_x",
            "impact_y"} <= lcs
    # RSTAB accidental magnitudes: 1.25 kN down-aisle (X), 2.5 kN cross-aisle (Y)
    assert abs(m.load_cases["impact_x"].nodal_loads[0].fx - 1250.0) < 1e-6
    assert abs(m.load_cases["impact_y"].nodal_loads[0].fy - 2500.0) < 1e-6
    # alternate lanes partition the full pay load (RSTAB LC12 ∪ LC13 = LC2)
    full = {ml.member for ml in m.load_cases["pallets"].member_loads}
    a1 = {ml.member for ml in m.load_cases["pallets_alt1"].member_loads}
    a2 = {ml.member for ml in m.load_cases["pallets_alt2"].member_loads}
    assert a1 | a2 == full and not (a1 & a2)
    # per-direction proof + SLS combos, both X and Y; SLS keeps the imperfection
    names = {c.name for c in m.combinations}
    for d in ("X", "Y"):
        assert {f"ULS-pay-{d}", f"ULS-placement-{d}", f"ULS-accidental-{d}",
                f"ULS-pattern-{d}", f"ULS-anchor-{d}", f"SLS-sway-{d}"} <= names
    assert all(c.imperfection for c in m.combinations if c.kind == "SLS")


def test_accidental_applied_at_strike_height_on_front_face():
    """RSTAB applies the forklift impact ~400 mm above the floor on a front-face
    upright — not snapped to a rail level."""
    m = build_rack(_cfg("drive_in", accidental_height=400.0,
                        beam_levels=[2400.0, 4900.0]))
    n = m.nodes[m.load_cases["impact_x"].nodal_loads[0].node]
    assert abs(n.z - 400.0) < 1e-6                     # at the strike height
    assert n.z not in (2400.0, 4900.0)                 # not a rail level
    assert abs(n.y - max(nn.y for nn in m.nodes.values())) < 1e-6   # front face


def test_per_direction_imperfection():
    m = build_rack(_cfg("drive_in"))
    # down-aisle 1/300, cross-aisle 1/200 -> different EHF magnitudes
    assert m.imperfection.value_for("+y") > m.imperfection.value_for("+x")


def test_seismic_cases_generated():
    m = build_rack(_cfg("drive_in", n_lanes=1, n_deep=1, n_frames=2,
                        frame_depth=400.0, beam_levels=[2000.0],
                        frame_height=3000.0, seismic=True, seismic_n_modes=3))
    assert m.seismic is not None and m.seismic.enabled
    cases = run_all(m)
    assert any(c.kind == "SEISMIC" for c in cases)
    assert all(c.converged for c in cases)


def test_deep_dimension():
    # lane deep = pallet_depth*n_deep + (n_deep+1)*clearance (storage envelope);
    # n_frames frames of frame_depth fit within it with auto gaps
    m = build_rack(_cfg("drive_in", n_deep=6, n_frames=4, frame_depth=1100.0,
                        pallet_depth=1200.0, deep_clearance=50.0))
    ys = [n.y for n in m.nodes.values()]
    assert max(ys) == 1200.0 * 6 + 7 * 50.0               # 7550, the lane deep
    # 4 frames -> 3 gaps of (7550 - 4*1100)/3 = 1050 mm; second leg-pair at 2150
    leg_ys = sorted({round(y) for y in ys})
    assert leg_ys[:4] == [0, 1100, 2150, 3250]


def test_deep_too_many_frames_raises():
    import pytest
    with pytest.raises(ValueError):
        build_rack(_cfg("drive_in", n_deep=2, n_frames=6, frame_depth=1100.0,
                        pallet_depth=1000.0, deep_clearance=50.0))


def test_built_up_end_columns():
    # opt-in boxed end columns: tagged "end columns", verified by BUILT_UP
    # (EN 1993-1-1 6.4) and excluded from the single-section STRESS/BUCKLING
    m = build_rack(_cfg("drive_in", built_up_end_columns=True,
                        built_up_arrangement="battened", built_up_h0=120.0,
                        built_up_panel=600.0))
    assert _sets(m)["end columns"] > 0
    assert m.built_up is not None and m.built_up.target_set == "end columns"
    cases = run_all(m)
    checks = run_checks(m, cases)
    kinds = {c.check for c in checks}
    assert "BUILT_UP" in kinds
    # end columns must not appear under the single-section checks
    for c in checks:
        if c.member_set == "end columns":
            assert c.check not in ("STRESS", "BUCKLING")


def test_no_built_up_by_default():
    m = build_rack(_cfg("drive_in"))
    assert m.built_up is None
    assert _sets(m)["end columns"] == 0


def test_upright_downaisle_effective_length_is_full_height():
    # the down-aisle (local z) upright effective length is the full frame height
    # (K=1.0, pinned-pinned) - the conservative worst case; cross-aisle (local y)
    # stays the braced bracing pitch.
    H = 6000.0
    m = build_rack(_cfg("drive_in", frame_height=H))
    ups = [mm for mm in m.members.values() if mm.member_set == "uprights"]
    assert ups
    assert all(mm.L_buckling_z == H for mm in ups)
    # cross-aisle: D bracing (default) -> Lcr = 2 x bracing_pitch = 1200
    assert all(mm.L_buckling_y == 1200.0 for mm in ups)
    # X bracing -> Lcr = bracing_pitch
    mx = build_rack(_cfg("drive_in", frame_height=H, bracing_type="X"))
    upx = [mm for mm in mx.members.values() if mm.member_set == "uprights"]
    assert all(mm.L_buckling_y == 600.0 for mm in upx)


def test_drivein_sections_are_shear_flexible():
    # the RSTAB drive-in rail and cantilever arm carry shear areas so the FEA
    # builds Timoshenko (shear-flexible) elements
    m = build_rack(_cfg("drive_in"))
    rail = m.sections["DRIVE-IN RAIL 2.5"]
    arm = m.sections["UU30x190x3 arm"]
    assert rail.Avy and rail.Avz and rail.It_gross
    assert arm.Avy and arm.Avz and arm.It_gross


def test_drivein_report_section():
    # the report carries a drive-in-specific verification section (rail/arm
    # deflection, down-aisle effective length, sway) that selective racks omit
    from rack15512.report import drivein_summary, is_drive_in, write_report
    from rack15512.report_html import design_validation_report
    m = build_rack(_cfg("drive_in"))
    cases = run_all(m)
    checks = run_checks(m, cases)
    assert is_drive_in(m)
    d = drivein_summary(m, checks)
    assert d is not None and d["Lcr_z"] == d["H"]   # down-aisle = 1.0H
    assert d["base_source"] == "calculated (R899)"
    labels = {row[0] for row in d["rows"]}
    assert any("rail deflection" in s for s in labels)
    assert any("Down-aisle frame sway" in s for s in labels)
    md = write_report(m, cases, checks)
    assert "## Drive-in verification" in md
    html = design_validation_report(m, cases, checks, {})
    assert "Drive-in verification" in html
    assert "Drive-in / multi-deep racking" in html


def test_frames_have_gaps():
    # frame bracing only within the 2-leg frames, not in the pallet gaps
    m = build_rack(_cfg("drive_in", n_deep=3, frame_depth=1100.0,
                        pallet_depth=1000.0, deep_clearance=100.0))
    # brace Y midpoints: should cluster in frame bays (0-1100, 2200-3300, ...)
    ymid = sorted({round((m.nodes[mm.node_i].y + m.nodes[mm.node_j].y) / 2)
                   for mm in m.members.values() if mm.member_set == "bracing"})
    # no brace spans a gap bay (e.g. 1100-2200 -> midpoint ~1650)
    assert all(not (1101 < y < 2199) for y in ymid)

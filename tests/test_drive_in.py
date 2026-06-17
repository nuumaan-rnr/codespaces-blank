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


def test_per_pallet_load_on_deep_bays():
    # multi-deep load is per pallet: each deep (gap) bay carries one pallet,
    # shared by its two side rails (weight_per_pallet / 2 on each)
    m = build_rack(_cfg("drive_in", n_lanes=2, n_deep=2, weight_per_pallet=8000.0,
                        frame_depth=1000.0, pallet_depth=900.0,
                        deep_clearance=100.0, beam_levels=[2400.0, 4900.0]))
    full = m.load_cases["pallets"].member_loads
    per_member = {round(abs(ml.qz) * m.member_length(m.members[ml.member]), 1)
                  for ml in full}
    assert per_member == {4000.0}                     # weight_per_pallet / 2
    # only deep bays loaded: 4 rails (2 per lane) x 2 deep x 2 levels
    assert len(full) == 4 * 2 * 2


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
    m = build_rack(_cfg("drive_in", n_lanes=1, n_deep=1, beam_levels=[2000.0],
                        frame_height=3000.0, seismic=True, seismic_n_modes=3))
    assert m.seismic is not None and m.seismic.enabled
    cases = run_all(m)
    assert any(c.kind == "SEISMIC" for c in cases)
    assert all(c.converged for c in cases)


def test_deep_dimension():
    # depth = n_deep*(frame_depth + gap) + frame_depth; frames are 2-leg ladders
    m = build_rack(_cfg("drive_in", n_deep=3, frame_depth=1100.0,
                        pallet_depth=1000.0, deep_clearance=100.0))
    ys = [n.y for n in m.nodes.values()]
    assert max(ys) == 3 * (1100.0 + 1100.0) + 1100.0      # 7700, the RSTAB depth


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


def test_upright_downaisle_effective_length_from_eigenvalue():
    # the down-aisle (local z) upright effective length is taken from the
    # critical-upright buckling eigenvalue (FEM 10.2.07), NOT the full frame
    # height - the engine already runs the 2nd-order sway, so K=1.0 full height
    # would double-count it (over-conservative).
    H = 6000.0
    m = build_rack(_cfg("drive_in", frame_height=H, base_stiffness=5.0e8))
    ups = [mm for mm in m.members.values() if mm.member_set == "uprights"]
    assert ups
    lz = {round(mm.L_buckling_z) for mm in ups}
    assert len(lz) == 1                       # all uprights share one length
    lcr = lz.pop()
    assert 0 < lcr < H                         # below full height (less conservative)
    # cross-aisle stays the braced bracing pitch
    assert all(mm.L_buckling_y == 600.0 for mm in ups)


def test_eigenvalue_effective_length_responds_to_base_spring():
    from rack15512.buckling_eig import column_effective_length
    H, E, Iz = 6000.0, 210000.0, 1.2e6
    free = column_effective_length([2400.0, 4900.0], H, E, Iz, A=2000.0,
                                   k_base=0.0)
    stiff = column_effective_length([2400.0, 4900.0], H, E, Iz, A=2000.0,
                                    k_base=5.0e8)
    assert free and stiff
    assert 0 < free <= H and 0 < stiff <= H
    assert stiff < free                        # a stiffer base shortens L_cr


def test_eigenvalue_recovers_euler_pinned_pinned():
    # a single top load on a pinned base / sway-held top is the Euler
    # pinned-pinned column: L_cr -> H (within a few percent on a meshed model)
    from rack15512.buckling_eig import column_effective_length
    H, E, Iz = 4000.0, 210000.0, 1.0e6
    lcr = column_effective_length([H], H, E, Iz, A=2000.0, k_base=0.0, mesh=10)
    assert lcr and abs(lcr - H) / H < 0.05


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
    assert d is not None and d["Lcr_z"] and d["Lcr_z"] < d["H"]
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

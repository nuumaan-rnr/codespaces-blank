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
    codes = {c.check for c in run_checks(m, cases)}
    assert {"STRESS", "BUCKLING", "DEFLECTION"} <= codes
    assert any("impact" in c.name for c in m.combinations)


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


def test_frames_have_gaps():
    # frame bracing only within the 2-leg frames, not in the pallet gaps
    m = build_rack(_cfg("drive_in", n_deep=3, frame_depth=1100.0,
                        pallet_depth=1000.0, deep_clearance=100.0))
    # brace Y midpoints: should cluster in frame bays (0-1100, 2200-3300, ...)
    ymid = sorted({round((m.nodes[mm.node_i].y + m.nodes[mm.node_j].y) / 2)
                   for mm in m.members.values() if mm.member_set == "bracing"})
    # no brace spans a gap bay (e.g. 1100-2200 -> midpoint ~1650)
    assert all(not (1101 < y < 2199) for y in ymid)

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
    m = build_rack(_cfg("drive_in", n_deep=6, pallet_depth=1200.0,
                        deep_clearance=50.0))
    ys = [n.y for n in m.nodes.values()]
    assert max(ys) == 6 * (1200.0 + 50.0)

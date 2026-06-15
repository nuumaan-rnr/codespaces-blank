"""Tests for the multi-deep drive-in / drive-through / radio-shuttle builder."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collections import Counter

from rack15512.analysis import run_all
from rack15512.builder import RackConfig, build_rack
from rack15512.checks.en15512 import run_checks


def _cfg(variant, **kw):
    return RackConfig(system_type="drive_in", di_variant=variant,
                      n_lanes=2, n_deep=4,
                      beam_levels=[1500.0, 3000.0, 4500.0],
                      frame_height=5000.0, **kw)


def _sets(m):
    return Counter(x.member_set for x in m.members.values())


def test_dispatch_and_grid():
    m = build_rack(_cfg("drive_in"))
    # uprights on a (n_lanes+1) x (n_deep+1) grid, full height
    up_lines = {(n // 1_000_000, (n // 1_000) % 1_000)
                for nid in m.members for n in
                ((m.members[nid].node_i,) if m.members[nid].member_set
                 == "uprights" else ())}
    assert len(up_lines) == (2 + 1) * (4 + 1)
    assert _sets(m)["rail beams"] > 0


def test_spine_by_variant():
    assert _sets(build_rack(_cfg("drive_in")))["spine bracing"] > 0
    assert _sets(build_rack(_cfg("shuttle_lifo")))["spine bracing"] > 0
    assert _sets(build_rack(_cfg("drive_through")))["spine bracing"] == 0
    assert _sets(build_rack(_cfg("shuttle_fifo")))["spine bracing"] == 0


def test_shuttle_has_level_beams_drivein_does_not():
    assert _sets(build_rack(_cfg("shuttle_lifo")))["level beams"] > 0
    assert _sets(build_rack(_cfg("drive_in")))["level beams"] == 0


def test_open_faces_have_fewer_rails():
    # drive-through (both faces open) drops a rail bay at front AND rear
    di = _sets(build_rack(_cfg("drive_in")))["rail beams"]
    dt = _sets(build_rack(_cfg("drive_through")))["rail beams"]
    assert dt < di


def test_plan_bracing_present():
    assert _sets(build_rack(_cfg("drive_in")))["plan bracing"] > 0


def test_gravity_runs_and_checks():
    m = build_rack(_cfg("drive_in"))
    cases = run_all(m)
    assert cases and all(c.converged for c in cases)
    checks = run_checks(m, cases)
    codes = {c.check for c in checks}
    assert {"STRESS", "BUCKLING", "DEFLECTION"} <= codes
    # impact load cases are generated
    assert any("impact" in c.name for c in m.combinations)


def test_deep_dimension():
    cfg = RackConfig(system_type="drive_in", di_variant="drive_in",
                     n_lanes=2, n_deep=6, pallet_depth=1200.0,
                     deep_clearance=50.0, beam_levels=[1500.0, 3000.0],
                     frame_height=3500.0)
    m = build_rack(cfg)
    ys = [n.y for n in m.nodes.values()]
    assert max(ys) == 6 * (1200.0 + 50.0)        # n_deep pitch positions

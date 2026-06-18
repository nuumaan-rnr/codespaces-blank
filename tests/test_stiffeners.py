"""Upright stiffener as a PARTIAL-COMPOSITE built-up member: a separate member
on its own (offset) centroid, tied to the upright at bolt rows by interface
links (transverse stiff, vertical = bolt shear stiffness)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rack15512.analysis import run_all
from rack15512.builder import RackConfig, build_rack
from rack15512.checks.en15512 import run_checks, upright_set_buckling_rows

_HEAVY = dict(module="single", n_bays=3, beam_levels=[1800.0, 3600.0, 5400.0],
              depth=1000.0, frame_height=6000.0, bracing_pitch=600.0,
              upright_section="UP-100x100x2.0", pallet_load_per_level=26000.0)
_RH = 1800.0
_STIFF = "UP-100x100x2.0"


def _reinf(**extra):
    return build_rack(RackConfig(**_HEAVY, stiffener_section=_STIFF,
                                 reinforce_height=_RH, **extra))


def test_disabled_by_default():
    m = build_rack(RackConfig(**_HEAVY))
    assert not m.links
    assert not any(mm.member_set == "upright stiffeners"
                   for mm in m.members.values())


def test_separate_offset_members_and_links():
    m = _reinf(stiffener_offset=30.0, stiffener_type=1)
    assert m.validate() == []
    st = [mm for mm in m.members.values()
          if mm.member_set == "upright stiffeners"]
    assert st                                    # separate stiffener members
    assert m.links                               # interface links present
    # stiffener nodes are offset 30 mm in cross-aisle (Y) from the upright
    SNID = 8_000_000
    snode = next(nd for nid, nd in m.nodes.items() if nid >= SNID)
    up = m.nodes[snode.id - SNID]
    assert abs(abs(snode.y - up.y) - 30.0) < 1e-6 and abs(snode.z - up.z) < 1e-6
    assert "upright stiffeners" in m.checks.buckling_sets


def test_axial_split_is_below_half_and_shear_lag():
    m = _reinf(stiffener_offset=30.0, stiffener_type=1, stiffener_shear_k=50000.0)
    cases = run_all(m)
    st = [(mid, mm) for mid, mm in m.members.items()
          if mm.member_set == "upright stiffeners"]

    def nmin(mid):
        return min((c.members[mid].N_min for c in cases if mid in c.members),
                   default=0.0)
    # stiffener axial near the base vs near the top of the reinforced zone
    by_z = sorted(((min(m.nodes[mm.node_i].z, m.nodes[mm.node_j].z), nmin(mid))
                   for mid, mm in st), key=lambda t: t[0])
    base_n = abs(by_z[0][1])
    top_n = abs(by_z[-1][1])
    assert base_n > top_n * 1.5                  # shear-lag: builds from the top
    # split: the stiffener carries clearly LESS than half (never 50%)
    up_base = abs(min(c.members[mid].N_min for c in cases
                      for mid, mm in m.members.items()
                      if mm.member_set == "uprights" and mid in c.members
                      and max(m.nodes[mm.node_i].z, m.nodes[mm.node_j].z) <= _RH))
    share = base_n / (base_n + up_base)
    assert 0.1 < share < 0.45                    # realistic, not 50%


def test_buckling_reduces_without_moment_spike():
    def low(**extra):
        m = build_rack(RackConfig(**_HEAVY, **extra))
        rows = upright_set_buckling_rows(m, run_checks(m, run_all(m)))
        return max((r for r in rows if "base" in r["set"]),
                   key=lambda r: r["util"])
    bare = low()
    reinf = low(stiffener_section=_STIFF, reinforce_height=_RH,
                stiffener_offset=30.0, stiffener_type=1)
    assert reinf["util"] < bare["util"]          # buckling reduced
    assert reinf["My_kNm"] <= bare["My_kNm"] + 0.1   # no induced moment


def test_solver_converges_both_types():
    for typ in (1, 2):
        m = _reinf(stiffener_offset=30.0, stiffener_type=typ)
        cases = run_all(m)
        assert cases and all(c.converged for c in cases if c.kind != "SEISMIC")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))

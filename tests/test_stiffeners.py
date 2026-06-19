"""Upright stiffener as a PARTIAL-COMPOSITE built-up member: a separate member
on its own (offset) centroid, tied to the upright at bolt rows by interface
links (transverse stiff, vertical = bolt shear stiffness)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rack15512.analysis import run_all
from rack15512.builder import RackConfig, build_rack, _closed_upright_section
from rack15512.checks.en15512 import (_chi_ft, run_checks,
                                      upright_set_buckling_rows)
from rack15512.model import CrossSection, Steel

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


def _open_upright_with_ft():
    """A lipped-channel upright carrying gross FT data from the master: small
    St-Venant torsion, sizeable warping, shear-centre offset from the centroid
    (so flexural-torsional buckling can govern)."""
    return CrossSection(
        name="UP-OC", material="S355", A=600.0, Iy=1.0e6, Iz=0.9e6,
        J=800.0, Wely=2.0e4, Welz=1.8e4, A_eff=540.0, buckling_curve_y="b",
        t=2.0, width_b=100.0, depth_h=100.0,
        It_gross=800.0, Iw_gross=2.5e9, y0=35.0)


def test_closed_section_reduces_warping_and_centres_shear_centre():
    up = _open_upright_with_ft()
    closed = _closed_upright_section("UP-OC~closed", up)
    # St-Venant torsion jumps (closed cell, Bredt); warping collapses; the
    # shear centre moves onto the centroid.
    assert closed.It_gross > up.It_gross * 100
    assert closed.Iw_gross < up.Iw_gross * 0.1
    assert closed.y0 == 0.0
    # the flexural section is untouched (composite gain lives on the stiffener).
    assert closed.A == up.A and closed.Iy == up.Iy and closed.Iz == up.Iz


def test_type1_closed_beats_open_on_ft():
    """With master FT data, the open upright is penalised by flexural-torsional
    buckling; closing the face (Type 1) lifts the FT reduction factor so the
    closed section is governed by ordinary flexural buckling instead."""
    mat = Steel(name="S355")
    up = _open_upright_with_ft()
    closed = _closed_upright_section("UP-OC~closed", up)
    length, ncr_y = 3000.0, 250.0e3
    chi_open = _chi_ft(up, mat, length, ncr_y)
    chi_closed = _chi_ft(closed, mat, length, ncr_y)
    assert chi_open is not None and chi_closed is not None
    assert chi_closed > chi_open                 # Type 1 FT credit is real


def test_mount_offset_from_section_overrides_config():
    """When the selected stiffener carries a mount_offset (from the master), the
    builder places the stiffener node at that distance, NOT the global config
    offset; the direction is still set automatically by the type."""
    from rack15512.builder import _pick
    from rack15512.library import SectionLibrary
    lib = SectionLibrary.bundled()
    lib.get(_pick(lib, _STIFF, "upright")).mount_offset = 42.0
    m = build_rack(RackConfig(**_HEAVY, library=lib, stiffener_section=_STIFF,
                              reinforce_height=_RH, stiffener_offset=30.0,
                              stiffener_type=1))
    SNID = 8_000_000
    sn = next(nd for nid, nd in m.nodes.items() if nid >= SNID)
    up = m.nodes[sn.id - SNID]
    assert abs(abs(sn.y - up.y) - 42.0) < 1e-6      # section value, not 30


def test_solver_converges_both_types():
    for typ in (1, 2):
        m = _reinf(stiffener_offset=30.0, stiffener_type=typ)
        cases = run_all(m)
        assert cases and all(c.converged for c in cases if c.kind != "SEISMIC")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))

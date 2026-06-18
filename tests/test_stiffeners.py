"""Upright stiffener as a MONOLITHIC combined section (parallel-axis about the
combined centroid), assigned to the reinforced lower upright segments."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rack15512.analysis import run_all
from rack15512.builder import RackConfig, build_rack
from rack15512.checks.en15512 import run_checks, upright_set_buckling_rows
from rack15512.composite import combined_section

_BASE = dict(n_bays=1, beam_levels=[1500.0, 3000.0], depth=1000.0,
             frame_height=3600.0)
_RH = 1500.0
_STIFF = "UP-100x100x2.0"          # a valid upright-role section name


def _build(**extra):
    return build_rack(RackConfig(**_BASE, **extra))


def test_stiffener_disabled_by_default():
    m = _build()
    assert m.checks.buckling_sets == ["uprights"]
    assert not any("@" in s for s in m.sections)        # no combined section


def test_combined_section_parallel_axis():
    m0 = _build()
    up = m0.sections["UP-100x100x2.0"]
    c30 = combined_section("c30", up, up, 30.0, up.material)
    c50 = combined_section("c50", up, up, 50.0, up.material)
    assert abs(c30.A - 2 * up.A) < 1e-6                  # areas add
    # parallel-axis: combined cross-aisle Iy exceeds the simple sum, more so for
    # the larger offset
    assert c30.Iy > 2 * up.Iy
    assert c50.Iy > c30.Iy
    assert abs(c30.Iz - 2 * up.Iz) < 1e-6               # down-aisle: simple sum
    assert c30.J > 0                                     # validate() needs J>0


def test_combined_section_assigned_to_lower_uprights():
    m = _build(stiffener_section=_STIFF, reinforce_height=_RH,
               stiffener_offset=30.0)
    assert m.validate() == []
    cnames = [s for s in m.sections if "@30" in s]
    assert cnames                                        # combined section made
    cname = cnames[0]
    low = [mm for mm in m.members.values() if mm.member_set == "uprights"
           and max(m.nodes[mm.node_i].z, m.nodes[mm.node_j].z) <= _RH + 1e-6]
    high = [mm for mm in m.members.values() if mm.member_set == "uprights"
            and min(m.nodes[mm.node_i].z, m.nodes[mm.node_j].z) >= _RH - 1e-6]
    assert low and all(mm.section == cname for mm in low)     # reinforced
    assert high and all(mm.section != cname for mm in high)   # plain above


def test_stiffener_reduces_buckling_without_moment_spike():
    """The composite section must LOWER the lower-zone upright buckling util and
    must NOT introduce a spurious moment."""
    heavy = dict(n_bays=3, beam_levels=[1800.0, 3600.0, 5400.0], depth=1000.0,
                 frame_height=6000.0, upright_section="UP-100x100x2.0",
                 pallet_load_per_level=26000.0)

    def low_row(**extra):
        m = build_rack(RackConfig(**heavy, **extra))
        rows = upright_set_buckling_rows(m, run_checks(m, run_all(m)))
        return max((r for r in rows if "base" in r["set"]),
                   key=lambda r: r["util"])

    bare = low_row()
    reinf = low_row(stiffener_section="UP-100x100x2.0", reinforce_height=1800.0,
                    stiffener_offset=30.0)
    assert reinf["util"] < bare["util"]                  # buckling reduced
    assert reinf["My_kNm"] <= bare["My_kNm"] + 0.05      # no induced moment


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))

"""Load-chart generator (rack15512.loadcharts) sanity checks."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rack15512 import loadcharts as lc
from rack15512.master_xlsx import load_master

_MASTER = os.path.join(os.path.dirname(__file__), "..", "examples",
                       "Master_Template_FINAL_mount_offset.xlsx")


def _lib():
    return load_master(_MASTER).library


def test_combined_section_parallel_axis_gain():
    lib = _lib()
    up = lib.get("UP0012")                       # 90-deep -> IN_STIFFENER90X1.6
    st = lib.get("IN_STIFFENER90X1.6")
    comb = lc.combined_upright_section(up, st, st.mount_offset or 30.0)
    assert comb.A == up.A + st.A
    assert comb.area_eff == up.area_eff + st.area_eff
    # cross-aisle inertia gains the parallel-axis (lever) term
    assert comb.Iy > up.Iy + st.Iy
    assert comb.Iz == up.Iz + st.Iz
    # closed-cell torsion credit carried over (It up, y0 -> 0)
    assert comb.It_gross and comb.It_gross > (up.It_gross or up.J)
    assert comb.y0 == 0.0


def test_upright_capacity_monotone_in_lcr_da():
    lib = _lib()
    up = lib.get("UP0012")
    caps = [lc.upright_capacity_kN(up, 355.0, da, 500.0)[0] for da in lc.UP_DA]
    assert all(caps[i] >= caps[i + 1] - 1e-6 for i in range(len(caps) - 1))
    assert all(c > 0 for c in caps)


def test_D_below_X_when_cross_aisle_governs_and_XS_above():
    lib = _lib()
    up = lib.get("UP0012")
    st = lib.get("IN_STIFFENER90X1.6")
    comb = lc.combined_upright_section(up, st, st.mount_offset or 30.0)
    # short down-aisle -> cross-aisle governs: D (Lcr_CA=1000) < X (Lcr_CA=500)
    x_500 = lc.upright_capacity_kN(up, 355.0, 250.0, 500.0)[0]
    d_1000 = lc.upright_capacity_kN(up, 355.0, 250.0, 1000.0)[0]
    xs_500 = lc.upright_capacity_kN(comb, 355.0, 250.0, 500.0)[0]
    assert d_1000 < x_500                         # D weaker (longer cross-aisle)
    assert xs_500 > x_500                         # internal stiffener helps


def test_beam_capacity_positive_decreasing_and_thicker_upright_stronger():
    lib = _lib()
    beam = lib.get("RHS112X50X1.6")
    curves = lc._beam_thickness_curves(beam)
    assert len(curves) >= 2                       # per-thickness connector data
    # capacity decreases with span and stays positive
    loads = [lc.beam_level_capacity_kN(beam, 310.0, L, curves[0][1],
                                       beam.connector_m_rd)[0]
             for L in lc.BEAM_SPAN]
    assert all(l > 0 for l in loads)
    assert all(loads[i] >= loads[i + 1] - 1e-6 for i in range(len(loads) - 1))
    # at a mid span, a thicker upright (stiffer connector) gives >= capacity
    span = 2000.0
    vals = [lc.beam_level_capacity_kN(beam, 310.0, span, k, beam.connector_m_rd)[0]
            for _, k in curves]
    assert vals == sorted(vals)
    # long spans are deflection-governed, short spans bending-governed
    assert lc.beam_level_capacity_kN(beam, 310.0, 500.0, curves[0][1],
                                     beam.connector_m_rd)[1] == "bending"
    assert lc.beam_level_capacity_kN(beam, 310.0, 4000.0, curves[0][1],
                                     beam.connector_m_rd)[1] == "deflection"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))

"""Tests for the calculated (R899) down-aisle base rotational stiffness used
when no tested floor-connection table is available."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rack15512.base_stiffness import concrete_modulus, derived_base_stiffness
from rack15512.model import CrossSection


def _upright():
    # 100x100x2.0-like upright: down-aisle Iz = 1.2e6 mm^4, 100x100 footprint
    return CrossSection(name="UP", material="steel", A=780.0, Iy=9.8e5,
                        Iz=1.2e6, J=5.0e4, Wely=2.0e4, Welz=2.0e4,
                        depth_h=100.0, width_b=100.0)


def test_concrete_modulus_en1992():
    # E_cm = 22000*((f_ck+8)/10)^0.3; C25 -> ~31.5 GPa
    assert abs(concrete_modulus(25.0) - 31476.0) < 50.0
    assert concrete_modulus(40.0) > concrete_modulus(25.0)


def test_derived_in_measured_band_and_series_near_kh():
    up = _upright()
    E, h = 210000.0, 1600.0
    k = derived_base_stiffness(up, E, h)
    # R899 Eq 46 upright term alone
    k_h = E * up.Iz / h
    assert k > 0
    assert 1.6e7 <= k <= 2.4e8                  # measured 16-242 kNm/rad band
    # the concrete term is much stiffer, so the series is governed by k_h
    assert k < k_h and k > 0.9 * k_h


def test_shorter_first_beam_gives_stiffer_base():
    up = _upright()
    E = 210000.0
    assert derived_base_stiffness(up, E, 1200.0) > derived_base_stiffness(up, E, 2400.0)


def test_falls_back_to_upright_term_without_plan_dims():
    up = _upright()
    up.depth_h = None
    up.width_b = None
    E, h = 210000.0, 1600.0
    assert abs(derived_base_stiffness(up, E, h) - E * up.Iz / h) < 1.0

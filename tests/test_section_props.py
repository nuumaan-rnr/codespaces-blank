"""Validate the thin-walled section-property calculator against closed-form
sections.  These pin the error-prone shear-centre / warping math:

  * doubly-symmetric I  -> shear centre at the centroid, Cw = t b^3 h^2 / 24;
  * plain channel       -> shear-centre offset e = 3 b^2 / (h + 6 b) from web.
"""

import math

import pytest

from rack15512.section_props import thin_walled_properties


def _i_section(b, h, t):
    """Doubly-symmetric I, midline model (flanges width b at y=+/-h/2, web h)."""
    nodes = {1: (-b / 2, h / 2), 2: (0.0, h / 2), 3: (b / 2, h / 2),
             4: (0.0, -h / 2), 5: (-b / 2, -h / 2), 6: (b / 2, -h / 2)}
    elems = [(1, 2, t), (2, 3, t),          # top flange
             (2, 4, t),                      # web
             (5, 4, t), (4, 6, t)]           # bottom flange
    return nodes, elems


def test_i_section_matches_closed_form():
    b, h, t = 60.0, 120.0, 2.0
    p = thin_walled_properties(*_i_section(b, h, t))
    assert p.A == pytest.approx((2 * b + h) * t)
    assert p.Ix == pytest.approx(b * t * h ** 2 / 2 + t * h ** 3 / 12, rel=1e-9)
    assert p.Iy == pytest.approx(t * b ** 3 / 6, rel=1e-9)
    assert p.J == pytest.approx((2 * b + h) * t ** 3 / 3, rel=1e-9)
    # doubly symmetric: shear centre at the centroid, no product of inertia
    assert p.xc == pytest.approx(0.0, abs=1e-9)
    assert p.x_sc == pytest.approx(0.0, abs=1e-6)
    assert p.y_sc == pytest.approx(0.0, abs=1e-6)
    assert p.Ixy == pytest.approx(0.0, abs=1e-6)
    # warping constant: Cw = Iy h^2 / 4 = t b^3 h^2 / 24
    assert p.Cw == pytest.approx(t * b ** 3 * h ** 2 / 24, rel=1e-6)
    assert not p.closed


def _channel(b, h, t, n=1):
    """Plain channel: web (x=0, y=-h/2..h/2), flanges in +x at y=+/-h/2."""
    nodes = {1: (0.0, h / 2), 2: (0.0, -h / 2),
             3: (b, h / 2), 4: (b, -h / 2)}
    elems = [(1, 2, t),                      # web
             (1, 3, t),                      # top flange
             (2, 4, t)]                      # bottom flange
    return nodes, elems


def test_channel_shear_centre_offset():
    b, h, t = 60.0, 120.0, 2.0
    p = thin_walled_properties(*_channel(b, h, t))
    # centroid sits toward the flanges: x_c = b^2 / (2b + h)
    assert p.xc == pytest.approx(b ** 2 / (2 * b + h), rel=1e-9)
    assert p.yc == pytest.approx(0.0, abs=1e-9)
    # shear centre lies on the far side of the web: x_abs = -3 b^2 / (h + 6 b)
    e = 3 * b ** 2 / (h + 6 * b)
    assert p.xc + p.x_sc == pytest.approx(-e, rel=1e-6)
    assert p.y_sc == pytest.approx(0.0, abs=1e-6)


def test_principal_axes_of_symmetric_section():
    p = thin_walled_properties(*_i_section(60.0, 120.0, 2.0))
    # Ix > Iy here, principal axis aligned with x -> theta ~ 0
    assert p.I_major == pytest.approx(p.Ix, rel=1e-9)
    assert p.I_minor == pytest.approx(p.Iy, rel=1e-9)
    assert abs(p.theta) < 1e-6


def test_i0_about_shear_centre():
    b, h, t = 60.0, 120.0, 2.0
    p = thin_walled_properties(*_i_section(b, h, t))
    expect = math.sqrt((p.Ix + p.Iy) / p.A)      # shear centre at centroid
    assert p.i0 == pytest.approx(expect, rel=1e-9)

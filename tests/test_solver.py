"""Verification of the internal engine against closed-form solutions."""

import math

import pytest

from rackapp.config import RackConfig, SectionConfig
from rackapp.engine_internal import InternalEngine
from rackapp.loads import Combination, LineLoad, LoadCase, PointLoad
from rackapp.model import Hinge, Member, Node, RackModel, Support

E = 210e9
SEC = SectionConfig(name="t", A=1e-3, Iy=1e-6, Wy=1e-5)


def _beam_model(k_end=None, support_ry=0.0) -> RackModel:
    """Single 4 m horizontal member on two supports.

    support_ry: 0.0 -> pinned node, None -> rotation clamped (so an end
    hinge spring k_end acts between the beam end and rigid ground).
    """
    m = RackModel(name="beam", E=E)
    m.nodes = {1: Node(1, 0.0, 0.0), 2: Node(2, 4.0, 0.0)}
    h = Hinge(k_end) if k_end is not None else None
    m.members = {1: Member(1, 1, 2, "beam", SEC, hinge_i=h, hinge_j=h)}
    m.supports = [Support(1, support_ry), Support(2, support_ry)]
    m.member_sets = {"beams": [1], "uprights": []}
    return m


def _solve(model, lc, second_order=False):
    eng = InternalEngine()
    combo = Combination("C1", "test", {"LC": 1.0}, second_order, "ULS")
    return eng.analyze(model, {"LC": lc}, [combo]).combos["C1"]


def test_simply_supported_udl():
    """SS beam, UDL: M_mid = qL^2/8, delta = 5qL^4/(384EI)."""
    model = _beam_model()
    q = 5e3  # N/m downwards
    lc = LoadCase("LC", "udl", line_loads=[LineLoad(1, -q)])
    r = _solve(model, lc).members[1]
    L = 4.0
    assert r.M_span_max == pytest.approx(q * L**2 / 8, rel=1e-6)
    assert r.defl_rel_max == pytest.approx(5 * q * L**4 / (384 * E * SEC.Iy), rel=0.01)
    # end moments ~ 0 at pinned supports
    assert abs(r.M1) < 1.0 and abs(r.M2) < 1.0


def test_semi_rigid_end_moments_between_pinned_and_fixed():
    """End moment of a UDL beam with equal end springs:
    M_end = qL^2/12 * 1/(1 + 2EI/(kL))  (slope-deflection closed form)."""
    q, L = 5e3, 4.0
    k = 2.0 * E * SEC.Iy / L  # spring of similar magnitude to beam stiffness
    model = _beam_model(k_end=k, support_ry=None)
    lc = LoadCase("LC", "udl", line_loads=[LineLoad(1, -q)])
    r = _solve(model, lc).members[1]
    m_expected = q * L**2 / 12 / (1 + 2 * E * SEC.Iy / (k * L))
    assert abs(r.M1) == pytest.approx(m_expected, rel=1e-4)
    assert 0 < abs(r.M1) < q * L**2 / 12


def test_cantilever_tip_load():
    """Clamped column with horizontal tip load: u = PH^3/(3EI)."""
    m = RackModel(name="cant", E=E)
    H = 3.0
    m.nodes = {1: Node(1, 0.0, 0.0), 2: Node(2, 0.0, H)}
    m.members = {1: Member(1, 1, 2, "upright", SEC)}
    m.supports = [Support(1, None)]  # RIGID base
    m.member_sets = {"uprights": [1], "beams": []}
    P = 1e3
    lc = LoadCase("LC", "tip", point_loads=[PointLoad(2, fx=P)])
    r = _solve(m, lc)
    assert r.nodes[2].ux == pytest.approx(P * H**3 / (3 * E * SEC.Iy), rel=1e-6)
    assert r.reactions[1].fx == pytest.approx(-P, rel=1e-6)
    assert abs(r.reactions[1].my) == pytest.approx(P * H, rel=1e-6)


def test_second_order_amplification():
    """Cantilever with axial load P: tip deflection under lateral load h is
    amplified roughly by 1/(1 - P/Pcr)."""
    m = RackModel(name="cant", E=E)
    H = 3.0
    m.nodes = {1: Node(1, 0.0, 0.0), 2: Node(2, 0.0, H)}
    m.members = {1: Member(1, 1, 2, "upright", SEC)}
    m.supports = [Support(1, None)]
    m.member_sets = {"uprights": [1], "beams": []}

    p_cr = math.pi**2 * E * SEC.Iy / (2 * H) ** 2
    P = 0.3 * p_cr
    h = 500.0
    lc = LoadCase("LC", "l", point_loads=[PointLoad(2, fx=h, fz=-P)])

    r1 = _solve(m, lc, second_order=False).nodes[2].ux
    r2 = _solve(m, lc, second_order=True)
    assert r2.converged
    amplification = r2.nodes[2].ux / r1
    assert amplification == pytest.approx(1.0 / (1.0 - 0.3), rel=0.05)


def test_axial_force_from_gravity():
    """Vertical member with self-weight type line load carries axial force."""
    m = RackModel(name="col", E=E)
    m.nodes = {1: Node(1, 0.0, 0.0), 2: Node(2, 0.0, 2.0)}
    m.members = {1: Member(1, 1, 2, "upright", SEC)}
    m.supports = [Support(1, None)]
    m.member_sets = {"uprights": [1], "beams": []}
    w = 100.0  # N/m down
    lc = LoadCase("LC", "sw", line_loads=[LineLoad(1, -w)])
    r = _solve(m, lc)
    # base reaction carries the full weight
    assert r.reactions[1].fz == pytest.approx(w * 2.0, rel=1e-6)
    # compression at the base end
    assert r.members[1].N_max_compression == pytest.approx(w * 2.0, rel=1e-6)

"""Verification of the internal 3D engine against closed-form solutions."""

import math

import pytest

from rackapp.config import SectionConfig
from rackapp.engine_internal import InternalEngine
from rackapp.loads import Combination, LineLoad, LoadCase, PointLoad
from rackapp.model import Hinge, Member, Node, RackModel, Support

E = 210e9
G = 81e9
SEC = SectionConfig(name="t", A=1e-3, Iy=1e-6, Wy=1e-5, Iz=4e-7, Wz=5e-6, J=2e-7)


def _model() -> RackModel:
    return RackModel(name="test", E=E, G=G)


def _beam_model(k_end=None, support_ry=0.0) -> RackModel:
    """Single 4 m member along X on two supports.

    support_ry: 0.0 -> pinned node, None -> rotation clamped (so an end
    hinge spring k_end acts between the beam end and rigid ground).
    """
    m = _model()
    m.nodes = {1: Node(1, 0.0, 0.0, 0.0), 2: Node(2, 4.0, 0.0, 0.0)}
    h = Hinge(my=k_end) if k_end is not None else None
    m.members = {1: Member(1, 1, 2, "beam", SEC, hinge_i=h, hinge_j=h)}
    m.supports = [Support(1, support_ry, None), Support(2, support_ry, None)]
    m.member_sets = {"beams": [1], "uprights": [], "braces": []}
    return m


def _cantilever(H=3.0) -> RackModel:
    m = _model()
    m.nodes = {1: Node(1, 0.0, 0.0, 0.0), 2: Node(2, 0.0, 0.0, H)}
    m.members = {1: Member(1, 1, 2, "upright", SEC)}
    m.supports = [Support(1, None, None)]
    m.member_sets = {"uprights": [1], "beams": [], "braces": []}
    return m


def _solve(model, lc, second_order=False):
    eng = InternalEngine()
    combo = Combination("C1", "test", {"LC": 1.0}, second_order, "ULS")
    return eng.analyze(model, {"LC": lc}, [combo]).combos["C1"]


def test_simply_supported_udl():
    """SS beam, UDL: My_mid = qL^2/8, delta = 5qL^4/(384 E Iy)."""
    model = _beam_model()
    q = 5e3  # N/m downwards
    lc = LoadCase("LC", "udl", line_loads=[LineLoad(1, -q)])
    r = _solve(model, lc).members[1]
    L = 4.0
    assert r.My_span_max == pytest.approx(q * L**2 / 8, rel=1e-6)
    assert r.defl_rel_max == pytest.approx(5 * q * L**4 / (384 * E * SEC.Iy), rel=0.01)
    assert abs(r.My1) < 1.0 and abs(r.My2) < 1.0


def test_semi_rigid_end_moments():
    """End moment of a UDL beam with equal end springs k to rigid ground:
    M_end = qL^2/12 * 1/(1 + 2EI/(kL))  (slope-deflection closed form)."""
    q, L = 5e3, 4.0
    k = 2.0 * E * SEC.Iy / L
    model = _beam_model(k_end=k, support_ry=None)
    lc = LoadCase("LC", "udl", line_loads=[LineLoad(1, -q)])
    r = _solve(model, lc).members[1]
    m_expected = q * L**2 / 12 / (1 + 2 * E * SEC.Iy / (k * L))
    assert abs(r.My1) == pytest.approx(m_expected, rel=1e-4)
    assert 0 < abs(r.My1) < q * L**2 / 12


def test_cantilever_both_axes():
    """Vertical cantilever, tip loads: u = PH^3/(3EI) per axis with the
    correct inertia (Iy for X loading, Iz for Y loading)."""
    H, P = 3.0, 1e3
    m = _cantilever(H)
    lc = LoadCase("LC", "tip", point_loads=[PointLoad(2, fx=P, fy=P)])
    r = _solve(m, lc)
    # X (down-aisle) bending governed by Iy; Y (cross-aisle) by Iz
    assert r.nodes[2].ux == pytest.approx(P * H**3 / (3 * E * SEC.Iy), rel=1e-6)
    assert r.nodes[2].uy == pytest.approx(P * H**3 / (3 * E * SEC.Iz), rel=1e-6)
    assert r.reactions[1].fx == pytest.approx(-P, rel=1e-6)
    assert r.reactions[1].fy == pytest.approx(-P, rel=1e-6)
    # base moments: about Y from X load, about X from Y load
    assert abs(r.reactions[1].my) == pytest.approx(P * H, rel=1e-6)
    assert abs(r.reactions[1].mx) == pytest.approx(P * H, rel=1e-6)
    # member moments appear about BOTH local axes (biaxial)
    mr = r.members[1]
    assert mr.My_abs_max == pytest.approx(P * H, rel=1e-6)
    assert mr.Mz_abs_max == pytest.approx(P * H, rel=1e-6)


def test_second_order_amplification_both_planes():
    """Cantilever with axial load 0.3*Pcr per axis: lateral deflection is
    amplified roughly by 1/(1 - P/Pcr) in BOTH bending planes."""
    H, h = 3.0, 500.0
    for axis, I in (("x", SEC.Iy), ("y", SEC.Iz)):
        m = _cantilever(H)
        p_cr = math.pi**2 * E * I / (2 * H) ** 2
        P = 0.3 * p_cr
        load = {"fx": h} if axis == "x" else {"fy": h}
        lc = LoadCase("LC", "l", point_loads=[PointLoad(2, fz=-P, **load)])
        u1 = getattr(_solve(m, lc, second_order=False).nodes[2], "u" + axis)
        r2 = _solve(m, lc, second_order=True)
        assert r2.converged
        u2 = getattr(r2.nodes[2], "u" + axis)
        assert u2 / u1 == pytest.approx(1.0 / 0.7, rel=0.05)


def test_axial_force_from_gravity():
    """Vertical member with self-weight line load carries axial force."""
    m = _cantilever(2.0)
    w = 100.0  # N/m down
    lc = LoadCase("LC", "sw", line_loads=[LineLoad(1, -w)])
    r = _solve(m, lc)
    assert r.reactions[1].fz == pytest.approx(w * 2.0, rel=1e-6)
    assert r.members[1].N_max_compression == pytest.approx(w * 2.0, rel=1e-6)


def test_truss_braced_frame():
    """Two columns + truss diagonal: the diagonal carries the lateral load
    as axial force (frame action negligible with pinned column bases)."""
    m = _model()
    B, H = 1.0, 1.0
    m.nodes = {1: Node(1, 0.0, 0.0, 0.0), 2: Node(2, B, 0.0, 0.0),
               3: Node(3, 0.0, 0.0, H), 4: Node(4, B, 0.0, H)}
    m.members = {
        1: Member(1, 1, 3, "upright", SEC),
        2: Member(2, 2, 4, "upright", SEC),
        3: Member(3, 3, 4, "brace", SEC, behavior="truss"),   # top strut
        4: Member(4, 1, 4, "brace", SEC, behavior="truss"),   # diagonal
    }
    # ry pinned (test plane); rx clamped so there is no out-of-plane mechanism
    m.supports = [Support(1, 0.0, None), Support(2, 0.0, None)]
    m.member_sets = {"uprights": [1, 2], "beams": [], "braces": [3, 4]}
    P = 1e3
    lc = LoadCase("LC", "lat", point_loads=[PointLoad(3, fx=P)])
    r = _solve(m, lc)
    # diagonal axial force ~ P / cos(45) in tension (load path via strut)
    diag = r.members[4]
    expected = P * math.sqrt(B**2 + H**2) / B
    assert diag.N1 == pytest.approx(expected, rel=0.02)
    # truss members carry no bending
    assert diag.My_abs_max < 1e-6
    assert r.members[3].N1 == pytest.approx(-P, rel=0.02)  # strut compression


def test_beam_connector_spring_transfers_moment():
    """A beam hung between two clamped stubs via My springs transfers
    moments consistent with the spring stiffness (not pinned, not rigid)."""
    q, L = 5e3, 4.0
    k = 110e3
    rigid = _beam_model(k_end=None, support_ry=None)
    spring = _beam_model(k_end=k, support_ry=None)
    pinned = _beam_model(k_end=0.0, support_ry=None)
    lc = LoadCase("LC", "udl", line_loads=[LineLoad(1, -q)])
    m_rigid = abs(_solve(rigid, lc).members[1].My1)
    m_spring = abs(_solve(spring, lc).members[1].My1)
    m_pinned = abs(_solve(pinned, lc).members[1].My1)
    assert m_pinned < 1e-6
    assert 0.0 < m_spring < m_rigid
    assert m_rigid == pytest.approx(q * L**2 / 12, rel=1e-4)

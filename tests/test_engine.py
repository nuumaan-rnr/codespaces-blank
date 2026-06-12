"""Engine validation against closed-form solutions."""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rack15512.combos import AssembledLoads
from rack15512.engine.opensees import OpenSeesEngine
from rack15512.model import (CrossSection, Hinge, Member, RackModel, Steel,
                             Support)

E = 210000.0
A = 1000.0
I = 2.0e6


def base_model() -> RackModel:
    m = RackModel()
    m.materials["S355"] = Steel("S355", E=E, fy=355.0)
    m.sections["SEC"] = CrossSection("SEC", "S355", A=A, I=I, Wel=I / 50.0)
    return m


def run(model, loads, order=1):
    return OpenSeesEngine().run_case(model, loads, name="t", combo="t",
                                     kind="ULS", order=order)


def test_cantilever_tip_load():
    """Tip deflection PL^3/3EI, base moment PL."""
    m = base_model()
    L, P = 2000.0, 1000.0
    m.add_node(1, 0, 0)
    m.add_node(2, 0, L)
    m.add_member(1, 1, 2, "SEC", mesh=4)
    m.supports.append(Support(1, True, True, True))
    loads = AssembledLoads()
    loads.add_nodal(2, P, 0, 0)
    r = run(m, loads)
    assert r.converged
    d = r.displacements[2][0]
    assert d == pytest.approx(P * L**3 / (3 * E * I), rel=1e-6)
    mr = r.members[1]
    assert mr.M_absmax == pytest.approx(P * L, rel=1e-6)
    assert r.reactions[1][0] == pytest.approx(-P, rel=1e-6)


def test_ss_beam_udl():
    """Simply supported beam, UDL: M_mid = wL^2/8 (sagging positive),
    midspan deflection 5wL^4/384EI, end shear wL/2."""
    m = base_model()
    L, w = 3000.0, 10.0           # N/mm downward
    m.add_node(1, 0, 0)
    m.add_node(2, L, 0)
    m.add_member(1, 1, 2, "SEC", mesh=4)
    m.supports.append(Support(1, True, True, False))
    m.supports.append(Support(2, False, True, False))
    loads = AssembledLoads()
    loads.add_member(1, 0.0, -w)
    r = run(m, loads)
    assert r.converged
    mr = r.members[1]
    mid = [s for s in mr.stations if abs(s.x - L / 2) < 1e-6][0]
    assert mid.M == pytest.approx(w * L**2 / 8, rel=1e-6)      # sagging +
    assert mid.defl == pytest.approx(-5 * w * L**4 / (384 * E * I), rel=1e-3)
    assert mr.V_absmax == pytest.approx(w * L / 2, rel=1e-6)
    assert r.reactions[1][1] == pytest.approx(w * L / 2, rel=1e-6)


def test_beam_with_rotational_end_springs():
    """SS beam + UDL with equal end springs k: end moment
    M_end = wL^2/12 * 1/(1 + 2EI/(kL)) (standard semi-rigid result)."""
    m = base_model()
    L, w = 2700.0, 8.0
    k = 1.0e8     # N*mm/rad, typical rack connector order of magnitude
    m.add_node(1, 0, 0)
    m.add_node(2, L, 0)
    m.add_member(1, 1, 2, "SEC", mesh=4,
                 hinge_i=Hinge(k), hinge_j=Hinge(k))
    m.supports.append(Support(1, True, True, True))
    m.supports.append(Support(2, False, True, True))
    loads = AssembledLoads()
    loads.add_member(1, 0.0, -w)
    r = run(m, loads)
    assert r.converged
    M_end_expected = w * L**2 / 12 / (1 + 2 * E * I / (k * L))
    mr = r.members[1]
    assert abs(mr.M_end("i")) == pytest.approx(M_end_expected, rel=1e-6)
    # zero spring stiffness must reproduce the pinned case
    m.members[1].hinge_i = Hinge(0.0)
    m.members[1].hinge_j = Hinge(0.0)
    r2 = run(m, loads)
    mid = [s for s in r2.members[1].stations if abs(s.x - L / 2) < 1e-6][0]
    assert mid.M == pytest.approx(w * L**2 / 8, rel=1e-6)


def test_spring_support_rotation():
    """Cantilever column with rotational spring base, moment H*L at base:
    extra tip displacement = H*L^2/k_rot."""
    m = base_model()
    L, H, krot = 2000.0, 500.0, 5.0e8
    m.add_node(1, 0, 0)
    m.add_node(2, 0, L)
    m.add_member(1, 1, 2, "SEC", mesh=2)
    m.supports.append(Support(1, True, True, krot))
    loads = AssembledLoads()
    loads.add_nodal(2, H, 0, 0)
    r = run(m, loads)
    assert r.converged
    d_expected = H * L**3 / (3 * E * I) + (H * L) * L / krot
    assert r.displacements[2][0] == pytest.approx(d_expected, rel=1e-6)
    assert r.reactions[1][2] == pytest.approx(-H * L, rel=1e-5)


def test_truss_axial():
    m = base_model()
    L, P = 1500.0, 2000.0
    m.add_node(1, 0, 0)
    m.add_node(2, L, 0)
    m.add_member(1, 1, 2, "SEC", mtype="truss")
    m.supports.append(Support(1, True, True, False))
    m.supports.append(Support(2, False, True, False))
    loads = AssembledLoads()
    loads.add_nodal(2, P, 0, 0)
    r = run(m, loads)
    assert r.converged
    assert r.displacements[2][0] == pytest.approx(P * L / (E * A), rel=1e-6)
    assert r.members[1].N_max == pytest.approx(P, rel=1e-6)


def test_second_order_sway_amplification():
    """Cantilever column, axial P + lateral H.  Second-order tip sway
    ~ first-order * 1/(1 - P/Pcr) for moderate P/Pcr."""
    m = base_model()
    L, H = 3000.0, 100.0
    Pcr = math.pi**2 * E * I / (2 * L) ** 2
    P = 0.3 * Pcr
    m.add_node(1, 0, 0)
    m.add_node(2, 0, L)
    m.add_member(1, 1, 2, "SEC", mesh=8)
    m.supports.append(Support(1, True, True, True))
    loads = AssembledLoads()
    loads.add_nodal(2, H, -P, 0)
    r1 = run(m, loads, order=1)
    r2 = run(m, loads, order=2)
    assert r1.converged and r2.converged
    d1 = r1.displacements[2][0]
    d2 = r2.displacements[2][0]
    amplification = d2 / d1
    # exact amplification for this case is (tan(u)-u)*3/u^3 with
    # u = (pi/2)*sqrt(P/Pcr); the 1/(1-P/Pcr) approximation is within ~2%
    assert amplification == pytest.approx(1.0 / (1.0 - P / Pcr), rel=0.03)
    assert amplification > 1.3
    # base moment must include the P-delta contribution
    M_base = abs(r2.members[1].M_end("i"))
    assert M_base == pytest.approx(H * L + P * d2, rel=0.02)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

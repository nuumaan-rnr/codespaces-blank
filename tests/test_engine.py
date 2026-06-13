"""3D engine validation against closed-form solutions."""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rack15512.combos import AssembledLoads
from rack15512.engine.opensees import OpenSeesEngine
from rack15512.model import (CrossSection, Hinge, Member, RackModel, Steel,
                             Support)

E = 210000.0
G = 81000.0
A = 1000.0
IY = 1.0e6
IZ = 2.0e6
J = 5.0e5


def base_model() -> RackModel:
    m = RackModel()
    m.materials["S355"] = Steel("S355", E=E, fy=355.0, G=G)
    m.sections["SEC"] = CrossSection("SEC", "S355", A=A, Iy=IY, Iz=IZ, J=J,
                                     Wely=IY / 50.0, Welz=IZ / 50.0)
    return m


def run(model, loads, order=1):
    return OpenSeesEngine().run_case(model, loads, name="t", combo="t",
                                     kind="ULS", order=order)


FIX_ALL = dict(ux=True, uy=True, uz=True, rx=True, ry=True, rz=True)


def test_cantilever_both_planes_and_torsion():
    """Vertical cantilever (upright), tip loads in X and Y + torque.
    Default upright axes: local y = +X (Iz bends down-aisle), local
    z = +Y (Iy bends cross-aisle)."""
    m = base_model()
    L, Px, Py, T = 2000.0, 1000.0, 600.0, 5.0e5
    m.add_node(1, 0, 0, 0)
    m.add_node(2, 0, 0, L)
    m.add_member(1, 1, 2, "SEC", mesh=4)
    m.supports.append(Support(1, **FIX_ALL))
    loads = AssembledLoads()
    loads.add_nodal(2, Px, Py, 0.0, 0.0, 0.0, T)
    r = run(m, loads)
    assert r.converged
    d = r.displacements[2]
    assert d[0] == pytest.approx(Px * L**3 / (3 * E * IZ), rel=1e-6)
    assert d[1] == pytest.approx(Py * L**3 / (3 * E * IY), rel=1e-6)
    assert d[5] == pytest.approx(T * L / (G * J), rel=1e-6)
    mr = r.members[1]
    assert mr.Mz_absmax == pytest.approx(Px * L, rel=1e-6)
    assert mr.My_absmax == pytest.approx(Py * L, rel=1e-6)
    assert mr.T_absmax == pytest.approx(T, rel=1e-6)
    # internal moments vanish at the free end
    tip = mr.end("j")
    assert abs(tip.Mz) < 1e-3 * Px * L
    assert abs(tip.My) < 1e-3 * Py * L
    # reactions
    assert r.reactions[1][0] == pytest.approx(-Px, rel=1e-6)
    assert r.reactions[1][1] == pytest.approx(-Py, rel=1e-6)


def test_ss_beam_udl_gravity():
    """Horizontal beam along X under gravity UDL: local y is vertical, so
    Mz_mid = wL^2/8 (sagging positive), defl = 5wL^4/384EIz."""
    m = base_model()
    L, w = 3000.0, 10.0           # N/mm downward (-Z)
    m.add_node(1, 0, 0, 0)
    m.add_node(2, L, 0, 0)
    m.add_member(1, 1, 2, "SEC", mesh=4)
    m.supports.append(Support(1, ux=True, uy=True, uz=True,
                              rx=True, ry=False, rz=False))
    m.supports.append(Support(2, ux=False, uy=True, uz=True,
                              rx=True, ry=False, rz=False))
    loads = AssembledLoads()
    loads.add_member(1, 0.0, 0.0, -w)
    r = run(m, loads)
    assert r.converged
    mr = r.members[1]
    mid = [s for s in mr.stations if abs(s.x - L / 2) < 1e-6][0]
    assert mid.Mz == pytest.approx(w * L**2 / 8, rel=1e-6)      # sagging +
    assert mid.defl_y == pytest.approx(-5 * w * L**4 / (384 * E * IZ), rel=1e-3)
    assert mr.V_absmax == pytest.approx(w * L / 2, rel=1e-6)
    assert r.reactions[1][2] == pytest.approx(w * L / 2, rel=1e-6)


def test_ss_beam_udl_lateral():
    """Same beam loaded laterally (+Y = local -z): bending about local y,
    |My|_mid = wL^2/8, deflection via Iy."""
    m = base_model()
    L, w = 3000.0, 10.0
    m.add_node(1, 0, 0, 0)
    m.add_node(2, L, 0, 0)
    m.add_member(1, 1, 2, "SEC", mesh=4)
    m.supports.append(Support(1, ux=True, uy=True, uz=True,
                              rx=True, ry=False, rz=False))
    m.supports.append(Support(2, ux=False, uy=True, uz=True,
                              rx=True, ry=False, rz=False))
    loads = AssembledLoads()
    loads.add_member(1, 0.0, w, 0.0)
    r = run(m, loads)
    assert r.converged
    mr = r.members[1]
    mid = [s for s in mr.stations if abs(s.x - L / 2) < 1e-6][0]
    assert abs(mid.My) == pytest.approx(w * L**2 / 8, rel=1e-6)
    assert abs(mid.defl_z) == pytest.approx(5 * w * L**4 / (384 * E * IY),
                                            rel=1e-3)
    # moment must vanish at the pinned ends and be continuous
    assert abs(mr.end("i").My) < 1.0
    assert abs(mr.end("j").My) < 1.0


def test_beam_with_rotational_end_springs():
    """SS beam + gravity UDL with equal end springs k about local z:
    M_end = wL^2/12 * 1/(1 + 2EIz/(kL))."""
    m = base_model()
    L, w = 2700.0, 8.0
    k = 1.0e8     # N*mm/rad, typical rack connector order of magnitude
    m.add_node(1, 0, 0, 0)
    m.add_node(2, L, 0, 0)
    m.add_member(1, 1, 2, "SEC", mesh=4,
                 hinge_i=Hinge(rz=k), hinge_j=Hinge(rz=k))
    m.supports.append(Support(1, **FIX_ALL))
    m.supports.append(Support(2, ux=False, uy=True, uz=True,
                              rx=True, ry=True, rz=True))
    loads = AssembledLoads()
    loads.add_member(1, 0.0, 0.0, -w)
    r = run(m, loads)
    assert r.converged
    M_end_expected = w * L**2 / 12 / (1 + 2 * E * IZ / (k * L))
    mr = r.members[1]
    assert abs(mr.end("i").Mz) == pytest.approx(M_end_expected, rel=1e-6)
    assert abs(mr.end("j").Mz) == pytest.approx(M_end_expected, rel=1e-6)
    # released hinge (rz=0) must reproduce the simply supported case
    m.members[1].hinge_i = Hinge(rz=0.0)
    m.members[1].hinge_j = Hinge(rz=0.0)
    r2 = run(m, loads)
    mid = [s for s in r2.members[1].stations if abs(s.x - L / 2) < 1e-6][0]
    assert mid.Mz == pytest.approx(w * L**2 / 8, rel=1e-5)


def test_spring_support_rotation():
    """Upright with rotational spring base loaded in X: extra tip sway
    = (H*L)*L/k_ry (rotation about global Y resists X-sway)."""
    m = base_model()
    L, H, krot = 2000.0, 500.0, 5.0e8
    m.add_node(1, 0, 0, 0)
    m.add_node(2, 0, 0, L)
    m.add_member(1, 1, 2, "SEC", mesh=2)
    m.supports.append(Support(1, ux=True, uy=True, uz=True,
                              rx=True, ry=krot, rz=True))
    loads = AssembledLoads()
    loads.add_nodal(2, H, 0.0, 0.0)
    r = run(m, loads)
    assert r.converged
    d_expected = H * L**3 / (3 * E * IZ) + (H * L) * L / krot
    assert r.displacements[2][0] == pytest.approx(d_expected, rel=1e-6)
    assert abs(r.reactions[1][4]) == pytest.approx(H * L, rel=1e-5)


def test_truss_axial():
    m = base_model()
    L, P = 1500.0, 2000.0
    m.add_node(1, 0, 0, 0)
    m.add_node(2, L, 0, 0)
    m.add_member(1, 1, 2, "SEC", mtype="truss")
    m.supports.append(Support(1, **FIX_ALL))
    m.supports.append(Support(2, ux=False, uy=True, uz=True))
    loads = AssembledLoads()
    loads.add_nodal(2, P, 0.0, 0.0)
    r = run(m, loads)
    assert r.converged
    assert r.displacements[2][0] == pytest.approx(P * L / (E * A), rel=1e-6)
    assert r.members[1].N_max == pytest.approx(P, rel=1e-6)


def test_second_order_sway_amplification():
    """Upright, axial P + lateral H: second-order tip sway
    ~ first-order * 1/(1 - P/Pcr)."""
    m = base_model()
    L, H = 3000.0, 100.0
    Pcr = math.pi**2 * E * IZ / (2 * L) ** 2
    P = 0.3 * Pcr
    m.add_node(1, 0, 0, 0)
    m.add_node(2, 0, 0, L)
    m.add_member(1, 1, 2, "SEC", mesh=8)
    m.supports.append(Support(1, **FIX_ALL))
    loads = AssembledLoads()
    loads.add_nodal(2, H, 0.0, -P)
    r1 = run(m, loads, order=1)
    r2 = run(m, loads, order=2)
    assert r1.converged and r2.converged
    d1 = r1.displacements[2][0]
    d2 = r2.displacements[2][0]
    amplification = d2 / d1
    assert amplification == pytest.approx(1.0 / (1.0 - P / Pcr), rel=0.03)
    assert amplification > 1.3
    # base moment must include the P-delta contribution
    M_base = abs(r2.members[1].end("i").Mz)
    assert M_base == pytest.approx(H * L + P * d2, rel=0.02)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

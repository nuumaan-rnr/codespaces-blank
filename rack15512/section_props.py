"""Thin-walled open-section properties from a CUFSM-style node/element mesh.

Computes the full cross-section property set CUFSM/CUTWP reports - area, second
moments, St-Venant torsion, **warping constant, shear centre and the polar
radius of gyration about the shear centre** - from the section midline (nodes +
strip elements).  These are exactly the gross-section quantities EN 15512 9.7.5
needs for flexural-torsional buckling (It, Iw, y0, i0), which are otherwise
estimated or left blank in the master.

Model: piecewise-linear midline, one "line" per element with thickness t (the
thin-walled line model - the t**3/12 self term is neglected for bending, kept
only for the St-Venant torsion Sum(L*t**3/3)).  Valid for **open** sections
(no closed cells); rack uprights qualify.  A consistent unit system is assumed
throughout (this package uses N, mm).

The shear-centre / warping derivation is the standard sectorial-area method and
is verified in tests against closed-form sections (doubly-symmetric I: shear
centre at the centroid and Cw = Iy*h**2/4; plain channel: the tabulated shear-
centre offset).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

__all__ = ["SectionProperties", "thin_walled_properties",
           "thickness_weighted_centroid", "recenter_to_centroid"]


@dataclass
class SectionProperties:
    """Full thin-walled section property set (consistent units, e.g. mm)."""

    A: float                 # area [L^2]
    xc: float                # centroid x [L]
    yc: float                # centroid y [L]
    Ix: float                # 2nd moment about centroidal x-axis (int y^2) [L^4]
    Iy: float                # 2nd moment about centroidal y-axis (int x^2) [L^4]
    Ixy: float               # product of inertia (int x*y) [L^4]
    I1: float                # major principal 2nd moment [L^4]
    I2: float                # minor principal 2nd moment [L^4]
    theta: float             # principal-axis angle from x [rad]
    J: float                 # St-Venant torsion constant Sum(L t^3/3) [L^4]
    Cw: float                # warping constant about the shear centre [L^6]
    x_sc: float              # shear-centre x, from the centroid [L]
    y_sc: float              # shear-centre y, from the centroid [L]
    i0: float                # polar radius of gyration about the shear centre [L]
    closed: bool = False     # True if a closed cell was detected (method n/a)

    @property
    def I_major(self) -> float:
        return self.I1

    @property
    def I_minor(self) -> float:
        return self.I2


def _line_int_1(t, L, fa, fb):
    """Integral of a linear field f along a strip: int f t ds."""
    return t * L * (fa + fb) / 2.0


def _line_int_2(t, L, fa, fb, ga, gb):
    """Integral of two linear fields: int f*g t ds (f from fa->fb, g ga->gb)."""
    return t * L * (2.0 * fa * ga + 2.0 * fb * gb + fa * gb + fb * ga) / 6.0


def _line_int_sq(t, L, fa, fb):
    """Integral of a squared linear field: int f^2 t ds."""
    return t * L * (fa * fa + fa * fb + fb * fb) / 3.0


def thin_walled_properties(nodes: Dict[int, Tuple[float, float]],
                           elems: Sequence[Tuple[int, int, float]]
                           ) -> SectionProperties:
    """Compute the section properties from a node/element midline mesh.

    Parameters
    ----------
    nodes : ``{node_id: (x, y)}`` midline coordinates.
    elems : sequence of ``(node_i, node_j, thickness)`` strip elements.

    Returns a :class:`SectionProperties`.  Open sections only; if a closed cell
    is found the area/inertia/J are still valid but the shear centre / Cw use an
    open-section traversal and ``closed`` is set True (treat them as indicative).
    """
    # --- area and centroid -------------------------------------------------
    A = Sx = Sy = 0.0
    el = []
    for ni, nj, t in elems:
        (xa, ya), (xb, yb) = nodes[ni], nodes[nj]
        L = math.hypot(xb - xa, yb - ya)
        if L <= 0.0:
            continue
        a = t * L
        A += a
        Sx += a * (xa + xb) / 2.0
        Sy += a * (ya + yb) / 2.0
        el.append((ni, nj, t, L))
    if A <= 0.0:
        raise ValueError("degenerate section: zero area")
    xc, yc = Sx / A, Sy / A

    # centroidal coordinates
    cx = {i: (p[0] - xc) for i, p in nodes.items()}
    cy = {i: (p[1] - yc) for i, p in nodes.items()}

    # --- second moments & torsion -----------------------------------------
    Ix = Iy = Ixy = J = 0.0
    for ni, nj, t, L in el:
        Ix += _line_int_sq(t, L, cy[ni], cy[nj])
        Iy += _line_int_sq(t, L, cx[ni], cx[nj])
        Ixy += _line_int_2(t, L, cx[ni], cx[nj], cy[ni], cy[nj])
        J += L * t ** 3 / 3.0

    # principal axes
    avg = (Ix + Iy) / 2.0
    diff = (Ix - Iy) / 2.0
    R = math.hypot(diff, Ixy)
    I1, I2 = avg + R, avg - R
    theta = 0.5 * math.atan2(-2.0 * Ixy, Ix - Iy) if R > 1e-300 else 0.0

    # --- sectorial area about the centroid (pole = centroid) --------------
    adj: Dict[int, List[Tuple[int, float]]] = defaultdict(list)
    for ni, nj, t, L in el:
        adj[ni].append((nj, t))
        adj[nj].append((ni, t))
    omega: Dict[int, float] = {}
    closed = False
    for start in nodes:                       # cover every connected component
        if start in omega:
            continue
        omega[start] = 0.0
        stack = [start]
        seen_from = {start: None}
        while stack:
            u = stack.pop()
            for v, _t in adj[u]:
                if v not in omega:
                    # d(omega) for pole at centroid: x_u*y_v - x_v*y_u
                    omega[v] = omega[u] + (cx[u] * cy[v] - cx[v] * cy[u])
                    seen_from[v] = u
                    stack.append(v)
                elif seen_from.get(u) != v:
                    closed = True             # back-edge -> closed cell

    # sectorial products about the centroid
    Px = Py = 0.0                             # int omega*x t ds, int omega*y t ds
    for ni, nj, t, L in el:
        Px += _line_int_2(t, L, omega[ni], omega[nj], cx[ni], cx[nj])
        Py += _line_int_2(t, L, omega[ni], omega[nj], cy[ni], cy[nj])

    # shear centre (general axes): solve the 2x2 from the zero-product condition
    D = Ix * Iy - Ixy * Ixy
    if abs(D) < 1e-300:
        x_sc = y_sc = 0.0
    else:
        x_sc = (Iy * Py - Ixy * Px) / D
        y_sc = (Ixy * Py - Ix * Px) / D

    # --- warping constant about the shear centre --------------------------
    # re-pole the sectorial area to the shear centre, then normalise
    omg_s = {i: omega[i] - x_sc * cy[i] + y_sc * cx[i] for i in nodes}
    Sw = 0.0
    for ni, nj, t, L in el:
        Sw += _line_int_1(t, L, omg_s[ni], omg_s[nj])
    w_mean = Sw / A
    omg_n = {i: omg_s[i] - w_mean for i in nodes}
    Cw = 0.0
    for ni, nj, t, L in el:
        Cw += _line_int_sq(t, L, omg_n[ni], omg_n[nj])

    i0 = math.sqrt((Ix + Iy) / A + x_sc ** 2 + y_sc ** 2)

    return SectionProperties(
        A=A, xc=xc, yc=yc, Ix=Ix, Iy=Iy, Ixy=Ixy, I1=I1, I2=I2, theta=theta,
        J=J, Cw=Cw, x_sc=x_sc, y_sc=y_sc, i0=i0, closed=closed)


def thickness_weighted_centroid(nodes: Dict[int, Tuple[float, float]],
                                elems: Sequence[Tuple[int, int, float]]
                                ) -> Tuple[float, float]:
    """Centre of gravity of a node/element mesh, weighting each element by its
    *area* (thickness x length) - so thicker plates pull the CG toward them."""
    A = Sx = Sy = 0.0
    for ni, nj, t in elems:
        (xa, ya), (xb, yb) = nodes[ni], nodes[nj]
        L = math.hypot(xb - xa, yb - ya)
        if L <= 0.0:
            continue
        a = t * L
        A += a
        Sx += a * (xa + xb) / 2.0
        Sy += a * (ya + yb) / 2.0
    if A <= 0.0:
        raise ValueError("degenerate section: zero area")
    return Sx / A, Sy / A


def recenter_to_centroid(nodes: Dict[int, Tuple[float, float]],
                         elems: Sequence[Tuple[int, int, float]]
                         ) -> Tuple[Dict[int, Tuple[float, float]],
                                    Tuple[float, float]]:
    """Translate every node so the thickness-weighted CG is at the origin.
    Returns ``(recentred_nodes, (xc, yc))`` - the original CG that was removed."""
    xc, yc = thickness_weighted_centroid(nodes, elems)
    moved = {i: (round(x - xc, 6), round(y - yc, 6))
             for i, (x, y) in nodes.items()}
    return moved, (xc, yc)

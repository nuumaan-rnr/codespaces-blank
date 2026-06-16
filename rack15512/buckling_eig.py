"""Nonlinear (geometric) buckling effective length of a drive-in upright.

The engine already runs a second-order analysis, so the down-aisle global
behaviour is in the member forces; applying chi over the full frame height again
double-counts it (over-conservative).  Instead, the down-aisle (local z)
effective length is taken from a geometric (nonlinear-tangent) buckling
eigenvalue of the FEM 10.2.07 "critical upright" sub-model: a single column over
the full height with the floor-connection rotational spring at the base, held
against down-aisle sway at the top, the storage loads applied at the rail levels,
and corotational (large-displacement) geometry.

The sub-model is tiny, so the eigenvalue is solved from the dense tangent
matrices with numpy (scipy is not installed):

    K0 . phi = -alpha_cr . Kg . phi,   Kg = K_t(corotational, loaded) - K0(elastic)
    N_cr,base = alpha_cr * (applied base axial),  L_cr = pi * sqrt(E*Iz / N_cr,base)

clamped to [first span, frame height].  Returns None on failure (caller keeps a
conservative fallback).
"""

from __future__ import annotations

import math
from typing import List, Optional


def column_effective_length(levels: List[float], H: float, E: float, Iz: float,
                            A: float = 1.0e4, k_base: float = 0.0,
                            mesh: int = 6) -> Optional[float]:
    """Down-aisle effective length of the critical upright (see module doc)."""
    try:
        import numpy as np
        import openseespy.opensees as ops
    except Exception:
        return None
    if H <= 0 or Iz <= 0 or E <= 0:
        return None
    breaks = sorted({0.0, *[z for z in levels if 0.0 < z < H], H})
    coords: List[float] = []
    for a, b in zip(breaks, breaks[1:]):
        for k in range(mesh):
            coords.append(a + (b - a) * k / mesh)
    coords.append(H)
    coords = sorted({round(c, 4) for c in coords})
    is_level = [any(abs(z - lz) < 1.0 for lz in levels) or i == len(coords) - 1
                for i, z in enumerate(coords)]
    n_loaded = sum(1 for f in is_level if f)
    if n_loaded == 0:
        return None

    def _matrix(order: int):
        ops.wipe()
        ops.model("basic", "-ndm", 2, "-ndf", 3)
        for i, z in enumerate(coords):
            ops.node(i + 1, 0.0, z)
        base, top = 1, len(coords)
        ops.fix(base, 1, 1, 0)                  # x,y held; rotation via spring
        ops.fix(top, 1, 0, 0)                   # held against down-aisle sway
        if k_base and k_base > 0:
            gd = len(coords) + 1
            ops.node(gd, 0.0, 0.0)
            ops.fix(gd, 1, 1, 1)
            ops.uniaxialMaterial("Elastic", 1, float(k_base))
            ops.element("zeroLength", 100000, gd, base, "-mat", 1, "-dir", 3)
        ops.geomTransf("Corotational" if order == 2 else "Linear", 1)
        for i in range(len(coords) - 1):
            ops.element("elasticBeamColumn", i + 1, i + 1, i + 2, A, E, Iz, 1)
        ops.timeSeries("Linear", 1)
        ops.pattern("Plain", 1, 1)
        for i, f in enumerate(is_level):
            if f:
                ops.load(i + 1, 0.0, -1.0, 0.0)
        ops.system("FullGeneral")
        ops.numberer("Plain")
        ops.constraints("Transformation")
        ops.test("NormDispIncr", 1.0e-8, 1)
        ops.algorithm("Linear")
        ops.integrator("LoadControl", 1.0)
        ops.analysis("Static")
        ok = ops.analyze(1) == 0
        a = ops.printA("-ret")
        ops.wipe()
        if not ok or not a:
            return None
        n = int(round(len(a) ** 0.5))
        return np.asarray(a, float).reshape(n, n) if n * n == len(a) else None

    K0 = _matrix(1)
    Kt = _matrix(2)
    if K0 is None or Kt is None or K0.shape != Kt.shape:
        return None
    try:
        mu = np.linalg.eigvals(np.linalg.solve(K0, Kt - K0))
    except Exception:
        return None
    lam = [-1.0 / m.real for m in mu
           if abs(m.imag) <= 1.0e-6 * (abs(m.real) + 1e-30)
           and abs(m.real) > 1e-12]
    lam = [x for x in lam if x > 1.0e-6]
    if not lam:
        return None
    Ncr_base = min(lam) * n_loaded
    if Ncr_base <= 0:
        return None
    Lcr = math.pi * math.sqrt(E * Iz / Ncr_base)
    first_span = breaks[1] if len(breaks) > 1 else H
    return max(min(Lcr, H), min(first_span, H))

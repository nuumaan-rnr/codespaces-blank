"""Load-combination assembly and equivalent-horizontal-force imperfections
(3D: vertical loads act in -Z, EHF act in the horizontal X-Y plane)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .model import Combination, RackModel


@dataclass
class AssembledLoads:
    """Factored loads for one analysis case.

    nodal  : node id -> [fx, fy, fz, mx, my, mz]
    member : member id -> [qx, qy, qz] (global, per unit member length)
    """

    nodal: Dict[int, List[float]] = field(default_factory=dict)
    member: Dict[int, List[float]] = field(default_factory=dict)

    def add_nodal(self, node: int, *f: float) -> None:
        acc = self.nodal.setdefault(node, [0.0] * 6)
        for i, v in enumerate(f):
            acc[i] += v

    def add_member(self, member: int, qx: float, qy: float, qz: float) -> None:
        q = self.member.setdefault(member, [0.0, 0.0, 0.0])
        q[0] += qx
        q[1] += qy
        q[2] += qz


def assemble(model: RackModel, combo: Combination) -> AssembledLoads:
    """Sum factor * load over all cases of the combination."""
    out = AssembledLoads()
    for case_name, factor in combo.factors.items():
        lc = model.load_cases[case_name]
        for nl in lc.nodal_loads:
            out.add_nodal(nl.node, factor * nl.fx, factor * nl.fy,
                          factor * nl.fz, factor * nl.mx, factor * nl.my,
                          factor * nl.mz)
        for ml in lc.member_loads:
            out.add_member(ml.member, factor * ml.qx, factor * ml.qy,
                           factor * ml.qz)
    return out


def apply_ehf(model: RackModel, loads: AssembledLoads, phi: float,
              direction: Tuple[float, float]) -> AssembledLoads:
    """Return a copy of `loads` with equivalent horizontal forces phi * V
    added in the horizontal `direction` (unit vector in the X-Y plane) for
    every downward vertical load; gravity member UDLs are lumped half to
    each end node."""
    dx, dy = direction
    out = AssembledLoads(
        nodal={n: list(f) for n, f in loads.nodal.items()},
        member={m: list(q) for m, q in loads.member.items()},
    )
    for node, f in loads.nodal.items():
        if f[2] < 0.0:
            h = phi * abs(f[2])
            out.add_nodal(node, dx * h, dy * h, 0.0)
    for mid, q in loads.member.items():
        if q[2] < 0.0:
            m = model.members[mid]
            h = phi * abs(q[2]) * model.member_length(m) / 2.0
            out.add_nodal(m.node_i, dx * h, dy * h, 0.0)
            out.add_nodal(m.node_j, dx * h, dy * h, 0.0)
    return out

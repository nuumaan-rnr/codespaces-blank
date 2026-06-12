"""Load-combination assembly and equivalent-horizontal-force imperfections."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .model import Combination, RackModel


@dataclass
class AssembledLoads:
    """Factored loads for one analysis case.

    nodal  : node id -> [fx, fy, mz]
    member : member id -> [qx, qy] (global, per unit member length)
    """

    nodal: Dict[int, List[float]] = field(default_factory=dict)
    member: Dict[int, List[float]] = field(default_factory=dict)

    def add_nodal(self, node: int, fx: float, fy: float, mz: float) -> None:
        f = self.nodal.setdefault(node, [0.0, 0.0, 0.0])
        f[0] += fx
        f[1] += fy
        f[2] += mz

    def add_member(self, member: int, qx: float, qy: float) -> None:
        q = self.member.setdefault(member, [0.0, 0.0])
        q[0] += qx
        q[1] += qy


def assemble(model: RackModel, combo: Combination) -> AssembledLoads:
    """Sum factor * load over all cases of the combination."""
    out = AssembledLoads()
    for case_name, factor in combo.factors.items():
        lc = model.load_cases[case_name]
        for nl in lc.nodal_loads:
            out.add_nodal(nl.node, factor * nl.fx, factor * nl.fy, factor * nl.mz)
        for ml in lc.member_loads:
            out.add_member(ml.member, factor * ml.qx, factor * ml.qy)
    return out


def apply_ehf(model: RackModel, loads: AssembledLoads, phi: float,
              direction: int) -> AssembledLoads:
    """Return a copy of `loads` with equivalent horizontal forces phi * V
    added for every downward vertical load (nodal forces and gravity member
    UDLs, the latter lumped half to each end node)."""
    out = AssembledLoads(
        nodal={n: list(f) for n, f in loads.nodal.items()},
        member={m: list(q) for m, q in loads.member.items()},
    )
    for node, f in loads.nodal.items():
        if f[1] < 0.0:
            out.add_nodal(node, direction * phi * abs(f[1]), 0.0, 0.0)
    for mid, q in loads.member.items():
        if q[1] < 0.0:
            m = model.members[mid]
            w_total = abs(q[1]) * model.member_length(m)
            h = direction * phi * w_total / 2.0
            out.add_nodal(m.node_i, h, 0.0, 0.0)
            out.add_nodal(m.node_j, h, 0.0, 0.0)
    return out

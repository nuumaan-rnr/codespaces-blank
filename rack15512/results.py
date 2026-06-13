"""Result containers produced by the FEA engine (3D)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Station:
    """Internal forces at a position along a member (local axes).

    x       : distance from node i along the member axis [mm]
    N       : axial force, tension positive [N]
    Vy, Vz  : shear forces in local y / z [N]
    T       : torsion [N*mm]
    My, Mz  : bending moments about local y / z [N*mm]
    defl_y/z: transverse deflection relative to the member chord [mm]
    """

    x: float
    N: float
    Vy: float = 0.0
    Vz: float = 0.0
    T: float = 0.0
    My: float = 0.0
    Mz: float = 0.0
    defl_y: float = 0.0
    defl_z: float = 0.0

    @property
    def defl(self) -> float:
        return math.hypot(self.defl_y, self.defl_z)


@dataclass
class MemberResult:
    member: int
    length: float
    stations: List[Station] = field(default_factory=list)

    @property
    def N_min(self) -> float:          # most compressive axial force
        return min(s.N for s in self.stations)

    @property
    def N_max(self) -> float:
        return max(s.N for s in self.stations)

    @property
    def My_absmax(self) -> float:
        return max(abs(s.My) for s in self.stations)

    @property
    def Mz_absmax(self) -> float:
        return max(abs(s.Mz) for s in self.stations)

    @property
    def V_absmax(self) -> float:
        return max(math.hypot(s.Vy, s.Vz) for s in self.stations)

    @property
    def T_absmax(self) -> float:
        return max(abs(s.T) for s in self.stations)

    @property
    def defl_absmax(self) -> float:
        return max(s.defl for s in self.stations)

    def end(self, end: str) -> Station:
        return self.stations[0] if end == "i" else self.stations[-1]


@dataclass
class CaseResult:
    """Results of one analysis case (a combination, possibly with one
    imperfection direction)."""

    name: str
    combo: str
    kind: str                                   # 'ULS' | 'SLS'
    order: int                                  # 1 or 2
    imp_direction: str = ""                     # '+x', '-y', ... or ''
    converged: bool = True
    # node id -> (ux, uy, uz, rx, ry, rz)
    displacements: Dict[int, Tuple[float, ...]] = field(default_factory=dict)
    reactions: Dict[int, Tuple[float, ...]] = field(default_factory=dict)
    members: Dict[int, MemberResult] = field(default_factory=dict)
    # companion first-order sway (same loads, linear) for alpha_cr estimate
    sway_first_order: Optional[float] = None

    @property
    def max_sway(self) -> float:
        """Maximum horizontal displacement resultant [mm]."""
        if not self.displacements:
            return 0.0
        return max(math.hypot(d[0], d[1]) for d in self.displacements.values())

    @property
    def max_sway_x(self) -> float:
        return max((abs(d[0]) for d in self.displacements.values()), default=0.0)

    @property
    def max_sway_y(self) -> float:
        return max((abs(d[1]) for d in self.displacements.values()), default=0.0)

    @property
    def alpha_cr_estimate(self) -> Optional[float]:
        """Elastic critical load factor estimated from the sway
        amplification:  d2 ~ d1 / (1 - 1/alpha_cr)."""
        d1, d2 = self.sway_first_order, self.max_sway
        if self.order != 2 or d1 is None or d2 <= 1.0e-9 or d1 >= d2:
            return None
        return 1.0 / (1.0 - d1 / d2)

"""Result containers produced by the FEA engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Station:
    """Internal forces at a position along a member.

    x    : distance from node i along the member axis [mm]
    N    : axial force, tension positive [N]
    V    : shear force [N]
    M    : bending moment [N*mm]
    defl : transverse deflection relative to the member chord [mm]
    """

    x: float
    N: float
    V: float
    M: float
    defl: float = 0.0


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
    def M_absmax(self) -> float:
        return max(abs(s.M) for s in self.stations)

    @property
    def V_absmax(self) -> float:
        return max(abs(s.V) for s in self.stations)

    @property
    def defl_absmax(self) -> float:
        return max(abs(s.defl) for s in self.stations)

    def M_end(self, end: str) -> float:
        return self.stations[0].M if end == "i" else self.stations[-1].M


@dataclass
class CaseResult:
    """Results of one analysis case (a combination, possibly with one
    imperfection direction)."""

    name: str
    combo: str
    kind: str                                   # 'ULS' | 'SLS'
    order: int                                  # 1 or 2
    imp_direction: int = 0                      # +1, -1 or 0 (none)
    converged: bool = True
    displacements: Dict[int, Tuple[float, float, float]] = field(default_factory=dict)
    reactions: Dict[int, Tuple[float, float, float]] = field(default_factory=dict)
    members: Dict[int, MemberResult] = field(default_factory=dict)
    # companion first-order sway (same loads, linear) for alpha_cr estimate
    sway_first_order: Optional[float] = None

    @property
    def max_sway(self) -> float:
        """Maximum absolute horizontal displacement [mm]."""
        if not self.displacements:
            return 0.0
        return max(abs(d[0]) for d in self.displacements.values())

    @property
    def alpha_cr_estimate(self) -> Optional[float]:
        """Estimate of the elastic critical load factor from the sway
        amplification:  d2 ~ d1 / (1 - 1/alpha_cr)  ->
        alpha_cr ~ 1 / (1 - d1/d2).  Only meaningful for 2nd-order sway
        cases with a 1st-order companion run."""
        d1, d2 = self.sway_first_order, self.max_sway
        if self.order != 2 or d1 is None or d2 <= 1.0e-9 or d1 >= d2:
            return None
        ratio = d1 / d2
        if ratio >= 1.0:
            return None
        return 1.0 / (1.0 - ratio)

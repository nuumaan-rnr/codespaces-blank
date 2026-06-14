"""Result envelopes.

An envelope groups several analysis cases (e.g. all ULS combinations, or
the imperfection directions of one combination) and exposes the enveloped
extremes per member and per support, so the user can view "the worst of
the ULS set" or "the worst of the SLS set" in one place.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .checks.en15512 import CheckResult
from .results import CaseResult


@dataclass
class MemberEnvelope:
    member: int
    member_set: str
    N_min: float = 0.0          # most compressive over the set
    N_max: float = 0.0
    My_absmax: float = 0.0
    Mz_absmax: float = 0.0
    V_absmax: float = 0.0
    defl_absmax: float = 0.0
    N_min_case: str = ""
    My_case: str = ""
    Mz_case: str = ""


@dataclass
class Envelope:
    name: str                   # 'ULS', 'SLS', or a combination name
    kind: str                   # 'ULS' | 'SLS' | 'mixed'
    cases: List[CaseResult] = field(default_factory=list)
    members: Dict[int, MemberEnvelope] = field(default_factory=dict)
    # node -> (component -> (value, case)) for the 6 reaction components
    reactions: Dict[int, Dict[str, Tuple[float, str]]] = field(
        default_factory=dict)
    # worst non-informative check over the set, and per check kind
    governing: Optional[CheckResult] = None
    util_by_check: Dict[str, float] = field(default_factory=dict)
    # worst EN 15512 utilisation per member over the set (member id -> util)
    member_util: Dict[int, float] = field(default_factory=dict)

    @property
    def converged(self) -> bool:
        return all(c.converged for c in self.cases)

    @property
    def max_sway(self) -> float:
        return max((c.max_sway for c in self.cases), default=0.0)

    def representative_case(self) -> Optional[CaseResult]:
        """The case driving the largest sway - used for the deformed view."""
        conv = [c for c in self.cases if c.converged]
        return max(conv, key=lambda c: c.max_sway) if conv else None


def _build_member_envelope(model, cases) -> Dict[int, MemberEnvelope]:
    env: Dict[int, MemberEnvelope] = {}
    for case in cases:
        if not case.converged:
            continue
        for mid, mr in case.members.items():
            if mid not in model.members:
                continue          # stale results vs the current model geometry
            e = env.get(mid)
            if e is None:
                e = MemberEnvelope(member=mid,
                                   member_set=model.members[mid].member_set)
                env[mid] = e
            if mr.N_min < e.N_min:
                e.N_min, e.N_min_case = mr.N_min, case.name
            e.N_max = max(e.N_max, mr.N_max)
            if mr.My_absmax > e.My_absmax:
                e.My_absmax, e.My_case = mr.My_absmax, case.name
            if mr.Mz_absmax > e.Mz_absmax:
                e.Mz_absmax, e.Mz_case = mr.Mz_absmax, case.name
            e.V_absmax = max(e.V_absmax, mr.V_absmax)
            e.defl_absmax = max(e.defl_absmax, mr.defl_absmax)
    return env


def _build_reaction_envelope(cases):
    comps = ("Fx", "Fy", "Fz", "Mx", "My", "Mz")
    out: Dict[int, Dict[str, Tuple[float, str]]] = {}
    for case in cases:
        if not case.converged:
            continue
        for node, r in case.reactions.items():
            d = out.setdefault(node, {})
            for i, c in enumerate(comps):
                if c not in d or abs(r[i]) > abs(d[c][0]):
                    d[c] = (r[i], case.name)
    return out


def build_envelopes(model, cases: List[CaseResult],
                    checks: List[CheckResult]) -> List[Envelope]:
    """Build the ULS and SLS envelopes (plus a per-combination envelope for
    each distinct combination), with their enveloped member forces,
    reactions and governing checks."""
    envs: List[Envelope] = []

    def make(name, kind, sel_cases):
        e = Envelope(name=name, kind=kind, cases=sel_cases)
        e.members = _build_member_envelope(model, sel_cases)
        e.reactions = _build_reaction_envelope(sel_cases)
        case_names = {c.name for c in sel_cases}
        rel = [c for c in checks
               if c.case in case_names and not c.informative]
        for c in rel:
            e.util_by_check[c.check] = max(e.util_by_check.get(c.check, 0.0),
                                           c.utilization)
            if c.target.startswith("member"):
                mid = int(c.target.split()[1])
                e.member_util[mid] = max(e.member_util.get(mid, 0.0),
                                         c.utilization)
        e.governing = max(rel, key=lambda c: c.utilization) if rel else None
        return e

    # exactly three envelopes: ULS, SLS and ULS-seismic (when present)
    for name, kind in (("ULS (all)", "ULS"), ("SLS (all)", "SLS"),
                       ("ULS-seismic", "SEISMIC")):
        sel = [c for c in cases if c.kind == kind]
        if sel:
            envs.append(make(name, kind, sel))
    return envs

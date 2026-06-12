"""Load cases, imperfection forces and load combinations.

Load cases generated:
    DL   dead load (member self weight + permanent beam line loads)
    UL   unit (pallet) loads on all beams
    PL   horizontal placement load
    IMP  equivalent horizontal forces for the global sway imperfection,
         H_j = phi * V_j at every beam level (EN 15512 allows replacing the
         geometric imperfection by equivalent horizontal forces)

Default combinations (EN 15512:2009 Table 2 partial factors):
    ULS1  gG*DL + gQ*UL + gQ*IMP                      (2nd order)
    ULS2  gG*DL + gQ*UL + gQ*IMP + gQp*PL             (2nd order)
    SLS   1.0*DL + 1.0*UL                             (1st order)

IMP scales linearly with the vertical loads (H = phi*V), so factoring it
with gamma_Q reproduces the imperfection of the factored gravity loads.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import RackConfig
from .model import RackModel

G = 9.81


@dataclass(frozen=True)
class PointLoad:
    node: int
    fx: float = 0.0     # N, +X (down-aisle)
    fz: float = 0.0     # N, +Z (up); gravity loads are negative


@dataclass(frozen=True)
class LineLoad:
    member: int
    q: float            # N/m, global Z (negative = downwards)


@dataclass
class LoadCase:
    id: str
    name: str
    point_loads: list[PointLoad] = field(default_factory=list)
    line_loads: list[LineLoad] = field(default_factory=list)


@dataclass
class Combination:
    id: str
    name: str
    factors: dict[str, float]       # load case id -> gamma
    second_order: bool
    kind: str                       # "ULS" | "SLS"


def build_load_cases(cfg: RackConfig, model: RackModel) -> dict[str, LoadCase]:
    geo = cfg.geometry

    # --- DL: self weight + permanent beam loads -----------------------------
    dl = LoadCase("DL", "Dead load")
    for m in model.members.values():
        w = m.section.self_weight * G          # N/m
        if m.kind == "beam":
            w += cfg.loads.beam_dead_load
        if w > 0.0:
            dl.line_loads.append(LineLoad(m.id, -w))

    # --- UL: unit (pallet) loads as UDL on every beam -----------------------
    ul = LoadCase("UL", "Unit loads")
    q_unit = cfg.loads.unit_load_per_beam / geo.bay_width   # N/m
    for m in model.beams:
        ul.line_loads.append(LineLoad(m.id, -q_unit))

    # --- PL: horizontal placement load at one level -------------------------
    pl = LoadCase("PL", "Placement load")
    lvl = cfg.loads.placement_level
    if lvl < 0:
        lvl = geo.n_levels + lvl
    level_nodes = sorted(model.nodes_at_level(lvl))
    if level_nodes and cfg.loads.placement_load > 0.0:
        # applied at one upright (worst case: end of the row)
        pl.point_loads.append(PointLoad(level_nodes[0], fx=cfg.loads.placement_load))

    # --- IMP: equivalent horizontal forces for sway imperfection ------------
    imp = LoadCase("IMP", "Sway imperfection (equivalent forces)")
    phi = cfg.sway_imperfection()
    for lvl_i in range(geo.n_levels):
        v_level = vertical_load_at_level(cfg, model, lvl_i)
        h = phi * v_level
        nodes = sorted(model.nodes_at_level(lvl_i))
        for nid in nodes:
            imp.point_loads.append(PointLoad(nid, fx=h / len(nodes)))

    return {lc.id: lc for lc in (dl, ul, pl, imp)}


def vertical_load_at_level(cfg: RackConfig, model: RackModel, level: int) -> float:
    """Characteristic vertical load (N) introduced at one beam level:
    unit loads + beam self/dead load of that level's beams."""
    geo = cfg.geometry
    per_beam = (
        cfg.loads.unit_load_per_beam
        + (cfg.loads.beam_dead_load + cfg.beam_section.self_weight * G) * geo.bay_width
    )
    return per_beam * geo.n_bays


def build_default_combinations(cfg: RackConfig) -> list[Combination]:
    f = cfg.factors
    so = cfg.analysis.second_order
    return [
        Combination(
            id="ULS1", name="ULS gravity + imperfection",
            factors={"DL": f.gamma_G, "UL": f.gamma_Q_unit, "IMP": f.gamma_Q_unit},
            second_order=so, kind="ULS",
        ),
        Combination(
            id="ULS2", name="ULS gravity + imperfection + placement",
            factors={"DL": f.gamma_G, "UL": f.gamma_Q_unit,
                     "IMP": f.gamma_Q_unit, "PL": f.gamma_Q_placement},
            second_order=so, kind="ULS",
        ),
        Combination(
            id="SLS", name="SLS characteristic",
            factors={"DL": 1.0, "UL": 1.0},
            second_order=False, kind="SLS",
        ),
    ]

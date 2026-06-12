"""Load cases, imperfection forces and load combinations (3D).

Load cases generated:
    DL     dead load (member self weight + permanent beam line loads)
    UL     unit (pallet) loads on all beams
    PLX    horizontal placement load, down-aisle (X)
    PLY    horizontal placement load, cross-aisle (Y)
    IMPX   equivalent horizontal forces for the down-aisle sway imperfection
    IMPY   equivalent horizontal forces for the cross-aisle imperfection
           (H_j = phi * V_j at every beam level; EN 15512 allows replacing
           geometric imperfections by equivalent horizontal forces)

Default combinations (EN 15512:2009 Table 2 partial factors). The standard
treats the two directions as separate design situations:
    ULS_DA1   gG*DL + gQ*UL + gQ*IMPX                    (2nd order)
    ULS_DA2   gG*DL + gQ*UL + gQ*IMPX + gQp*PLX          (2nd order)
    ULS_CA    gG*DL + gQ*UL + gQ*IMPY + gQp*PLY          (2nd order)
    SLS       1.0*(DL + UL)                  -> beam deflections
    SLS_SWX   1.0*(DL + UL + IMPX + PLX)     -> down-aisle sway
    SLS_SWY   1.0*(DL + UL + IMPY + PLY)     -> cross-aisle sway

IMPX/IMPY scale linearly with the vertical loads (H = phi*V), so factoring
them with gamma_Q reproduces the imperfection of the factored gravity loads.
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
    fy: float = 0.0     # N, +Y (cross-aisle)
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

    # --- placement loads at one level (worst case: end frame, front) --------
    lvl = cfg.loads.placement_level
    if lvl < 0:
        lvl = geo.n_levels + lvl
    plx = LoadCase("PLX", "Placement load, down-aisle")
    ply = LoadCase("PLY", "Placement load, cross-aisle")
    if cfg.loads.placement_load > 0.0:
        target = model.grid.get((0, 0, lvl))
        if target is not None:
            plx.point_loads.append(PointLoad(target, fx=cfg.loads.placement_load))
            ply.point_loads.append(PointLoad(target, fy=cfg.loads.placement_load))

    # --- imperfection equivalent horizontal forces ---------------------------
    impx = LoadCase("IMPX", "Sway imperfection X (equivalent forces)")
    impy = LoadCase("IMPY", "Sway imperfection Y (equivalent forces)")
    phi_x = cfg.sway_imperfection_x()
    phi_y = cfg.sway_imperfection_y()
    for lvl_i in range(geo.n_levels):
        v_level = vertical_load_at_level(cfg, model, lvl_i)
        nodes = sorted(model.nodes_at_level(lvl_i))
        for nid in nodes:
            impx.point_loads.append(PointLoad(nid, fx=phi_x * v_level / len(nodes)))
            impy.point_loads.append(PointLoad(nid, fy=phi_y * v_level / len(nodes)))

    return {lc.id: lc for lc in (dl, ul, plx, ply, impx, impy)}


def vertical_load_at_level(cfg: RackConfig, model: RackModel, level: int) -> float:
    """Characteristic vertical load (N) introduced at one beam level:
    unit loads + dead load of that level's beams (front + rear)."""
    geo = cfg.geometry
    per_beam = (
        cfg.loads.unit_load_per_beam
        + (cfg.loads.beam_dead_load + cfg.beam_section.self_weight * G) * geo.bay_width
    )
    return per_beam * geo.n_bays * 2        # two beams (faces) per bay


def build_default_combinations(cfg: RackConfig) -> list[Combination]:
    f = cfg.factors
    so = cfg.analysis.second_order
    return [
        Combination(
            id="ULS_DA1", name="ULS down-aisle: gravity + imperfection",
            factors={"DL": f.gamma_G, "UL": f.gamma_Q_unit, "IMPX": f.gamma_Q_unit},
            second_order=so, kind="ULS",
        ),
        Combination(
            id="ULS_DA2", name="ULS down-aisle: + placement",
            factors={"DL": f.gamma_G, "UL": f.gamma_Q_unit,
                     "IMPX": f.gamma_Q_unit, "PLX": f.gamma_Q_placement},
            second_order=so, kind="ULS",
        ),
        Combination(
            id="ULS_CA", name="ULS cross-aisle: gravity + imperfection + placement",
            factors={"DL": f.gamma_G, "UL": f.gamma_Q_unit,
                     "IMPY": f.gamma_Q_unit, "PLY": f.gamma_Q_placement},
            second_order=so, kind="ULS",
        ),
        Combination(
            id="SLS", name="SLS characteristic (beam deflection)",
            factors={"DL": 1.0, "UL": 1.0},
            second_order=False, kind="SLS",
        ),
        Combination(
            id="SLS_SWX", name="SLS sway, down-aisle",
            factors={"DL": 1.0, "UL": 1.0, "IMPX": 1.0, "PLX": 1.0},
            second_order=False, kind="SLS",
        ),
        Combination(
            id="SLS_SWY", name="SLS sway, cross-aisle",
            factors={"DL": 1.0, "UL": 1.0, "IMPY": 1.0, "PLY": 1.0},
            second_order=False, kind="SLS",
        ),
    ]

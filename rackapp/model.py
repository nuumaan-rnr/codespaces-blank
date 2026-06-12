"""Engine-neutral structural model of the rack (2D down-aisle frame).

Coordinate system: X = down-aisle (horizontal), Z = vertical (up).
The down-aisle "spine" frame is the model EN 15512 uses for sway stability
and second-order analysis; the cross-aisle braced frame is a separate model.

Sign conventions, hinges, supports etc. are neutral; each engine adapter
maps them onto its own API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .config import RackConfig, SectionConfig

RIGID = None  # marker for a rigid (no hinge / fully fixed) DOF


@dataclass(frozen=True)
class Node:
    id: int
    x: float
    z: float


@dataclass(frozen=True)
class Hinge:
    """Rotational spring about the in-plane bending axis (My).
    stiffness in Nm/rad; RIGID (None) means no hinge."""
    stiffness: Optional[float]


@dataclass(frozen=True)
class Member:
    id: int
    node_i: int
    node_j: int
    kind: str                       # "upright" | "beam"
    section: SectionConfig
    hinge_i: Optional[Hinge] = None
    hinge_j: Optional[Hinge] = None
    # bookkeeping for checks / reporting
    line: int = -1                  # upright line index (uprights)
    level: int = -1                 # beam level index (beams) / segment (uprights)
    bay: int = -1                   # bay index (beams)


@dataclass(frozen=True)
class Support:
    """Base support: translations fixed, in-plane rotation on a spring
    (semi-rigid base plate per EN 15512 floor connection tests)."""
    node: int
    ry_stiffness: Optional[float]   # Nm/rad; RIGID = clamped, 0.0 = pinned


@dataclass
class RackModel:
    name: str
    nodes: dict[int, Node] = field(default_factory=dict)
    members: dict[int, Member] = field(default_factory=dict)
    supports: list[Support] = field(default_factory=list)
    member_sets: dict[str, list[int]] = field(default_factory=dict)
    # (line, level) -> node id;  level -1 = base
    grid: dict[tuple[int, int], int] = field(default_factory=dict)
    level_elevations: list[float] = field(default_factory=list)
    total_height: float = 0.0
    E: float = 210e9                # material Young's modulus (Pa)

    def node_coords(self, nid: int) -> tuple[float, float]:
        n = self.nodes[nid]
        return n.x, n.z

    def member_length(self, mid: int) -> float:
        m = self.members[mid]
        xi, zi = self.node_coords(m.node_i)
        xj, zj = self.node_coords(m.node_j)
        return ((xj - xi) ** 2 + (zj - zi) ** 2) ** 0.5

    @property
    def uprights(self) -> list[Member]:
        return [self.members[i] for i in self.member_sets.get("uprights", [])]

    @property
    def beams(self) -> list[Member]:
        return [self.members[i] for i in self.member_sets.get("beams", [])]

    def nodes_at_level(self, level: int) -> list[int]:
        """All upright nodes at a given beam level (0-based)."""
        return [nid for (line, lvl), nid in self.grid.items() if lvl == level]

    @property
    def top_nodes(self) -> list[int]:
        top = len(self.level_elevations) - 1
        return self.nodes_at_level(top)


def build_rack_model(cfg: RackConfig) -> RackModel:
    """Generate nodes, members, hinges and supports from the rack parameters."""
    geo = cfg.geometry
    model = RackModel(
        name=cfg.name,
        level_elevations=geo.level_elevations,
        total_height=geo.total_height,
        E=cfg.material.E,
    )

    nid = 0
    for line in range(geo.n_uprights):
        x = line * geo.bay_width
        # base node
        nid += 1
        model.nodes[nid] = Node(nid, x, 0.0)
        model.grid[(line, -1)] = nid
        for lvl, z in enumerate(geo.level_elevations):
            nid += 1
            model.nodes[nid] = Node(nid, x, z)
            model.grid[(line, lvl)] = nid

    mid = 0
    uprights: list[int] = []
    beams: list[int] = []

    # Upright segments (split at every beam level so connector nodes exist)
    for line in range(geo.n_uprights):
        prev = model.grid[(line, -1)]
        for lvl in range(geo.n_levels):
            nxt = model.grid[(line, lvl)]
            mid += 1
            model.members[mid] = Member(
                id=mid, node_i=prev, node_j=nxt, kind="upright",
                section=cfg.upright_section, line=line, level=lvl,
            )
            uprights.append(mid)
            prev = nxt

    # Pallet beams with semi-rigid end connectors at both ends
    connector = Hinge(stiffness=cfg.connections.beam_end_stiffness)
    for lvl in range(geo.n_levels):
        for bay in range(geo.n_bays):
            mid += 1
            model.members[mid] = Member(
                id=mid,
                node_i=model.grid[(bay, lvl)],
                node_j=model.grid[(bay + 1, lvl)],
                kind="beam",
                section=cfg.beam_section,
                hinge_i=connector,
                hinge_j=connector,
                level=lvl,
                bay=bay,
            )
            beams.append(mid)

    model.member_sets["uprights"] = uprights
    model.member_sets["beams"] = beams

    # Semi-rigid base supports (floor connection)
    for line in range(geo.n_uprights):
        model.supports.append(
            Support(node=model.grid[(line, -1)],
                    ry_stiffness=cfg.connections.base_stiffness)
        )
    return model

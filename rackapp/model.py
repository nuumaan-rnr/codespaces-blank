"""Engine-neutral 3D structural model of the rack.

Coordinates: X = down-aisle, Y = cross-aisle (depth), Z = vertical (up).

The full rack is modelled: at each frame position x_i there is an upright
frame consisting of a front upright (y = 0), a rear upright (y = depth) and
truss bracing between them; pallet beams run down-aisle on both faces and
connect to the uprights through semi-rigid connector hinges.

Member local axes (see engine): for uprights local y = global Y, so section
Iy governs down-aisle bending and Iz cross-aisle bending; for beams local
z = global Z, so Iy is the major (vertical) bending axis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .config import RackConfig, SectionConfig

RIGID = None    # marker for a rigid (no hinge / clamped) rotational component
TOL = 1e-6      # node-merge tolerance (m)


@dataclass(frozen=True)
class Node:
    id: int
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class Hinge:
    """Member-end rotational releases (springs) in local axes.

    my / mz: spring stiffness in Nm/rad about the local y / z axis;
    RIGID (None) = no release, 0.0 = frictionless pin.
    Axial force and torsion are always transferred.
    """
    my: Optional[float] = RIGID
    mz: Optional[float] = RIGID


@dataclass(frozen=True)
class Member:
    id: int
    node_i: int
    node_j: int
    kind: str                       # "upright" | "beam" | "brace"
    section: SectionConfig
    behavior: str = "beam"          # "beam" (frame) | "truss" (axial only)
    hinge_i: Optional[Hinge] = None
    hinge_j: Optional[Hinge] = None
    # bookkeeping for checks / reporting
    line: int = -1                  # frame index (uprights/braces)
    face: int = -1                  # 0 = front (y=0), 1 = rear (uprights/beams)
    level: int = -1                 # beam level index / upright segment index
    bay: int = -1                   # bay index (beams)


@dataclass(frozen=True)
class Support:
    """Base support: translations and torsion (rz) fixed; rotations about the
    horizontal axes on springs (semi-rigid base plate per EN 15512 tests).

    ry_stiffness: about global Y  -> resists down-aisle (X) sway
    rx_stiffness: about global X  -> resists cross-aisle (Y) sway
    RIGID = clamped, 0.0 = pinned.
    """
    node: int
    ry_stiffness: Optional[float]
    rx_stiffness: Optional[float]


@dataclass
class RackModel:
    name: str
    nodes: dict[int, Node] = field(default_factory=dict)
    members: dict[int, Member] = field(default_factory=dict)
    supports: list[Support] = field(default_factory=list)
    member_sets: dict[str, list[int]] = field(default_factory=dict)
    # (frame line, face, level) -> node id at beam levels; level -1 = base
    grid: dict[tuple[int, int, int], int] = field(default_factory=dict)
    level_elevations: list[float] = field(default_factory=list)
    total_height: float = 0.0
    E: float = 210e9
    G: float = 81e9

    def node_coords(self, nid: int) -> tuple[float, float, float]:
        n = self.nodes[nid]
        return n.x, n.y, n.z

    def member_length(self, mid: int) -> float:
        m = self.members[mid]
        xi, yi, zi = self.node_coords(m.node_i)
        xj, yj, zj = self.node_coords(m.node_j)
        return ((xj - xi) ** 2 + (yj - yi) ** 2 + (zj - zi) ** 2) ** 0.5

    @property
    def uprights(self) -> list[Member]:
        return [self.members[i] for i in self.member_sets.get("uprights", [])]

    @property
    def beams(self) -> list[Member]:
        return [self.members[i] for i in self.member_sets.get("beams", [])]

    @property
    def braces(self) -> list[Member]:
        return [self.members[i] for i in self.member_sets.get("braces", [])]

    def nodes_at_level(self, level: int) -> list[int]:
        """All upright nodes (front + rear) at a given beam level."""
        return [nid for (_, _, lvl), nid in self.grid.items() if lvl == level]

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
        G=cfg.material.G,
    )

    # elevations where the uprights need nodes: beam levels + brace points
    beam_z = geo.level_elevations
    brace_z: list[float] = []
    if geo.bracing.pattern != "none":
        p = geo.bracing.panel_height
        z = p
        while z < geo.total_height - TOL:
            brace_z.append(z)
            z += p
        brace_z.append(geo.total_height)
    upright_z = _merge_elevations(beam_z, brace_z)

    # --- nodes ---------------------------------------------------------------
    nid = 0
    # (line, face) -> ordered list of (z, node id) including the base
    columns: dict[tuple[int, int], list[tuple[float, int]]] = {}
    for line in range(geo.n_frames):
        x = line * geo.bay_width
        for face, y in enumerate((0.0, geo.depth)):
            nid += 1
            model.nodes[nid] = Node(nid, x, y, 0.0)
            model.grid[(line, face, -1)] = nid
            col = [(0.0, nid)]
            for z in upright_z:
                nid += 1
                model.nodes[nid] = Node(nid, x, y, z)
                col.append((z, nid))
                lvl = _level_of(z, beam_z)
                if lvl is not None:
                    model.grid[(line, face, lvl)] = nid
            columns[(line, face)] = col

    mid = 0
    uprights: list[int] = []
    beams: list[int] = []
    braces: list[int] = []

    # --- upright segments (continuous columns split at every node) -----------
    for (line, face), col in columns.items():
        for seg in range(len(col) - 1):
            mid += 1
            model.members[mid] = Member(
                id=mid, node_i=col[seg][1], node_j=col[seg + 1][1],
                kind="upright", section=cfg.upright_section,
                line=line, face=face, level=seg,
            )
            uprights.append(mid)

    # --- pallet beams on both faces, semi-rigid connectors -------------------
    mz = RIGID if cfg.connections.beam_end_mz == "rigid" else 0.0
    connector = Hinge(my=cfg.connections.beam_end_stiffness, mz=mz)
    for lvl in range(geo.n_levels):
        for bay in range(geo.n_bays):
            for face in (0, 1):
                mid += 1
                model.members[mid] = Member(
                    id=mid,
                    node_i=model.grid[(bay, face, lvl)],
                    node_j=model.grid[(bay + 1, face, lvl)],
                    kind="beam", section=cfg.beam_section,
                    hinge_i=connector, hinge_j=connector,
                    level=lvl, bay=bay, face=face,
                )
                beams.append(mid)

    # --- cross-aisle frame bracing (truss members) ----------------------------
    if geo.bracing.pattern != "none":
        # canonical (merged) elevations of the brace points
        canon_brace = [z for z in upright_z
                       if any(abs(z - b) <= TOL for b in brace_z)]
        for line in range(geo.n_frames):
            front = dict_at(columns[(line, 0)])
            rear = dict_at(columns[(line, 1)])
            pts = [0.0] + canon_brace
            for k in range(len(pts) - 1):
                z_lo, z_hi = pts[k], pts[k + 1]
                # horizontal strut at the top of each panel
                mid += 1
                model.members[mid] = Member(
                    id=mid, node_i=front[z_hi], node_j=rear[z_hi],
                    kind="brace", section=cfg.brace_section,
                    behavior="truss", line=line, level=k,
                )
                braces.append(mid)
                # alternating diagonal
                lo_face, hi_face = (front, rear) if k % 2 == 0 else (rear, front)
                mid += 1
                model.members[mid] = Member(
                    id=mid, node_i=lo_face[z_lo], node_j=hi_face[z_hi],
                    kind="brace", section=cfg.brace_section,
                    behavior="truss", line=line, level=k,
                )
                braces.append(mid)

    model.member_sets["uprights"] = uprights
    model.member_sets["beams"] = beams
    model.member_sets["braces"] = braces

    # --- semi-rigid base supports ---------------------------------------------
    for line in range(geo.n_frames):
        for face in (0, 1):
            model.supports.append(Support(
                node=model.grid[(line, face, -1)],
                ry_stiffness=cfg.connections.base_stiffness,
                rx_stiffness=cfg.connections.base_cross,
            ))
    return model


def _merge_elevations(beam_z: list[float], brace_z: list[float]) -> list[float]:
    out: list[float] = []
    for z in sorted(beam_z + brace_z):
        if not out or z - out[-1] > TOL:
            out.append(z)
    return out


def _level_of(z: float, beam_z: list[float]) -> Optional[int]:
    for lvl, bz in enumerate(beam_z):
        if abs(z - bz) <= TOL:
            return lvl
    return None


def dict_at(col: list[tuple[float, int]]) -> dict[float, int]:
    """Map elevation -> node id for one upright (keyed on merged z values)."""
    return {z: nid for z, nid in col}

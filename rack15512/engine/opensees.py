"""OpenSees (OpenSeesPy) engine for 2D rack frames.

Why OpenSees: it is a proven, open-source FEA engine that natively supports
everything EN 15512 requires for the global analysis of racks:
  * elastic beam-column and truss elements,
  * semi-rigid connections (zero-length rotational springs with arbitrary
    stiffness) for beam-to-upright connectors and floor connections,
  * geometrically nonlinear (second-order / P-Delta, corotational) analysis,
  * spring supports and initial-geometry imperfections.

Modelling choices:
  * Semi-rigid member-end hinge: an auxiliary node is created at the member
    end, tied to the structure node in translation (equalDOF) and connected
    in rotation through a zeroLength element with an elastic material of the
    connector stiffness.  Zero stiffness = perfect pin.
  * Spring support DOFs: zeroLength element to a fully fixed ground node.
  * Second order: 'PDelta' geometric transformation for beams (members are
    subdivided so P-little-delta is captured), 'corotTruss' for truss
    members, with incremental Newton-Raphson solution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import openseespy.opensees as ops

from ..combos import AssembledLoads
from ..model import Member, RackModel
from ..results import CaseResult, MemberResult, Station


@dataclass
class _Segment:
    ele_tag: int
    tag_i: int            # internal node tag at segment start
    tag_j: int
    x_start: float        # distance of segment start from member node i
    length: float
    wx: float = 0.0       # local axial UDL
    wy: float = 0.0       # local transverse UDL


@dataclass
class _MemberMap:
    member: Member
    length: float
    cx: float
    cy: float
    segments: List[_Segment] = field(default_factory=list)
    truss_tag: Optional[int] = None


class OpenSeesEngine:
    """Builds and solves one analysis case per call to `run_case`."""

    def run_case(self, model: RackModel, loads: AssembledLoads, *,
                 name: str, combo: str, kind: str, order: int = 2,
                 imp_direction: int = 0,
                 geom_sway: Optional[Tuple[float, int]] = None) -> CaseResult:
        """geom_sway = (phi, direction) applies an initial out-of-plumb to
        the geometry (x' = x + dir * phi * (y - y_min))."""

        n_steps = max(1, model.analysis.n_steps) if order == 2 else 1
        converged = False
        for attempt_steps in (n_steps, 5 * n_steps):
            ops.wipe()
            ops.model("basic", "-ndm", 2, "-ndf", 3)

            self._next_tag = 1
            self._node_tag: Dict[int, int] = {}      # model node id -> ops tag
            self._coords: Dict[int, Tuple[float, float]] = {}
            self._members: Dict[int, _MemberMap] = {}
            self._spring_ground: Dict[int, int] = {}  # support node -> ground tag
            self._mat_tag = 0
            self._transf_tag = 0

            self._build_nodes(model, geom_sway)
            self._build_members(model, order)
            self._build_supports(model)
            self._fix_spinning_nodes(model)
            self._apply_loads(model, loads)

            converged = self._solve(model, attempt_steps)
            if converged:
                break

        res = CaseResult(name=name, combo=combo, kind=kind, order=order,
                         imp_direction=imp_direction, converged=converged)
        if converged:
            self._collect(model, res)
        ops.wipe()
        return res

    # ------------------------------------------------------------------ build
    def _new_tag(self) -> int:
        t = self._next_tag
        self._next_tag += 1
        return t

    def _build_nodes(self, model: RackModel,
                     geom_sway: Optional[Tuple[float, int]]) -> None:
        y_min = min(n.y for n in model.nodes.values())
        for n in model.nodes.values():
            x = n.x
            if geom_sway is not None:
                phi, direction = geom_sway
                x += direction * phi * (n.y - y_min)
            tag = self._new_tag()
            self._node_tag[n.id] = tag
            self._coords[tag] = (x, n.y)
            ops.node(tag, x, n.y)

    def _elastic_mat(self, k: float) -> int:
        self._mat_tag += 1
        ops.uniaxialMaterial("Elastic", self._mat_tag, k)
        return self._mat_tag

    def _hinged_end(self, struct_tag: int, hinge) -> int:
        """Create the auxiliary node + translational tie + rotational spring
        for a semi-rigid member end; return the tag the member connects to."""
        aux = self._new_tag()
        x, y = self._coords[struct_tag]
        ops.node(aux, x, y)
        self._coords[aux] = (x, y)
        ops.equalDOF(struct_tag, aux, 1, 2)
        if hinge.stiffness > 0.0:
            mat = self._elastic_mat(hinge.stiffness)
            ele = self._new_tag()
            ops.element("zeroLength", ele, struct_tag, aux,
                        "-mat", mat, "-dir", 6)
        return aux

    def _build_members(self, model: RackModel, order: int) -> None:
        for m in model.members.values():
            sec = model.section_of(m)
            mat = model.material_of(m)
            ti = self._node_tag[m.node_i]
            tj = self._node_tag[m.node_j]
            xi, yi = self._coords[ti]
            xj, yj = self._coords[tj]
            L = math.hypot(xj - xi, yj - yi)
            cx, cy = (xj - xi) / L, (yj - yi) / L
            mmap = _MemberMap(member=m, length=L, cx=cx, cy=cy)
            self._members[m.id] = mmap

            if m.mtype == "truss":
                mt = self._elastic_mat(mat.E)
                ele = self._new_tag()
                etype = "corotTruss" if order == 2 else "truss"
                ops.element(etype, ele, ti, tj, sec.A, mt)
                mmap.truss_tag = ele
                continue

            end_i = self._hinged_end(ti, m.hinge_i) if m.hinge_i else ti
            end_j = self._hinged_end(tj, m.hinge_j) if m.hinge_j else tj

            self._transf_tag += 1
            ttype = "PDelta" if order == 2 else "Linear"
            ops.geomTransf(ttype, self._transf_tag)

            nseg = max(1, int(m.mesh))
            tags = [end_i]
            for k in range(1, nseg):
                t = self._new_tag()
                x = xi + cx * L * k / nseg
                y = yi + cy * L * k / nseg
                ops.node(t, x, y)
                self._coords[t] = (x, y)
                tags.append(t)
            tags.append(end_j)
            for k in range(nseg):
                ele = self._new_tag()
                ops.element("elasticBeamColumn", ele, tags[k], tags[k + 1],
                            sec.A, mat.E, sec.I, self._transf_tag)
                mmap.segments.append(_Segment(
                    ele_tag=ele, tag_i=tags[k], tag_j=tags[k + 1],
                    x_start=L * k / nseg, length=L / nseg))

    def _build_supports(self, model: RackModel) -> None:
        for sup in model.supports:
            tag = self._node_tag[sup.node]
            restraints = (sup.ux, sup.uy, sup.rz)
            fix_flags = [1 if r is True else 0 for r in restraints]
            springs = [(i, float(r)) for i, r in enumerate(restraints)
                       if not isinstance(r, bool)
                       and isinstance(r, (int, float)) and r > 0.0]
            if any(fix_flags):
                ops.fix(tag, *fix_flags)
            if springs:
                ground = self._new_tag()
                x, y = self._coords[tag]
                ops.node(ground, x, y)
                self._coords[ground] = (x, y)
                ops.fix(ground, 1, 1, 1)
                self._spring_ground[sup.node] = ground
                mats, dirs = [], []
                for dof_idx, k in springs:
                    mats.append(self._elastic_mat(k))
                    dirs.append({0: 1, 1: 2, 2: 6}[dof_idx])
                ele = self._new_tag()
                ops.element("zeroLength", ele, ground, tag,
                            "-mat", *mats, "-dir", *dirs)

    def _fix_spinning_nodes(self, model: RackModel) -> None:
        """Restrain the rotation of nodes whose rz DOF has no stiffness
        (e.g. nodes connected only by truss members)."""
        has_rot: Dict[int, bool] = {nid: False for nid in model.nodes}
        for m in model.members.values():
            if m.mtype == "beam":
                if not m.hinge_i:
                    has_rot[m.node_i] = True
                if not m.hinge_j:
                    has_rot[m.node_j] = True
        for sup in model.supports:
            rz = sup.rz
            if rz is True or (not isinstance(rz, bool)
                              and isinstance(rz, (int, float)) and rz > 0):
                has_rot[sup.node] = True
        for m in model.members.values():
            # a hinge spring also gives the structure node some rotational
            # stiffness only if the hinge stiffness is non-zero
            if m.mtype == "beam":
                if m.hinge_i and m.hinge_i.stiffness > 0:
                    has_rot[m.node_i] = True
                if m.hinge_j and m.hinge_j.stiffness > 0:
                    has_rot[m.node_j] = True
        for nid, ok in has_rot.items():
            if not ok:
                ops.fix(self._node_tag[nid], 0, 0, 1)

    def _apply_loads(self, model: RackModel, loads: AssembledLoads) -> None:
        ops.timeSeries("Linear", 1)
        ops.pattern("Plain", 1, 1)
        for nid, (fx, fy, mz) in loads.nodal.items():
            ops.load(self._node_tag[nid], fx, fy, mz)
        for mid, (qx, qy) in loads.member.items():
            mmap = self._members[mid]
            if mmap.member.mtype == "truss":
                # lump on end nodes
                w = mmap.length / 2.0
                ops.load(self._node_tag[mmap.member.node_i], qx * w, qy * w, 0.0)
                ops.load(self._node_tag[mmap.member.node_j], qx * w, qy * w, 0.0)
                continue
            cx, cy = mmap.cx, mmap.cy
            wx = qx * cx + qy * cy            # local axial
            wy = -qx * cy + qy * cx           # local transverse
            for seg in mmap.segments:
                seg.wx, seg.wy = wx, wy
                ops.eleLoad("-ele", seg.ele_tag, "-type", "-beamUniform", wy, wx)

    # ------------------------------------------------------------------ solve
    def _solve(self, model: RackModel, n_steps: int) -> bool:
        st = model.analysis
        ops.constraints("Transformation")
        ops.numberer("RCM")
        ops.system("BandGeneral")
        ops.test("NormDispIncr", st.tolerance, st.max_iter)
        ops.algorithm("Newton")
        ops.integrator("LoadControl", 1.0 / n_steps)
        ops.analysis("Static")
        return ops.analyze(n_steps) == 0

    # ---------------------------------------------------------------- results
    def _collect(self, model: RackModel, res: CaseResult) -> None:
        for nid, tag in self._node_tag.items():
            d = ops.nodeDisp(tag)
            res.displacements[nid] = (d[0], d[1], d[2])

        ops.reactions()
        for sup in model.supports:
            tag = self._node_tag[sup.node]
            r = ops.nodeReaction(tag)
            rx, ry, rm = r[0], r[1], r[2]
            ground = self._spring_ground.get(sup.node)
            if ground is not None:
                # the ground-node reaction acts on the ground; the restraining
                # force on the structure is its opposite
                rg = ops.nodeReaction(ground)
                rx -= rg[0]
                ry -= rg[1]
                rm -= rg[2]
            res.reactions[sup.node] = (rx, ry, rm)

        for mid, mmap in self._members.items():
            res.members[mid] = self._member_result(mmap)

    def _member_result(self, mmap: _MemberMap) -> MemberResult:
        mr = MemberResult(member=mmap.member.id, length=mmap.length)
        cx, cy = mmap.cx, mmap.cy

        if mmap.truss_tag is not None:
            f = ops.eleResponse(mmap.truss_tag, "axialForce")
            N = f[0] if f else 0.0
            mr.stations = [Station(0.0, N, 0.0, 0.0),
                           Station(mmap.length, N, 0.0, 0.0)]
            return mr

        # chord (local transverse) displacements of the member's end nodes
        def local_v(tag: int) -> float:
            d = ops.nodeDisp(tag)
            return -d[0] * cy + d[1] * cx

        v_i = local_v(mmap.segments[0].tag_i)
        v_j = local_v(mmap.segments[-1].tag_j)

        def chord_defl(tag: int, x: float) -> float:
            v = local_v(tag)
            return v - (v_i + (v_j - v_i) * x / mmap.length)

        for k, seg in enumerate(mmap.segments):
            lf = ops.eleResponse(seg.ele_tag, "localForce")
            fxi, fyi, mzi = lf[0], lf[1], lf[2]

            def section_forces(x: float) -> Tuple[float, float, float]:
                N = -(fxi + seg.wx * x)
                V = fyi + seg.wy * x
                M = -mzi + fyi * x + seg.wy * x * x / 2.0
                return N, V, M

            xs = [0.0]
            if abs(seg.wy) > 1.0e-12:           # moment parabola vertex
                xv = -fyi / seg.wy
                if 0.0 < xv < seg.length:
                    xs.append(xv)
            xs.append(seg.length)

            for x in xs:
                if k > 0 and x == 0.0:
                    continue                     # avoid duplicate stations
                N, V, M = section_forces(x)
                if x == 0.0:
                    defl = chord_defl(seg.tag_i, seg.x_start)
                elif x == seg.length:
                    defl = chord_defl(seg.tag_j, seg.x_start + seg.length)
                else:
                    di = chord_defl(seg.tag_i, seg.x_start)
                    dj = chord_defl(seg.tag_j, seg.x_start + seg.length)
                    defl = di + (dj - di) * x / seg.length
                mr.stations.append(Station(seg.x_start + x, N, V, M, defl))
        return mr

"""OpenSees (OpenSeesPy) engine for 3D rack structures.

Why OpenSees: a proven, open-source FEA engine that natively supports
everything EN 15512 requires for the global analysis of racks:
  * 3D elastic beam-column and truss elements,
  * semi-rigid connections (zero-length rotational springs with arbitrary
    stiffness about each member-local axis) for beam-to-upright connectors
    and floor connections,
  * geometrically nonlinear (second-order / P-Delta, corotational) analysis,
  * spring supports and initial-geometry imperfections.

Modelling choices:
  * Semi-rigid member-end hinge: an auxiliary node at the member end is
    tied to the structure node in translation (equalDOF) and connected in
    rotation through a zeroLength element oriented to the member's local
    axes - per rotation axis: spring stiffness, perfect release, or a stiff
    penalty spring (RIGID_ROT) for continuous axes.
  * Spring support DOFs: zeroLength element to a fully fixed ground node
    (global axes).
  * Second order: 'PDelta' geometric transformation for beams (members are
    subdivided so P-little-delta is captured), 'corotTruss' for trusses,
    incremental Newton-Raphson solution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import openseespy.opensees as ops

from ..combos import AssembledLoads
from ..model import Member, RackModel
from ..results import CaseResult, MemberResult, Station

# penalty stiffness for 'continuous' rotation axes at hinged ends
# [N*mm/rad]; ~4 orders above typical member EI/L - rigid for practical
# purposes while keeping the tangent well-conditioned for Newton iteration
RIGID_ROT = 1.0e12


@dataclass
class _Segment:
    ele_tag: int
    tag_i: int            # internal node tag at segment start
    tag_j: int
    x_start: float        # distance of segment start from member node i
    length: float
    wx: float = 0.0       # local UDLs
    wy: float = 0.0
    wz: float = 0.0


@dataclass
class _MemberMap:
    member: Member
    length: float
    xh: Tuple[float, float, float]      # local axes (unit vectors, global)
    yh: Tuple[float, float, float]
    zh: Tuple[float, float, float]
    segments: List[_Segment] = field(default_factory=list)
    truss_tag: Optional[int] = None


class OpenSeesEngine:
    """Builds and solves one analysis case per call to `run_case`."""

    def run_case(self, model: RackModel, loads: AssembledLoads, *,
                 name: str, combo: str, kind: str, order: int = 2,
                 imp_direction: str = "",
                 geom_sway: Optional[Tuple[float, Tuple[float, float]]] = None
                 ) -> CaseResult:
        """geom_sway = (phi, (dx, dy)) applies an initial out-of-plumb to
        the geometry: (x, y) += (dx, dy) * phi * (z - z_min)."""

        n_steps = max(1, model.analysis.n_steps) if order == 2 else 1
        converged = False
        for attempt_steps in (n_steps, 5 * n_steps):
            self._build(model, order, geom_sway)
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

    def modal(self, model: RackModel, masses: Dict[int, float],
              n_modes: int) -> "ModalResult":
        """Build the model once (linear), assign translational lumped mass,
        and run an eigenvalue analysis.  Returns periods + mode shapes; on any
        failure returns ModalResult(converged=False) so the caller can fall
        back to the equivalent-static method."""
        from ..results import ModalResult
        try:
            self._build(model, order=1, geom_sway=None)
            # negligible regularizing mass on every node's translational DOFs so
            # the banded ARPACK solver has a non-singular mass matrix (many rack
            # DOFs carry no lumped mass); too small to affect the real modes.
            tiny = max(sum(masses.values()) * 1.0e-9, 1.0e-12)
            for tag in self._node_tag.values():
                ops.mass(tag, tiny, tiny, tiny, 0.0, 0.0, 0.0)
            for nid, mss in masses.items():
                tag = self._node_tag.get(nid)
                if tag is not None and mss > 0.0:
                    ops.mass(tag, mss + tiny, mss + tiny, mss + tiny,
                             0.0, 0.0, 0.0)
            ops.constraints("Transformation")
            ops.numberer("RCM")
            ops.test("NormDispIncr", 1.0e-6, 50)
            ops.algorithm("Linear")
            ops.integrator("LoadControl", 1.0)
            ops.analysis("Static")
            n = max(1, min(int(n_modes), len(self._node_tag) * 3 - 1))
            # Prefer the fast banded ARPACK solver; only fall back to the dense
            # (very slow) LAPACK solver if ARPACK fails or returns junk.
            eigvals = None
            for solver, sysname in (("-genBandArpack", "BandGeneral"),
                                    ("-fullGenLapack", "FullGeneral")):
                try:
                    ops.system(sysname)
                    ev = ops.eigen(solver, n)
                    if ev and all(v is not None and v > 0.0 for v in ev):
                        eigvals = ev
                        break
                except Exception:
                    continue
            if eigvals is None:
                raise ValueError("eigen returned no valid eigenvalues")
            periods, omega2 = [], []
            for w2 in eigvals:
                omega2.append(w2)
                periods.append(2.0 * math.pi / math.sqrt(w2))
            shapes: Dict[int, List[Tuple[float, float, float]]] = {}
            for nid, tag in self._node_tag.items():
                modes = []
                for k in range(1, n + 1):
                    v = ops.nodeEigenvector(tag, k)
                    modes.append((v[0], v[1], v[2]))
                shapes[nid] = modes
            ops.wipe()
            return ModalResult(converged=True, periods=periods, omega2=omega2,
                               shapes=shapes, masses=dict(masses))
        except Exception as exc:                      # eigen unsupported/failed
            ops.wipe()
            return ModalResult(converged=False, note=f"eigen failed: {exc}")

    # ------------------------------------------------------------------ build
    def _reset_state(self) -> None:
        ops.wipe()
        ops.model("basic", "-ndm", 3, "-ndf", 6)
        self._next_tag = 1
        self._node_tag: Dict[int, int] = {}          # model node id -> ops tag
        self._coords: Dict[int, Tuple[float, float, float]] = {}
        self._members: Dict[int, _MemberMap] = {}
        self._spring_ground: Dict[int, int] = {}      # support node -> ground
        self._mat_tag = 0
        self._transf_tag = 0

    def _build(self, model: RackModel, order: int,
               geom_sway: Optional[Tuple[float, Tuple[float, float]]]) -> None:
        self._reset_state()
        self._build_nodes(model, geom_sway)
        self._build_members(model, order)
        self._build_supports(model)
        self._fix_spinning_nodes(model)

    def _new_tag(self) -> int:
        t = self._next_tag
        self._next_tag += 1
        return t

    def _build_nodes(self, model: RackModel,
                     geom_sway: Optional[Tuple[float, Tuple[float, float]]]
                     ) -> None:
        z_min = min(n.z for n in model.nodes.values())
        for n in model.nodes.values():
            x, y = n.x, n.y
            if geom_sway is not None:
                phi, (dx, dy) = geom_sway
                x += dx * phi * (n.z - z_min)
                y += dy * phi * (n.z - z_min)
            tag = self._new_tag()
            self._node_tag[n.id] = tag
            self._coords[tag] = (x, y, n.z)
            ops.node(tag, x, y, n.z)

    def _elastic_mat(self, k: float) -> int:
        self._mat_tag += 1
        ops.uniaxialMaterial("Elastic", self._mat_tag, k)
        return self._mat_tag

    def _hinged_end(self, struct_tag: int, hinge, mmap: _MemberMap) -> int:
        """Create the auxiliary node + translational tie + rotational
        springs (about the member local axes) for a semi-rigid member end;
        return the tag the member connects to."""
        aux = self._new_tag()
        xyz = self._coords[struct_tag]
        ops.node(aux, *xyz)
        self._coords[aux] = xyz
        ops.equalDOF(struct_tag, aux, 1, 2, 3)
        mats, dirs = [], []
        for direction, k in ((4, hinge.rx), (5, hinge.ry), (6, hinge.rz)):
            if k is None:
                k = RIGID_ROT              # continuous axis
            elif k <= 0.0:
                continue                   # released axis
            mats.append(self._elastic_mat(float(k)))
            dirs.append(direction)
        if mats:
            ele = self._new_tag()
            ops.element("zeroLength", ele, struct_tag, aux,
                        "-mat", *mats, "-dir", *dirs,
                        "-orient", *mmap.xh, *mmap.yh)
        return aux

    def _build_members(self, model: RackModel, order: int) -> None:
        for m in model.members.values():
            sec = model.section_of(m)
            mat = model.material_of(m)
            ti = self._node_tag[m.node_i]
            tj = self._node_tag[m.node_j]
            xi = self._coords[ti]
            xj = self._coords[tj]
            L = math.dist(xi, xj)
            # local axes from the *as-modelled* (possibly tilted) geometry
            xh = tuple((xj[k] - xi[k]) / L for k in range(3))
            yh, zh = _local_yz(xh, m.vecxz)
            mmap = _MemberMap(member=m, length=L, xh=xh, yh=yh, zh=zh)
            self._members[m.id] = mmap

            A_an = sec.A * m.area_factor      # analysis-stiffness area
            if m.mtype == "truss":
                mt = self._elastic_mat(mat.E)
                ele = self._new_tag()
                etype = "corotTruss" if order == 2 else "truss"
                ops.element(etype, ele, ti, tj, A_an, mt)
                mmap.truss_tag = ele
                continue

            end_i = self._hinged_end(ti, m.hinge_i, mmap) if m.hinge_i else ti
            end_j = self._hinged_end(tj, m.hinge_j, mmap) if m.hinge_j else tj

            self._transf_tag += 1
            ttype = "PDelta" if order == 2 else "Linear"
            ops.geomTransf(ttype, self._transf_tag, *zh)

            nseg = max(1, int(m.mesh))
            tags = [end_i]
            for k in range(1, nseg):
                t = self._new_tag()
                p = tuple(xi[c] + xh[c] * L * k / nseg for c in range(3))
                ops.node(t, *p)
                self._coords[t] = p
                tags.append(t)
            tags.append(end_j)
            for k in range(nseg):
                ele = self._new_tag()
                ops.element("elasticBeamColumn", ele, tags[k], tags[k + 1],
                            A_an, mat.E, mat.G, sec.J, sec.Iy, sec.Iz,
                            self._transf_tag)
                mmap.segments.append(_Segment(
                    ele_tag=ele, tag_i=tags[k], tag_j=tags[k + 1],
                    x_start=L * k / nseg, length=L / nseg))

    def _build_supports(self, model: RackModel) -> None:
        for sup in model.supports:
            tag = self._node_tag[sup.node]
            restraints = sup.restraints()
            fix_flags = [1 if r is True else 0 for r in restraints]
            springs = [(i, float(r)) for i, r in enumerate(restraints)
                       if not isinstance(r, bool)
                       and isinstance(r, (int, float)) and r > 0.0]
            if any(fix_flags):
                ops.fix(tag, *fix_flags)
            if springs:
                ground = self._new_tag()
                xyz = self._coords[tag]
                ops.node(ground, *xyz)
                self._coords[ground] = xyz
                ops.fix(ground, 1, 1, 1, 1, 1, 1)
                self._spring_ground[sup.node] = ground
                mats = [self._elastic_mat(k) for _, k in springs]
                dirs = [i + 1 for i, _ in springs]    # global axes
                ele = self._new_tag()
                ops.element("zeroLength", ele, ground, tag,
                            "-mat", *mats, "-dir", *dirs)

    def _fix_spinning_nodes(self, model: RackModel) -> None:
        """Restrain the rotations of nodes with no rotational stiffness
        (connected only by truss members and without rotational support)."""
        has_rot: Dict[int, bool] = {nid: False for nid in model.nodes}
        for m in model.members.values():
            if m.mtype == "beam":
                has_rot[m.node_i] = True
                has_rot[m.node_j] = True
        for sup in model.supports:
            for r in sup.restraints()[3:]:
                if r is True or (not isinstance(r, bool)
                                 and isinstance(r, (int, float)) and r > 0):
                    has_rot[sup.node] = True
        for nid, ok in has_rot.items():
            if not ok:
                ops.fix(self._node_tag[nid], 0, 0, 0, 1, 1, 1)

    def _apply_loads(self, model: RackModel, loads: AssembledLoads) -> None:
        ops.timeSeries("Linear", 1)
        ops.pattern("Plain", 1, 1)
        self._apply_load_values(model, loads)

    def _apply_load_values(self, model: RackModel,
                           loads: AssembledLoads) -> None:
        """Apply load values into the currently-open load pattern."""
        for nid, f in loads.nodal.items():
            ops.load(self._node_tag[nid], *f)
        for mid, (qx, qy, qz) in loads.member.items():
            mmap = self._members[mid]
            if mmap.member.mtype == "truss":
                w = mmap.length / 2.0     # lump on end nodes
                for nid in (mmap.member.node_i, mmap.member.node_j):
                    ops.load(self._node_tag[nid],
                             qx * w, qy * w, qz * w, 0.0, 0.0, 0.0)
                continue
            q = (qx, qy, qz)
            wx = _dot(q, mmap.xh)
            wy = _dot(q, mmap.yh)
            wz = _dot(q, mmap.zh)
            for seg in mmap.segments:
                seg.wx, seg.wy, seg.wz = wx, wy, wz
                ops.eleLoad("-ele", seg.ele_tag, "-type", "-beamUniform",
                            wy, wz, wx)

    def run_static_batch(self, model: RackModel, jobs: List[dict]
                         ) -> List[CaseResult]:
        """Build the (linear) model ONCE and solve several independent load
        cases, returning one CaseResult each.  Used for the seismic per-mode
        recovery and gravity rows so the model is not rebuilt per case (the
        rebuild dominates the cost for a braced rack)."""
        results: List[CaseResult] = []
        self._build(model, order=1, geom_sway=None)
        for i, job in enumerate(jobs, start=1):
            # clear any member UDLs left on the segments from a previous job
            for mm in self._members.values():
                for seg in mm.segments:
                    seg.wx = seg.wy = seg.wz = 0.0
            ops.timeSeries("Linear", i)
            ops.pattern("Plain", i, i)
            self._apply_load_values(model, job["loads"])
            ok = self._solve_linear()
            res = CaseResult(name=job["name"], combo=job["combo"],
                             kind=job["kind"], order=1, converged=ok)
            if ok:
                self._collect(model, res, with_defl=False)
            results.append(res)
            ops.remove("loadPattern", i)
            ops.reset()
            ops.wipeAnalysis()
        ops.wipe()
        return results

    def _solve_linear(self) -> bool:
        """Single-factorization linear static solve for the batch (no Newton
        iteration); a sparse direct solver where available, else banded."""
        ops.constraints("Transformation")
        ops.numberer("RCM")
        try:
            ops.system("UmfPack")
        except Exception:
            ops.system("BandGeneral")
        ops.test("NormDispIncr", 1.0e-8, 1)
        ops.algorithm("Linear")
        ops.integrator("LoadControl", 1.0)
        ops.analysis("Static")
        return ops.analyze(1) == 0

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
    def _collect(self, model: RackModel, res: CaseResult,
                 with_defl: bool = True) -> None:
        for nid, tag in self._node_tag.items():
            res.displacements[nid] = tuple(ops.nodeDisp(tag))

        ops.reactions()
        for sup in model.supports:
            tag = self._node_tag[sup.node]
            r = list(ops.nodeReaction(tag))
            ground = self._spring_ground.get(sup.node)
            if ground is not None:
                # the ground-node reaction acts on the ground; the
                # restraining force on the structure is its opposite
                rg = ops.nodeReaction(ground)
                r = [a - b for a, b in zip(r, rg)]
            res.reactions[sup.node] = tuple(r)

        for mid, mmap in self._members.items():
            res.members[mid] = self._member_result(mmap, with_defl)

    def _member_result(self, mmap: _MemberMap,
                       with_defl: bool = True) -> MemberResult:
        mr = MemberResult(member=mmap.member.id, length=mmap.length)

        if mmap.truss_tag is not None:
            f = ops.eleResponse(mmap.truss_tag, "axialForce")
            N = f[0] if f else 0.0
            mr.stations = [Station(0.0, N), Station(mmap.length, N)]
            return mr

        # local transverse displacements of nodes, for chord deflections
        # (skipped for the seismic batch - member deflection is not checked at
        # ULS/SEISMIC, and the per-node displacements are collected separately)
        def local_vw(tag: int) -> Tuple[float, float]:
            d = ops.nodeDisp(tag)
            return (_dot(d[:3], mmap.yh), _dot(d[:3], mmap.zh))

        if with_defl:
            v_i, w_i = local_vw(mmap.segments[0].tag_i)
            v_j, w_j = local_vw(mmap.segments[-1].tag_j)

        def chord_defl(tag: int, x: float) -> Tuple[float, float]:
            v, w = local_vw(tag)
            t = x / mmap.length
            return (v - (v_i + (v_j - v_i) * t),
                    w - (w_i + (w_j - w_i) * t))

        for k, seg in enumerate(mmap.segments):
            lf = ops.eleResponse(seg.ele_tag, "localForce")
            fxi, fyi, fzi, mxi, myi, mzi = lf[0], lf[1], lf[2], lf[3], lf[4], lf[5]

            def section_forces(x: float) -> Station:
                return Station(
                    x=seg.x_start + x,
                    N=-(fxi + seg.wx * x),
                    Vy=fyi + seg.wy * x,
                    Vz=-(fzi + seg.wz * x),
                    T=-mxi,
                    My=-myi - fzi * x - seg.wz * x * x / 2.0,
                    Mz=-mzi + fyi * x + seg.wy * x * x / 2.0,
                )

            xs = [0.0]
            if abs(seg.wy) > 1.0e-12:           # Mz parabola vertex
                xv = -fyi / seg.wy
                if 0.0 < xv < seg.length:
                    xs.append(xv)
            if abs(seg.wz) > 1.0e-12:           # My parabola vertex
                xv = -fzi / seg.wz
                if 0.0 < xv < seg.length:
                    xs.append(xv)
            xs.append(seg.length)

            for x in sorted(set(xs)):
                if k > 0 and x == 0.0:
                    continue                     # avoid duplicate stations
                st = section_forces(x)
                if not with_defl:
                    mr.stations.append(st)
                    continue
                if x == 0.0:
                    st.defl_y, st.defl_z = chord_defl(seg.tag_i, seg.x_start)
                elif x == seg.length:
                    st.defl_y, st.defl_z = chord_defl(seg.tag_j,
                                                      seg.x_start + seg.length)
                else:
                    dyi, dzi = chord_defl(seg.tag_i, seg.x_start)
                    dyj, dzj = chord_defl(seg.tag_j, seg.x_start + seg.length)
                    t = x / seg.length
                    st.defl_y = dyi + (dyj - dyi) * t
                    st.defl_z = dzi + (dzj - dzi) * t
                mr.stations.append(st)
        return mr


# --------------------------------------------------------------------- math
def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b) -> Tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _local_yz(xh, vecxz):
    """Local y and z unit vectors for member axis xh, following the model's
    default convention when vecxz is None (see rack15512.model)."""
    if vecxz is None:
        if abs(xh[2]) > 0.999:                  # vertical member
            vecxz = (0.0, 1.0, 0.0)
        else:
            vecxz = _cross(xh, (0.0, 0.0, 1.0))
    yh = _cross(vecxz, xh)
    n = math.sqrt(_dot(yh, yh))
    if n < 1.0e-12:
        raise ValueError("member vecxz is parallel to the member axis")
    yh = (yh[0] / n, yh[1] / n, yh[2] / n)
    zh = _cross(xh, yh)
    return yh, zh

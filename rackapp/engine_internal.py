"""Built-in 3D frame FEA engine.

Capabilities (what EN 15512 needs for the full rack model):
  * 12-DOF Euler-Bernoulli space beam-column elements (axial, torsion,
    biaxial bending) -> My AND Mz internal moments for biaxial checks
  * truss members (axial only) for the cross-aisle frame bracing
  * semi-rigid member ends: rotational springs about local y and/or z,
    condensed into the element (internal end-rotation DOFs eliminated)
  * semi-rigid supports: rotational springs to ground about global X / Y
  * second-order (P-Delta) analysis: geometric stiffness in both bending
    planes, iterated until the displacement increment converges
  * line loads (consistent, condensed fixed-end forces) and nodal loads

DOFs per node: [ux, uy, uz, rx, ry, rz]  (global; X down-aisle, Z up).

Member local axes: local x from node i to j; for non-vertical members the
local y axis is horizontal (z_g x x_l) so local z points "up"; for vertical
members local y = global Y, local z = -global X. Hence for uprights, section
Iy governs down-aisle bending and Iz cross-aisle bending; for beams, Iy is
the major (vertical-plane) axis.
"""

from __future__ import annotations

import numpy as np

from .model import RackModel, Member, RIGID
from .loads import LoadCase, Combination
from .results import AnalysisResults, ComboResult, MemberResult, NodeResult, Reaction

NDOF = 6  # per node

# local DOF indices of the end rotations that can be released
REL_RY1, REL_RZ1, REL_RY2, REL_RZ2 = 4, 5, 10, 11


class SingularModelError(RuntimeError):
    pass


def _bend_block(EI: float, L: float, sign: float) -> np.ndarray:
    """4x4 bending block for (v1, r1, v2, r2).
    sign=+1: (uy, rz) plane (about local z); sign=-1: (uz, ry) plane."""
    a = 12 * EI / L**3
    b = sign * 6 * EI / L**2
    c = 4 * EI / L
    d = 2 * EI / L
    return np.array([
        [a, b, -a, b],
        [b, c, -b, d],
        [-a, -b, a, -b],
        [b, d, -b, c],
    ])


def _geo_block(N: float, L: float, sign: float) -> np.ndarray:
    """Geometric stiffness bending block, same DOF ordering as _bend_block."""
    a = 1.2 * N / L
    b = sign * N / 10.0
    c = 2.0 * N * L / 15.0
    d = -N * L / 30.0
    return np.array([
        [a, b, -a, b],
        [b, c, -b, d],
        [-a, -b, a, -b],
        [b, d, -b, c],
    ])


# local DOF indices of the two bending planes
PLANE_Z = [1, 5, 7, 11]    # (uy1, rz1, uy2, rz2), bending about local z
PLANE_Y = [2, 4, 8, 10]    # (uz1, ry1, uz2, ry2), bending about local y


def _rotation(dx: float, dy: float, dz: float, L: float) -> np.ndarray:
    """3x3 matrix with rows = local x, y, z axes in global coordinates."""
    x = np.array([dx, dy, dz]) / L
    if abs(x[2]) > 0.9999:                  # vertical member
        y = np.array([0.0, 1.0, 0.0])
    else:
        y = np.cross([0.0, 0.0, 1.0], x)
        y /= np.linalg.norm(y)
    z = np.cross(x, y)
    return np.vstack([x, y, z])


class _Element:
    """Space frame element with optional rotational end springs.

    Full DOF vector: 12 nodal DOFs + one internal DOF per released end
    rotation (about local y/z at either end). The spring couples the nodal
    rotation to the internal beam-end rotation; the internal DOFs are
    condensed out before assembly.
    """

    def __init__(self, member: Member, model: RackModel):
        self.member = member
        xi, yi, zi = model.node_coords(member.node_i)
        xj, yj, zj = model.node_coords(member.node_j)
        self.L = float(np.sqrt((xj - xi) ** 2 + (yj - yi) ** 2 + (zj - zi) ** 2))
        self.R = _rotation(xj - xi, yj - yi, zj - zi, self.L)
        self.E, self.G = model.E, model.G
        self.sec = member.section
        self.is_truss = member.behavior == "truss"

        # releases: (local dof index, spring stiffness)
        self.releases: list[tuple[int, float]] = []
        if not self.is_truss:
            for hinge, ry_idx, rz_idx in (
                (member.hinge_i, REL_RY1, REL_RZ1),
                (member.hinge_j, REL_RY2, REL_RZ2),
            ):
                if hinge is None:
                    continue
                if hinge.my is not RIGID:
                    self.releases.append((ry_idx, max(hinge.my, 0.0)))
                if hinge.mz is not RIGID:
                    self.releases.append((rz_idx, max(hinge.mz, 0.0)))
        self.n_int = len(self.releases)
        # beam matrix DOF -> full-vector position (released rotations are
        # redirected to the internal DOFs appended after the 12 nodal ones)
        self.beam_map = list(range(12))
        for k, (dof, _) in enumerate(self.releases):
            self.beam_map[dof] = 12 + k

        self.k12 = self._k12_elastic()
        self.qy = 0.0       # local y line load (N/m)
        self.qz = 0.0       # local z line load (N/m)
        self.qa = 0.0       # local axial line load (N/m)
        self.N = 0.0        # axial force for geometric stiffness (tension +)

    # -- local matrices --------------------------------------------------------
    def _k12_elastic(self) -> np.ndarray:
        k = np.zeros((12, 12))
        L, E, sec = self.L, self.E, self.sec
        ea = E * sec.A / L
        k[0, 0] = k[6, 6] = ea
        k[0, 6] = k[6, 0] = -ea
        if self.is_truss:
            return k
        gj = self.G * sec.J / L
        k[3, 3] = k[9, 9] = gj
        k[3, 9] = k[9, 3] = -gj
        k[np.ix_(PLANE_Z, PLANE_Z)] += _bend_block(E * sec.Iz, L, +1.0)
        k[np.ix_(PLANE_Y, PLANE_Y)] += _bend_block(E * sec.Iy, L, -1.0)
        return k

    def _kg12(self) -> np.ndarray:
        kg = np.zeros((12, 12))
        if self.N == 0.0:
            return kg
        if self.is_truss:
            c = self.N / self.L
            for i, j in ((1, 7), (2, 8)):
                kg[i, i] += c
                kg[j, j] += c
                kg[i, j] -= c
                kg[j, i] -= c
            return kg
        kg[np.ix_(PLANE_Z, PLANE_Z)] += _geo_block(self.N, self.L, +1.0)
        kg[np.ix_(PLANE_Y, PLANE_Y)] += _geo_block(self.N, self.L, -1.0)
        return kg

    # -- full (12 + n_int) system ----------------------------------------------
    def _k_full(self, geometric: bool) -> np.ndarray:
        n = 12 + self.n_int
        K = np.zeros((n, n))
        k12 = self.k12 + self._kg12() if geometric else self.k12
        bm = self.beam_map
        for a in range(12):
            for b in range(12):
                K[bm[a], bm[b]] += k12[a, b]
        for k_idx, (dof, ks) in enumerate(self.releases):
            i, j = dof, 12 + k_idx
            K[i, i] += ks
            K[j, j] += ks
            K[i, j] -= ks
            K[j, i] -= ks
        return K

    def _f_full(self) -> np.ndarray:
        """Consistent (clamped) equivalent nodal forces for the line loads.
        Rotational components go to the beam DOFs (internal when released)."""
        n = 12 + self.n_int
        f = np.zeros(n)
        L, bm = self.L, self.beam_map
        if self.is_truss:
            # lumped: half of everything to each end, translations only
            for comp, q in ((0, self.qa), (1, self.qy), (2, self.qz)):
                f[comp] += q * L / 2
                f[comp + 6] += q * L / 2
            return f
        f12 = np.zeros(12)
        f12[0] += self.qa * L / 2
        f12[6] += self.qa * L / 2
        # local y load -> bending about z: (uy, rz) plane, +6L sign pattern
        f12[1] += self.qy * L / 2
        f12[7] += self.qy * L / 2
        f12[5] += self.qy * L**2 / 12
        f12[11] -= self.qy * L**2 / 12
        # local z load -> bending about y: theta_y = -dw/dx, signs flip
        f12[2] += self.qz * L / 2
        f12[8] += self.qz * L / 2
        f12[4] -= self.qz * L**2 / 12
        f12[10] += self.qz * L**2 / 12
        for a in range(12):
            f[bm[a]] += f12[a]
        return f

    def condensed(self, geometric: bool) -> tuple[np.ndarray, np.ndarray]:
        """12x12 condensed stiffness and 12-vector condensed load, local."""
        K = self._k_full(geometric)
        f = self._f_full()
        if self.n_int == 0:
            return K, f
        a = list(range(12))
        b = list(range(12, 12 + self.n_int))
        kaa, kab = K[np.ix_(a, a)], K[np.ix_(a, b)]
        kba, kbb = K[np.ix_(b, a)], K[np.ix_(b, b)]
        kbb_inv = np.linalg.inv(kbb)
        return kaa - kab @ kbb_inv @ kba, f[a] - kab @ kbb_inv @ f[b]

    def transform(self) -> np.ndarray:
        T = np.zeros((12, 12))
        for blk in range(4):
            T[3 * blk:3 * blk + 3, 3 * blk:3 * blk + 3] = self.R
        return T

    def k_global(self, geometric: bool) -> tuple[np.ndarray, np.ndarray]:
        kc, fc = self.condensed(geometric)
        T = self.transform()
        return T.T @ kc @ T, T.T @ fc

    # -- result recovery ---------------------------------------------------------
    def recover(self, u_nodal_global: np.ndarray, geometric: bool
                ) -> tuple[np.ndarray, np.ndarray]:
        """Return (local end forces on the 12 nodal DOFs, beam-DOF vector).

        End forces f = [Fx1, Fy1, Fz1, Mx1, My1, Mz1, Fx2, ...] acting ON the
        member. The beam-DOF vector holds the 12 displacements/rotations of
        the beam proper (internal values where ends are released).
        """
        T = self.transform()
        ua = T @ u_nodal_global
        K = self._k_full(geometric)
        f = self._f_full()
        if self.n_int:
            a = list(range(12))
            b = list(range(12, 12 + self.n_int))
            kba, kbb = K[np.ix_(b, a)], K[np.ix_(b, b)]
            ub = np.linalg.solve(kbb, f[b] - kba @ ua)
            u_full = np.concatenate([ua, ub])
        else:
            u_full = ua
        f_all = K @ u_full - f
        u_beam = np.array([u_full[self.beam_map[a]] for a in range(12)])
        return f_all[:12], u_beam

    def span_results(self, f_loc: np.ndarray, u_beam: np.ndarray
                     ) -> tuple[float, float]:
        """(max |My| along span, max local-z deflection relative to chord).

        Vertical-plane internal moment, sagging positive:
            My(x) = My1 + Fz1*x - qd*x^2/2,  qd = -qz (downward intensity),
        with My1, Fz1 the on-member end-1 local forces.
        """
        if self.is_truss:
            return 0.0, 0.0
        L, EI = self.L, self.E * self.sec.Iy
        qd = -self.qz
        Fz1, My1 = f_loc[2], f_loc[4]

        xs = [0.0, L / 2.0, L]
        if qd != 0.0 and 0.0 < Fz1 / qd < L:
            xs.append(Fz1 / qd)             # shear zero -> moment extremum
        m_max = max(abs(My1 + Fz1 * x - qd * x**2 / 2.0) for x in xs)

        # transverse deflection in local z: hermite interpolation of the
        # beam-proper end values (slope = -theta_y) + clamped UDL solution
        w1, w2 = u_beam[2], u_beam[8]
        r1, r2 = -u_beam[4], -u_beam[10]
        d_max = 0.0
        for i in range(1, 10):
            x = L * i / 10.0
            xi = x / L
            h1 = 1 - 3 * xi**2 + 2 * xi**3
            h2 = x * (1 - xi) ** 2
            h3 = 3 * xi**2 - 2 * xi**3
            h4 = x * (xi**2 - xi)
            w = h1 * w1 + h2 * r1 + h3 * w2 + h4 * r2
            if qd != 0.0:
                w -= qd * x**2 * (L - x) ** 2 / (24.0 * EI)
            chord = w1 + (w2 - w1) * xi
            d_max = max(d_max, abs(w - chord))
        return m_max, d_max


class InternalEngine:
    """Direct-stiffness 3D frame solver with P-Delta iteration."""

    name = "internal"

    def __init__(self, max_iterations: int = 15, tolerance: float = 1e-8):
        self.max_iterations = max_iterations
        self.tolerance = tolerance

    def analyze(self, model: RackModel, load_cases: dict[str, LoadCase],
                combinations: list[Combination]) -> AnalysisResults:
        results = AnalysisResults(engine=self.name)
        for combo in combinations:
            results.combos[combo.id] = self._solve_combo(model, load_cases, combo)
        return results

    # -------------------------------------------------------------------------
    def _solve_combo(self, model: RackModel, load_cases: dict[str, LoadCase],
                     combo: Combination) -> ComboResult:
        node_ids = sorted(model.nodes)
        index = {nid: i for i, nid in enumerate(node_ids)}
        n_dof = NDOF * len(node_ids)

        elements = {mid: _Element(m, model) for mid, m in model.members.items()}

        # factored loads
        F = np.zeros(n_dof)
        for lc_id, gamma in combo.factors.items():
            lc = load_cases.get(lc_id)
            if lc is None:
                continue
            for pl in lc.point_loads:
                i = index[pl.node] * NDOF
                F[i] += gamma * pl.fx
                F[i + 1] += gamma * pl.fy
                F[i + 2] += gamma * pl.fz
            for ll in lc.line_loads:
                el = elements[ll.member]
                # global Z line load -> local components via rotation matrix
                q_loc = el.R @ np.array([0.0, 0.0, gamma * ll.q])
                el.qa += q_loc[0]
                el.qy += q_loc[1]
                el.qz += q_loc[2]

        # boundary conditions: translations + torsion (rz) fixed at the base,
        # rotations about the horizontal axes on ground springs
        fixed: set[int] = set()
        springs: dict[int, float] = {}
        for sup in model.supports:
            i = index[sup.node] * NDOF
            fixed.update((i, i + 1, i + 2, i + 5))
            for off, ks in ((3, sup.rx_stiffness), (4, sup.ry_stiffness)):
                if ks is RIGID:
                    fixed.add(i + off)
                else:
                    springs[i + off] = springs.get(i + off, 0.0) + ks

        free = np.array([d for d in range(n_dof) if d not in fixed], dtype=int)

        # P-Delta iteration
        u = np.zeros(n_dof)
        iterations = 1
        converged = True
        max_iter = self.max_iterations if combo.second_order else 1
        for it in range(max_iter):
            iterations = it + 1
            geometric = combo.second_order and it > 0
            K = np.zeros((n_dof, n_dof))
            Feq = np.zeros(n_dof)
            for el in elements.values():
                kg, fg = el.k_global(geometric)
                dofs = _element_dofs(el.member, index)
                K[np.ix_(dofs, dofs)] += kg
                Feq[dofs] += fg
            for d, ks in springs.items():
                K[d, d] += ks

            u_new = np.zeros(n_dof)
            if free.size:
                try:
                    u_new[free] = np.linalg.solve(
                        K[np.ix_(free, free)], (F + Feq)[free])
                except np.linalg.LinAlgError as exc:
                    raise SingularModelError(
                        f"combination {combo.id}: stiffness matrix singular "
                        f"(structure unstable or buckled)"
                    ) from exc

            if combo.second_order:
                for el in elements.values():
                    dofs = _element_dofs(el.member, index)
                    f_loc, _ = el.recover(u_new[dofs], geometric=False)
                    el.N = f_loc[6]     # axial at end 2, tension positive
                du = np.linalg.norm(u_new - u)
                ref = max(np.linalg.norm(u_new), 1e-12)
                u = u_new
                if it > 0 and du / ref < self.tolerance:
                    break
            else:
                u = u_new
                break
        else:
            # loop exhausted without break: only possible for 2nd-order runs
            converged = False

        if not np.all(np.isfinite(u)):
            raise SingularModelError(f"combination {combo.id}: divergence (buckling)")

        return self._collect(model, elements, index, u, F, combo,
                             iterations, converged)

    # -------------------------------------------------------------------------
    def _collect(self, model: RackModel, elements: dict[int, "_Element"],
                 index: dict[int, int], u: np.ndarray, F: np.ndarray,
                 combo: Combination, iterations: int,
                 converged: bool) -> ComboResult:
        res = ComboResult(combo_id=combo.id, second_order=combo.second_order,
                          converged=converged, iterations=iterations)
        for nid, i in index.items():
            d = i * NDOF
            res.nodes[nid] = NodeResult(
                ux=float(u[d]), uy=float(u[d + 1]), uz=float(u[d + 2]),
                rx=float(u[d + 3]), ry=float(u[d + 4]), rz=float(u[d + 5]),
            )

        geometric = combo.second_order
        for mid, el in elements.items():
            dofs = _element_dofs(el.member, index)
            f, u_beam = el.recover(u[dofs], geometric)
            my_max, d_max = el.span_results(f, u_beam)
            res.members[mid] = MemberResult(
                # internal-force convention: end 1 components negated where
                # the on-member force opposes the internal force direction
                N1=float(-f[0]), Vy1=float(f[1]), Vz1=float(f[2]),
                Mt1=float(-f[3]), My1=float(f[4]), Mz1=float(f[5]),
                N2=float(f[6]), Vy2=float(-f[7]), Vz2=float(-f[8]),
                Mt2=float(f[9]), My2=float(-f[10]), Mz2=float(-f[11]),
                My_span_max=float(my_max), defl_rel_max=float(d_max),
            )

        # support reactions from equilibrium of the supported nodes
        for sup in model.supports:
            i = index[sup.node] * NDOF
            r = Reaction()
            for el in elements.values():
                m = el.member
                if sup.node not in (m.node_i, m.node_j):
                    continue
                dofs = _element_dofs(m, index)
                f_loc, _ = el.recover(u[dofs], geometric)
                fg = el.transform().T @ f_loc
                off = 0 if m.node_i == sup.node else 6
                r.fx += fg[off]
                r.fy += fg[off + 1]
                r.fz += fg[off + 2]
                r.mx += fg[off + 3]
                r.my += fg[off + 4]
            r.fx = float(r.fx - F[i])
            r.fy = float(r.fy - F[i + 1])
            r.fz = float(r.fz - F[i + 2])
            r.mx = float(r.mx)
            r.my = float(r.my)
            res.reactions[sup.node] = r
        return res


def _element_dofs(member: Member, index: dict[int, int]) -> list[int]:
    i, j = index[member.node_i] * NDOF, index[member.node_j] * NDOF
    return list(range(i, i + 6)) + list(range(j, j + 6))

"""Built-in 2D frame FEA engine.

Capabilities (the subset EN 15512 needs for the down-aisle spine model):
  * Euler-Bernoulli beam-column elements in the XZ plane
  * semi-rigid member ends: rotational springs condensed into the element
    (internal end-rotation DOFs eliminated by static condensation)
  * semi-rigid supports: rotational spring to ground at base nodes
  * second-order (P-Delta) analysis: geometric stiffness, iterated until
    the displacement increment converges
  * line loads (consistent, condensed fixed-end forces) and nodal loads

DOFs per node: [ux, uz, ry]   (X right, Z up, ry counter-clockwise)

Sign conventions for results follow `results.MemberResult`.
"""

from __future__ import annotations

import numpy as np

from .model import RackModel, Member, RIGID
from .loads import LoadCase, Combination
from .results import AnalysisResults, ComboResult, MemberResult, NodeResult, Reaction

NDOF = 3  # per node


class SingularModelError(RuntimeError):
    pass


def _beam_k6(E: float, A: float, I: float, L: float) -> np.ndarray:
    """Local elastic stiffness, DOFs [u1, w1, r1, u2, w2, r2]."""
    k = np.zeros((6, 6))
    ea, ei = E * A / L, E * I
    k[0, 0] = k[3, 3] = ea
    k[0, 3] = k[3, 0] = -ea
    c1, c2, c3, c4 = 12 * ei / L**3, 6 * ei / L**2, 4 * ei / L, 2 * ei / L
    k[1, 1] = k[4, 4] = c1
    k[1, 4] = k[4, 1] = -c1
    k[1, 2] = k[2, 1] = k[1, 5] = k[5, 1] = c2
    k[2, 4] = k[4, 2] = k[4, 5] = k[5, 4] = -c2
    k[2, 2] = k[5, 5] = c3
    k[2, 5] = k[5, 2] = c4
    return k


def _beam_kg6(N: float, L: float) -> np.ndarray:
    """Local geometric stiffness for axial force N (tension positive)."""
    kg = np.zeros((6, 6))
    c = N / L
    kg[1, 1] = kg[4, 4] = 1.2 * c
    kg[1, 4] = kg[4, 1] = -1.2 * c
    s = c * L / 10.0
    kg[1, 2] = kg[2, 1] = kg[1, 5] = kg[5, 1] = s
    kg[2, 4] = kg[4, 2] = kg[4, 5] = kg[5, 4] = -s
    kg[2, 2] = kg[5, 5] = 2.0 * c * L**2 / 15.0
    kg[2, 5] = kg[5, 2] = -c * L**2 / 30.0
    return kg


class _Element:
    """Beam element with optional rotational end springs.

    Internal 8-DOF vector: [ux1, uz1, rn1, ux2, uz2, rn2, ri1, ri2]
    where rn = nodal rotation, ri = beam-end rotation. The springs connect
    rn<->ri; rigid ends tie them with a large penalty stiffness.
    The two internal rotations (indices 6, 7) are condensed out.
    """

    A_IDX = [0, 1, 2, 3, 4, 5]
    B_IDX = [6, 7]
    BEAM_MAP = [0, 1, 6, 3, 4, 7]   # beam k6 acts on these 8-DOF positions

    def __init__(self, member: Member, model: RackModel, E: float):
        self.member = member
        xi, zi = model.node_coords(member.node_i)
        xj, zj = model.node_coords(member.node_j)
        self.L = float(np.hypot(xj - xi, zj - zi))
        self.c = (xj - xi) / self.L
        self.s = (zj - zi) / self.L
        self.E = E
        sec = member.section
        self.k6 = _beam_k6(E, sec.A, sec.Iy, self.L)
        k_rigid = 1e6 * 4.0 * E * sec.Iy / self.L
        self.k_spring = [
            k_rigid if (h is None or h.stiffness is RIGID) else max(h.stiffness, 1e-9)
            for h in (member.hinge_i, member.hinge_j)
        ]
        self.q_local = 0.0      # transverse line load, negative = "downwards"
        self.qa_local = 0.0     # axial line load (local x direction)
        self.N = 0.0            # axial force for geometric stiffness

    # -- 8x8 assembly ---------------------------------------------------------
    def _k8(self, geometric: bool) -> np.ndarray:
        k8 = np.zeros((8, 8))
        k6 = self.k6.copy()
        if geometric and self.N != 0.0:
            k6 = k6 + _beam_kg6(self.N, self.L)
        for a, ia in enumerate(self.BEAM_MAP):
            for b, ib in enumerate(self.BEAM_MAP):
                k8[ia, ib] += k6[a, b]
        for end, (rn, ri) in enumerate(((2, 6), (5, 7))):
            ks = self.k_spring[end]
            k8[rn, rn] += ks
            k8[ri, ri] += ks
            k8[rn, ri] -= ks
            k8[ri, rn] -= ks
        return k8

    def _f8(self) -> np.ndarray:
        """Consistent (clamped) equivalent nodal forces for the line load,
        applied at the *beam* DOFs (rotations go to the internal DOFs)."""
        f8 = np.zeros(8)
        q, qa, L = self.q_local, self.qa_local, self.L
        if q != 0.0 or qa != 0.0:
            f6 = np.array([qa * L / 2, q * L / 2, q * L**2 / 12,
                           qa * L / 2, q * L / 2, -q * L**2 / 12])
            for a, ia in enumerate(self.BEAM_MAP):
                f8[ia] += f6[a]
        return f8

    def condensed(self, geometric: bool) -> tuple[np.ndarray, np.ndarray]:
        """6x6 condensed stiffness and 6-vector condensed load, in local axes."""
        k8 = self._k8(geometric)
        f8 = self._f8()
        a, b = self.A_IDX, self.B_IDX
        kaa, kab = k8[np.ix_(a, a)], k8[np.ix_(a, b)]
        kba, kbb = k8[np.ix_(b, a)], k8[np.ix_(b, b)]
        kbb_inv = np.linalg.inv(kbb)
        kc = kaa - kab @ kbb_inv @ kba
        fc = f8[a] - kab @ kbb_inv @ f8[b]
        return kc, fc

    def transform(self) -> np.ndarray:
        """Local -> global rotation for the 6 nodal DOFs."""
        c, s = self.c, self.s
        t = np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])
        T = np.zeros((6, 6))
        T[:3, :3] = t
        T[3:, 3:] = t
        return T

    def k_global(self, geometric: bool) -> tuple[np.ndarray, np.ndarray]:
        kc, fc = self.condensed(geometric)
        T = self.transform()
        return T.T @ kc @ T, T.T @ fc

    # -- result recovery ------------------------------------------------------
    def end_forces(self, u_nodal_global: np.ndarray, geometric: bool) -> tuple[np.ndarray, np.ndarray]:
        """Return (local end forces on the 6 nodal DOFs, internal rotations).

        Local end forces f = [Fx1, Fy1, M1, Fx2, Fy2, M2] acting ON the member.
        """
        T = self.transform()
        ua = T @ u_nodal_global
        k8 = self._k8(geometric)
        f8 = self._f8()
        a, b = self.A_IDX, self.B_IDX
        kba, kbb = k8[np.ix_(b, a)], k8[np.ix_(b, b)]
        ub = np.linalg.solve(kbb, f8[b] - kba @ ua)
        u8 = np.concatenate([ua, ub])
        f_full = k8 @ u8 - np.concatenate([f8[a], f8[b]])
        return f_full[a], ub

    def span_results(self, f_local: np.ndarray, ua_local: np.ndarray,
                     ub: np.ndarray) -> tuple[float, float]:
        """(max |M| along span, max transverse deflection relative to chord).

        Internal moment, sagging positive:
            M(x) = -M1 + Fy1*x - qd*x^2/2,  qd = downward load intensity
        """
        L, EI = self.L, self.E * self.member.section.Iy
        qd = -self.q_local                      # downward positive
        Fy1, M1 = f_local[1], f_local[2]

        xs = [0.0, L / 2.0, L]
        if qd != 0.0 and 0.0 < Fy1 / qd < L:
            xs.append(Fy1 / qd)                 # shear zero -> moment extremum
        m_max = max(abs(-M1 + Fy1 * x - qd * x**2 / 2.0) for x in xs)

        # transverse deflection: hermite interpolation of the beam-proper end
        # values + clamped particular solution for the UDL
        w1, w2 = ua_local[1], ua_local[4]
        r1, r2 = ub[0], ub[1]
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
    """Direct-stiffness 2D frame solver with P-Delta iteration."""

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

        elements = {mid: _Element(m, model, model.E) for mid, m in model.members.items()}

        # factored loads
        F = np.zeros(n_dof)
        for lc_id, gamma in combo.factors.items():
            lc = load_cases.get(lc_id)
            if lc is None:
                continue
            for pl in lc.point_loads:
                i = index[pl.node] * NDOF
                F[i] += gamma * pl.fx
                F[i + 1] += gamma * pl.fz
            for ll in lc.line_loads:
                el = elements[ll.member]
                # global Z line load -> local transverse / axial components
                el.q_local += gamma * ll.q * el.c
                el.qa_local += gamma * ll.q * el.s

        # boundary conditions: fixed DOF list + ground springs
        fixed: set[int] = set()
        springs: dict[int, float] = {}
        for sup in model.supports:
            i = index[sup.node] * NDOF
            fixed.update((i, i + 1))
            if sup.ry_stiffness is RIGID:
                fixed.add(i + 2)
            else:
                springs[i + 2] = springs.get(i + 2, 0.0) + sup.ry_stiffness

        # fully restrained models (all nodal DOFs fixed) are still valid:
        # forces then come purely from the condensed fixed-end actions
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
                Kff = K[np.ix_(free, free)]
                rhs = (F + Feq)[free]
                try:
                    uf = np.linalg.solve(Kff, rhs)
                except np.linalg.LinAlgError as exc:
                    raise SingularModelError(
                        f"combination {combo.id}: stiffness matrix singular "
                        f"(structure unstable or buckled)"
                    ) from exc
                u_new[free] = uf

            if combo.second_order:
                # update element axial forces for the geometric stiffness
                for el in elements.values():
                    dofs = _element_dofs(el.member, index)
                    f_loc, _ = el.end_forces(u_new[dofs], geometric=False)
                    el.N = f_loc[3]     # axial force at end 2, tension positive
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

        # sanity: amplification should not explode
        if not np.all(np.isfinite(u)):
            raise SingularModelError(f"combination {combo.id}: divergence (buckling)")

        return self._collect(model, elements, index, u, F, combo, iterations, converged)

    # -------------------------------------------------------------------------
    def _collect(self, model: RackModel, elements: dict[int, "_Element"],
                 index: dict[int, int], u: np.ndarray, F: np.ndarray,
                 combo: Combination, iterations: int, converged: bool) -> ComboResult:
        res = ComboResult(combo_id=combo.id, second_order=combo.second_order,
                          converged=converged, iterations=iterations)
        for nid, i in index.items():
            d = i * NDOF
            res.nodes[nid] = NodeResult(ux=float(u[d]), uz=float(u[d + 1]),
                                        ry=float(u[d + 2]))

        geometric = combo.second_order
        for mid, el in elements.items():
            dofs = _element_dofs(el.member, index)
            f_loc, ub = el.end_forces(u[dofs], geometric)
            ua_local = el.transform() @ u[dofs]
            m_max, d_max = el.span_results(f_loc, ua_local, ub)
            res.members[mid] = MemberResult(
                N1=float(-f_loc[0]), V1=float(f_loc[1]), M1=float(f_loc[2]),
                N2=float(f_loc[3]), V2=float(-f_loc[4]), M2=float(-f_loc[5]),
                M_span_max=float(m_max), defl_rel_max=float(d_max),
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
                f_loc, _ = el.end_forces(u[dofs], geometric)
                fg = el.transform().T @ f_loc
                off = 0 if m.node_i == sup.node else 3
                r.fx += fg[off]
                r.fz += fg[off + 1]
                r.my += fg[off + 2]
            r.fx = float(r.fx - F[i])
            r.fz = float(r.fz - F[i + 1])
            r.my = float(r.my)
            res.reactions[sup.node] = r
        return res


def _element_dofs(member: Member, index: dict[int, int]) -> list[int]:
    i, j = index[member.node_i] * NDOF, index[member.node_j] * NDOF
    return [i, i + 1, i + 2, j, j + 1, j + 2]

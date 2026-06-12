"""RFEM 6 engine adapter (Dlubal RFEM WebServices Python API).

RFEM 6 is the recommended production engine for EN 15512 rack analysis:
  * member hinges with rotational spring constants  -> beam-end connectors
  * nodal supports with rotational spring constants -> base-plate connection
  * second-order (P-Delta) / large-deformation analysis per load combination
  * imperfection cases, member sets, full result tables via the API
  * optional Steel Design add-on with rack-specific EN 15512 checks

Requirements:
  * RFEM 6 running with WebServices enabled
    (Options > Program Options > Web Services, default port 8081)
  * pip install RFEM  (Dlubal "RFEM_Python_Client";
    see https://github.com/Dlubal-Software/RFEM_Python_Client)

The adapter builds the model, runs all combinations and maps the RFEM result
tables back onto `results.AnalysisResults`, so the EN 15512 checks and report
work identically for both engines.

NOTE: the Dlubal client API evolves between releases; if a constructor
signature changed in your installed version, the mapping below is intentionally
kept in small helper functions that are easy to adjust.

Coordinate mapping: our model is X right / Z up; RFEM's global Z is positive
downwards, so z_rfem = -z and gravity loads use RFEM's +Z direction.
"""

from __future__ import annotations

from .config import RackConfig
from .model import RackModel, RIGID
from .loads import LoadCase, Combination
from .results import AnalysisResults, ComboResult, MemberResult, NodeResult, Reaction

INF = 1e14  # "rigid" spring constant used for fixed releases


class RFEMNotAvailableError(RuntimeError):
    pass


class RFEMEngine:
    name = "rfem"

    def __init__(self, cfg: RackConfig, url: str = "http://localhost:8081"):
        self.cfg = cfg
        self.url = url

    # -------------------------------------------------------------------------
    def analyze(self, model: RackModel, load_cases: dict[str, LoadCase],
                combinations: list[Combination]) -> AnalysisResults:
        rfem = self._import_client()
        self._build(rfem, model, load_cases, combinations)
        rfem["Calculate_all"]()
        return self._fetch_results(rfem, model, combinations)

    # -------------------------------------------------------------------------
    def _import_client(self) -> dict:
        try:
            from RFEM.initModel import Model, Calculate_all
            from RFEM.BasicObjects.node import Node
            from RFEM.BasicObjects.material import Material
            from RFEM.BasicObjects.section import Section
            from RFEM.BasicObjects.member import Member
            from RFEM.TypesForNodes.nodalSupport import NodalSupport
            from RFEM.TypesForMembers.memberHinge import MemberHinge
            from RFEM.LoadCasesAndCombinations.loadCase import LoadCase as RfLoadCase
            from RFEM.LoadCasesAndCombinations.loadCombination import LoadCombination
            from RFEM.LoadCasesAndCombinations.staticAnalysisSettings import (
                StaticAnalysisSettings,
            )
            from RFEM.Loads.nodalLoad import NodalLoad
            from RFEM.Loads.memberLoad import MemberLoad
            from RFEM.Results.resultTables import ResultTables
        except ImportError as exc:  # pragma: no cover - needs RFEM installed
            raise RFEMNotAvailableError(
                "The Dlubal RFEM Python client is not installed. "
                "Install it with `pip install RFEM` and make sure RFEM 6 is "
                "running with WebServices enabled, or use engine 'internal'."
            ) from exc
        return dict(
            Model=Model, Calculate_all=Calculate_all, Node=Node,
            Material=Material, Section=Section, Member=Member,
            NodalSupport=NodalSupport, MemberHinge=MemberHinge,
            LoadCase=RfLoadCase, LoadCombination=LoadCombination,
            StaticAnalysisSettings=StaticAnalysisSettings,
            NodalLoad=NodalLoad, MemberLoad=MemberLoad,
            ResultTables=ResultTables,
        )

    # -------------------------------------------------------------------------
    def _build(self, rfem: dict, model: RackModel,
               load_cases: dict[str, LoadCase],
               combinations: list[Combination]) -> None:  # pragma: no cover
        cfg = self.cfg
        rfem["Model"](True, model.name)

        # material & sections
        rfem["Material"](1, cfg.material.name)
        upright_name = cfg.upright_section.rfem_section or cfg.upright_section.name
        beam_name = cfg.beam_section.rfem_section or cfg.beam_section.name
        rfem["Section"](1, upright_name, 1)
        rfem["Section"](2, beam_name, 1)
        section_no = {"upright": 1, "beam": 2}

        # nodes (flip Z: RFEM global Z is downwards)
        for n in model.nodes.values():
            rfem["Node"](n.id, n.x, 0.0, -n.z)

        # semi-rigid beam-end connector hinge: My on a rotational spring,
        # all other releases rigid
        hinge_no = 0
        hinge_map: dict[float, int] = {}
        for m in model.members.values():
            for h in (m.hinge_i, m.hinge_j):
                if h is not None and h.stiffness is not RIGID \
                        and h.stiffness not in hinge_map:
                    hinge_no += 1
                    hinge_map[h.stiffness] = hinge_no
                    rfem["MemberHinge"](
                        hinge_no, "Local", "",
                        INF, INF, INF,          # N, Vy, Vz releases (rigid)
                        INF, h.stiffness, INF,  # Mt, My (spring), Mz
                    )

        # members
        for m in model.members.values():
            hi = hinge_map.get(m.hinge_i.stiffness) if m.hinge_i else 0
            hj = hinge_map.get(m.hinge_j.stiffness) if m.hinge_j else 0
            rfem["Member"](
                m.id, m.node_i, m.node_j, 0.0,
                section_no[m.kind], section_no[m.kind],
                start_member_hinge=hi or 0,
                end_member_hinge=hj or 0,
            )

        # base supports: translations fixed, ry on a spring; the out-of-plane
        # DOFs are fixed to keep the 2D spine model stable in RFEM's 3D space
        for i, sup in enumerate(model.supports, start=1):
            ry = INF if sup.ry_stiffness is RIGID else sup.ry_stiffness
            rfem["NodalSupport"](
                i, str(sup.node),
                [INF, INF, INF, INF, ry, INF],   # ux, uy, uz, rx, ry(spring), rz
            )
        # lateral restraint of all non-base nodes (2D model)
        non_base = [n for n in model.nodes
                    if n not in {s.node for s in model.supports}]
        rfem["NodalSupport"](
            len(model.supports) + 1,
            " ".join(str(n) for n in non_base),
            [0, INF, 0, INF, 0, INF],            # uy, rx, rz fixed
        )

        # analysis settings: 1 = first order, 2 = second order (P-Delta)
        rfem["StaticAnalysisSettings"].GeometricallyLinear(1, "First order")
        rfem["StaticAnalysisSettings"].SecondOrderPDelta(2, "Second order")

        # load cases
        lc_no = {}
        for i, (lc_id, lc) in enumerate(load_cases.items(), start=1):
            lc_no[lc_id] = i
            rfem["LoadCase"](i, lc.name, [False])   # self weight handled by us
            nl = ml = 0
            for pl in lc.point_loads:
                nl += 1
                # FX is the same in both systems; FZ flips with the Z axis
                rfem["NodalLoad"].Components(
                    nl, i, str(pl.node), [pl.fx, 0.0, -pl.fz, 0, 0, 0]
                )
            for ll in lc.line_loads:
                ml += 1
                # our q is +Z(up); RFEM ZA(down) magnitude = -q
                rfem["MemberLoad"](ml, i, str(ll.member), magnitude=-ll.q)

        # combinations
        for i, combo in enumerate(combinations, start=1):
            items = [[gamma, lc_no[lc_id], 0, False]
                     for lc_id, gamma in combo.factors.items()
                     if lc_id in lc_no]
            rfem["LoadCombination"](
                i, analysis_type=2 if combo.second_order else 1,
                design_situation=1, name=combo.name, to_solve=True,
                combination_items=items,
            )

    # -------------------------------------------------------------------------
    def _fetch_results(self, rfem: dict, model: RackModel,
                       combinations: list[Combination]
                       ) -> AnalysisResults:  # pragma: no cover
        from RFEM.enums import CaseObjectType

        results = AnalysisResults(engine=self.name)
        rt = rfem["ResultTables"]
        for i, combo in enumerate(combinations, start=1):
            cr = ComboResult(combo_id=combo.id, second_order=combo.second_order)

            for row in rt.NodesDeformations(
                    CaseObjectType.E_OBJECT_TYPE_LOAD_COMBINATION, i, ""):
                nid = int(row["node_no"])
                cr.nodes[nid] = NodeResult(
                    ux=float(row["displacement_x"]),
                    uz=-float(row["displacement_z"]),
                    ry=float(row["rotation_y"]),
                )

            forces: dict[int, dict] = {}
            for row in rt.MembersInternalForces(
                    CaseObjectType.E_OBJECT_TYPE_LOAD_COMBINATION, i, ""):
                mid = int(row["member_no"])
                f = forces.setdefault(
                    mid, dict(N1=0, V1=0, M1=0, N2=0, V2=0, M2=0, Mmax=0))
                x = float(row["location"])
                n, v, m = (float(row["internal_force_n"]),
                           float(row["internal_force_vz"]),
                           float(row["internal_force_my"]))
                f["Mmax"] = max(f["Mmax"], abs(m))
                if x == 0.0:
                    f.update(N1=n, V1=v, M1=m)
                else:
                    f.update(N2=n, V2=v, M2=m)
            for mid, f in forces.items():
                cr.members[mid] = MemberResult(
                    N1=f["N1"], V1=f["V1"], M1=f["M1"],
                    N2=f["N2"], V2=f["V2"], M2=f["M2"],
                    M_span_max=f["Mmax"],
                )

            for row in rt.MembersLocalDeformations(
                    CaseObjectType.E_OBJECT_TYPE_LOAD_COMBINATION, i, ""):
                mid = int(row["member_no"])
                if mid in cr.members:
                    d = abs(float(row["displacement_z"]))
                    cr.members[mid].defl_rel_max = max(
                        cr.members[mid].defl_rel_max, d)

            for row in rt.NodesSupportForces(
                    CaseObjectType.E_OBJECT_TYPE_LOAD_COMBINATION, i, ""):
                cr.reactions[int(row["node_no"])] = Reaction(
                    fx=float(row["support_force_p_x"]),
                    fz=-float(row["support_force_p_z"]),
                    my=float(row["support_moment_m_y"]),
                )

            results.combos[combo.id] = cr
        return results

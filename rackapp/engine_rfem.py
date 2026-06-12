"""RFEM 6 engine adapter (Dlubal RFEM WebServices Python API) - 3D model.

RFEM 6 is the recommended production engine for EN 15512 rack analysis:
  * member hinges with rotational spring constants  -> beam-end connectors
  * nodal supports with rotational spring constants -> base-plate connection
  * truss member type for the cross-aisle frame bracing
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

Coordinate mapping: our model is X down-aisle / Y cross-aisle / Z up; RFEM's
global Z is positive downwards, so z_rfem = -z (X and Y map directly) and
vertical loads flip sign.
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
        section_no = {}
        for no, (kind, sec) in enumerate((
            ("upright", cfg.upright_section),
            ("beam", cfg.beam_section),
            ("brace", cfg.brace_section),
        ), start=1):
            rfem["Section"](no, sec.rfem_section or sec.name, 1)
            section_no[kind] = no

        # nodes (flip Z: RFEM global Z is downwards)
        for n in model.nodes.values():
            rfem["Node"](n.id, n.x, n.y, -n.z)

        # semi-rigid beam-end connector hinge: My on a rotational spring,
        # Mz pinned or rigid per config, the rest rigid
        hinge_no = 0
        hinge_map: dict[tuple, int] = {}
        for m in model.members.values():
            for h in (m.hinge_i, m.hinge_j):
                if h is None:
                    continue
                key = (h.my, h.mz)
                if key in hinge_map:
                    continue
                hinge_no += 1
                hinge_map[key] = hinge_no
                my = INF if h.my is RIGID else h.my
                mz = INF if h.mz is RIGID else h.mz
                rfem["MemberHinge"](
                    hinge_no, "Local", "",
                    INF, INF, INF,      # N, Vy, Vz releases (rigid)
                    INF, my, mz,        # Mt, My (spring), Mz
                )

        # members (braces as truss type)
        for m in model.members.values():
            hi = hinge_map.get((m.hinge_i.my, m.hinge_i.mz)) if m.hinge_i else 0
            hj = hinge_map.get((m.hinge_j.my, m.hinge_j.mz)) if m.hinge_j else 0
            sec_no = section_no[m.kind]
            if m.behavior == "truss":
                rfem["Member"].Truss(m.id, m.node_i, m.node_j, 0.0, sec_no)
            else:
                rfem["Member"](
                    m.id, m.node_i, m.node_j, 0.0, sec_no, sec_no,
                    start_member_hinge=hi or 0,
                    end_member_hinge=hj or 0,
                )

        # base supports: translations + torsion fixed, rx/ry on springs.
        # Note RFEM axes: our rx (about X) keeps its axis, our ry likewise;
        # only Z flips, which does not affect the horizontal rotation axes.
        for i, sup in enumerate(model.supports, start=1):
            rx = INF if sup.rx_stiffness is RIGID else sup.rx_stiffness
            ry = INF if sup.ry_stiffness is RIGID else sup.ry_stiffness
            rfem["NodalSupport"](
                i, str(sup.node),
                [INF, INF, INF, rx, ry, INF],   # ux, uy, uz, rx, ry, rz
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
                # X/Y map directly; FZ flips with the Z axis
                rfem["NodalLoad"].Components(
                    nl, i, str(pl.node), [pl.fx, pl.fy, -pl.fz, 0, 0, 0]
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
                    uy=float(row["displacement_y"]),
                    uz=-float(row["displacement_z"]),
                    rx=float(row["rotation_x"]),
                    ry=float(row["rotation_y"]),
                    rz=float(row["rotation_z"]),
                )

            forces: dict[int, dict] = {}
            for row in rt.MembersInternalForces(
                    CaseObjectType.E_OBJECT_TYPE_LOAD_COMBINATION, i, ""):
                mid = int(row["member_no"])
                f = forces.setdefault(mid, dict(
                    N1=0, Vy1=0, Vz1=0, Mt1=0, My1=0, Mz1=0,
                    N2=0, Vy2=0, Vz2=0, Mt2=0, My2=0, Mz2=0,
                    Mymax=0.0, started=False))
                x = float(row["location"])
                vals = dict(
                    N=float(row["internal_force_n"]),
                    Vy=float(row.get("internal_force_vy", 0.0)),
                    Vz=float(row["internal_force_vz"]),
                    Mt=float(row.get("internal_force_mt", 0.0)),
                    My=float(row["internal_force_my"]),
                    Mz=float(row.get("internal_force_mz", 0.0)),
                )
                f["Mymax"] = max(f["Mymax"], abs(vals["My"]))
                end = "1" if x == 0.0 else "2"
                if end == "1" and f["started"]:
                    continue
                for k, v in vals.items():
                    f[k + end] = v
                f["started"] = True
            for mid, f in forces.items():
                cr.members[mid] = MemberResult(
                    N1=f["N1"], Vy1=f["Vy1"], Vz1=f["Vz1"],
                    Mt1=f["Mt1"], My1=f["My1"], Mz1=f["Mz1"],
                    N2=f["N2"], Vy2=f["Vy2"], Vz2=f["Vz2"],
                    Mt2=f["Mt2"], My2=f["My2"], Mz2=f["Mz2"],
                    My_span_max=f["Mymax"],
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
                    fy=float(row.get("support_force_p_y", 0.0)),
                    fz=-float(row["support_force_p_z"]),
                    mx=float(row.get("support_moment_m_x", 0.0)),
                    my=float(row["support_moment_m_y"]),
                )

            results.combos[combo.id] = cr
        return results

"""JSON serialization of the rack model (the app's input file format)."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict

from .model import (AnalysisSettings, BasePlate, CheckSettings, Combination,
                    CrossSection, Hinge, Imperfection, Link, LoadCase, Member,
                    MemberLoad, NodalLoad, Node, RackModel, Splice, Steel,
                    Support)


def model_to_dict(m: RackModel) -> Dict[str, Any]:
    return {
        "name": m.name,
        "materials": [asdict(x) for x in m.materials.values()],
        "sections": [asdict(x) for x in m.sections.values()],
        "nodes": [asdict(x) for x in m.nodes.values()],
        "members": [asdict(x) for x in m.members.values()],
        "supports": [asdict(x) for x in m.supports],
        "load_cases": [asdict(x) for x in m.load_cases.values()],
        "combinations": [asdict(x) for x in m.combinations],
        "imperfection": asdict(m.imperfection),
        "analysis": asdict(m.analysis),
        "checks": asdict(m.checks),
        "base_plate": asdict(m.base_plate) if m.base_plate else None,
        "splices": [asdict(s) for s in m.splices],
        "links": [asdict(x) for x in m.links],
    }


def model_from_dict(d: Dict[str, Any]) -> RackModel:
    m = RackModel(name=d.get("name", "rack"))
    for x in d.get("materials", []):
        m.materials[x["name"]] = Steel(**x)
    for x in d.get("sections", []):
        m.sections[x["name"]] = CrossSection(**x)
    for x in d.get("nodes", []):
        m.nodes[x["id"]] = Node(**x)
    for x in d.get("members", []):
        x = dict(x)
        for h in ("hinge_i", "hinge_j"):
            if x.get(h) is not None:
                x[h] = Hinge(**x[h])
        if x.get("vecxz") is not None:
            x["vecxz"] = tuple(x["vecxz"])
        m.members[x["id"]] = Member(**x)
    for x in d.get("supports", []):
        m.supports.append(Support(**x))
    for x in d.get("load_cases", []):
        x = dict(x)
        x["nodal_loads"] = [NodalLoad(**n) for n in x.get("nodal_loads", [])]
        x["member_loads"] = [MemberLoad(**n) for n in x.get("member_loads", [])]
        m.load_cases[x["name"]] = LoadCase(**x)
    for x in d.get("combinations", []):
        m.combinations.append(Combination(**x))
    if "imperfection" in d:
        m.imperfection = Imperfection(**d["imperfection"])
    if "analysis" in d:
        m.analysis = AnalysisSettings(**d["analysis"])
    if "checks" in d:
        m.checks = CheckSettings(**d["checks"])
    if d.get("base_plate"):
        m.base_plate = BasePlate(**d["base_plate"])
    for x in d.get("splices", []):
        m.splices.append(Splice(**x))
    for x in d.get("links", []):
        m.links.append(Link(**x))
    return m


def save(m: RackModel, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(model_to_dict(m), f, indent=2)


def load(path: str) -> RackModel:
    with open(path, encoding="utf-8") as f:
        return model_from_dict(json.load(f))

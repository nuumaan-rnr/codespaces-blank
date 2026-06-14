"""Per-zone seismic cost study: sweep bracing strategies and recommend the
lightest arrangement that passes all checks, for each IS 1893 seismic zone."""

from __future__ import annotations

import dataclasses
from typing import Dict, List, Optional

from .analysis import run_all
from .builder import RackConfig, build_rack
from .checks.en15512 import all_ok, governing, run_checks
from .seismic import RHO_STEEL, ZONE_FACTORS

# bracing strategies, cheapest -> strongest (mutations applied to the config)
STRATEGIES = [
    ("Bare frame", {}),
    ("Cross-aisle X", {"bracing_type": "X"}),
    ("Spine every 3rd", {"spine_bracing": True,
                         "spine_bracing_modules": "every_3rd"}),
    ("Spine alternate", {"spine_bracing": True,
                         "spine_bracing_modules": "alternate"}),
    ("Spine all + plan", {"spine_bracing": True,
                          "spine_bracing_modules": "all",
                          "plan_bracing": True}),
    ("CA-X + spine all + plan", {"bracing_type": "X", "spine_bracing": True,
                                 "spine_bracing_modules": "all",
                                 "plan_bracing": True}),
]


def steel_weight(model) -> float:
    """Total steel mass [kg] = sum(section.A * member_length * rho)."""
    w = 0.0
    for m in model.members.values():
        sec = model.sections.get(m.section)
        if sec:
            w += sec.A * model.member_length(m) * RHO_STEEL
    return w


def _evaluate(cfg: RackConfig) -> Dict:
    """Build + run one configuration, returning verdict / governing / weight."""
    model = build_rack(cfg)
    try:
        cases = run_all(model)
        checks = run_checks(model, cases)
    except Exception as exc:                       # analysis failure
        return {"verdict": "ERROR", "governing": str(exc),
                "max_util": None, "weight_kg": steel_weight(model)}
    gov = governing(checks)
    return {
        "verdict": "PASS" if all_ok(checks) else "FAIL",
        "governing": (f"{gov.check} {gov.utilization:.2f}" if gov else "-"),
        "governing_check": gov.check if gov else None,
        "max_util": round(gov.utilization, 3) if gov else None,
        "weight_kg": round(steel_weight(model), 1),
    }


def zone_study(cfg: RackConfig, *, zones=("II", "III", "IV", "V"),
               strategies: Optional[List] = None,
               spine_sections: Optional[List[str]] = None,
               progress=None) -> Dict:
    """For each zone, evaluate the bracing strategies and recommend the
    lightest passing one.  spine_sections, when given, are swept on the spine
    strategies to 'design' the spine C-section (lightest passing).

    ``progress(stage, frac)`` is called after each evaluated configuration so a
    UI can show a live progress bar for the (long) study."""
    strategies = strategies or STRATEGIES
    # total evaluations for the progress fraction
    n_sec = len(spine_sections) if spine_sections else 1
    total = sum(len(zones) * (n_sec if mut.get("spine_bracing") else 1)
                for _lbl, mut in strategies) or 1
    done = 0
    result: Dict[str, Dict] = {}
    for zone in zones:
        options = []
        for label, mut in strategies:
            secs = (spine_sections if spine_sections and mut.get("spine_bracing")
                    else [None])
            best_opt = None
            for sec in secs:
                m2 = dict(mut)
                if sec:
                    m2["spine_bracing_section"] = sec
                cfg2 = dataclasses.replace(
                    cfg, seismic=True, seismic_zone=zone, **m2)
                ev = _evaluate(cfg2)
                ev["label"] = label + (f" [{sec}]" if sec else "")
                done += 1
                if progress:
                    progress(f"Zone {zone}: {ev['label']} -> {ev['verdict']}",
                             done / total)
                # prefer the lightest passing within a section sweep
                if best_opt is None or (
                        ev["verdict"] == "PASS"
                        and (best_opt["verdict"] != "PASS"
                             or ev["weight_kg"] < best_opt["weight_kg"])):
                    best_opt = ev
            options.append(best_opt)
        passing = [o for o in options if o["verdict"] == "PASS"]
        recommended = (min(passing, key=lambda o: o["weight_kg"])
                       if passing else None)
        result[zone] = {
            "Z": ZONE_FACTORS.get(zone),
            "options": options,
            "recommended": recommended,
            "note": (None if recommended else
                     "No strategy in the set passes; increase sections / R "
                     "or add heavier bracing."),
        }
    return result

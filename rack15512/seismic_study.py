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


BUCKLING_CHECKS = {"BUCKLING", "BRACE_BUCKLING"}


def _evaluate(cfg: RackConfig) -> Dict:
    """Build + run one configuration, returning verdict / governing / weight /
    the set of failing (non-informative) check kinds."""
    model = build_rack(cfg)
    try:
        cases = run_all(model)
        checks = run_checks(model, cases)
    except Exception as exc:                       # analysis failure
        return {"verdict": "ERROR", "governing": str(exc), "max_util": None,
                "weight_kg": steel_weight(model), "fails": set()}
    gov = governing(checks)
    fails = {c.check for c in checks if not c.ok and not c.informative}
    return {
        "verdict": "PASS" if all_ok(checks) else "FAIL",
        "governing": (f"{gov.check} {gov.utilization:.2f}" if gov else "-"),
        "governing_check": gov.check if gov else None,
        "max_util": round(gov.utilization, 3) if gov else None,
        "weight_kg": round(steel_weight(model), 1),
        "fails": fails,
    }


def _beam_levels(cfg: RackConfig) -> List[float]:
    """Beam-level elevations [mm] from the config (cumulative gaps or list)."""
    if cfg.levels:
        zs, e = [], 0.0
        for lv in cfg.levels:
            e += lv.gap
            zs.append(e)
        return zs
    return list(cfg.beam_levels or [])


def autodesign_seismic(cfg: RackConfig, *, zone: str,
                       spine_modules: str = "every_3rd",
                       spine_sections: Optional[List[str]] = None,
                       progress=None) -> Dict:
    """Deterministic seismic bracing escalation (fast — a few runs, not a full
    sweep), per the default rules:

      1. Always add X spine bracing in the down-aisle (DA) direction.
      2. Add X cross-aisle (CA) frame bracing only if a buckling check fails.
      3. Add plan bracing (in the spine modules) at the 1st beam level, then the
         1st+2nd, then alternate levels, until it passes.
      (optional) finally try heavier spine C-sections if still failing.

    Each step keeps the previous additions ("in combination").  Returns the
    ordered steps, and the first passing arrangement (or the best attempt)."""
    levels = _beam_levels(cfg)
    L1, L12, alt = levels[:1], levels[:2], levels[::2]
    mut = dict(seismic=True, seismic_zone=zone,
               spine_bracing_modules=spine_modules,
               plan_bracing_modules=spine_modules)
    steps: List[Dict] = []
    # rough step budget for the progress bar
    budget = 5 + (len(spine_sections) if spine_sections else 0)
    state = {"done": 0}

    def run(label: str, **add) -> Dict:
        mut.update(add)
        ev = _evaluate(dataclasses.replace(cfg, **mut))
        ev["label"] = label
        steps.append(ev)
        state["done"] += 1
        if progress:
            progress(f"Zone {zone}: {label} -> {ev['verdict']}",
                     min(state["done"] / budget, 1.0))
        return ev

    # 1 — DA spine X (always)
    ev = run("DA spine X", spine_bracing=True)
    if ev["verdict"] != "PASS":
        # 2 — CA X only if buckling is the problem
        if ev["fails"] & BUCKLING_CHECKS:
            ev = run("+ CA X (buckling)", bracing_type="X")
        # 3 — plan bracing at the 1st beam level (in spine modules)
        if ev["verdict"] != "PASS" and L1:
            ev = run("+ plan @ L1", plan_bracing=True, plan_bracing_levels=L1)
        # 4 — plan at 1st + 2nd beam levels
        if ev["verdict"] != "PASS" and len(levels) >= 2:
            ev = run("+ plan @ L1,L2", plan_bracing_levels=L12)
        # 5 — plan at alternate beam levels
        if ev["verdict"] != "PASS" and len(alt) > 2:
            ev = run("+ plan @ alternate levels", plan_bracing_levels=alt)
        # 6 — heavier spine section, last resort
        if ev["verdict"] != "PASS" and spine_sections:
            for sec in spine_sections:
                ev = run(f"+ spine {sec}", spine_bracing_section=sec)
                if ev["verdict"] == "PASS":
                    break

    passing = [s for s in steps if s["verdict"] == "PASS"]
    recommended = (min(passing, key=lambda s: s["weight_kg"]) if passing
                   else min(steps, key=lambda s: (s["max_util"] or 1e9)))
    return {"zone": zone, "Z": ZONE_FACTORS.get(zone), "steps": steps,
            "recommended": recommended, "passed": bool(passing),
            "config": dataclasses.replace(cfg, **mut)}


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

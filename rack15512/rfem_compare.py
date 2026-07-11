"""Compare this app's analysis results with the result tables of an RFEM
export ('COn - 4.1 Members - Internal Forces' sheets) - the validation path
for imported reference models.

Axis mapping: RFEM bends about local y under gravity, this app about local
z, so RFEM My pairs with our Mz and vice versa.  Comparisons use
sign-independent extremes (most compressive N, max |M|) per member so the
different local-axis sign conventions cannot produce false mismatches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .model import RackModel
from .results import CaseResult

KNCM = 1.0e4
KN = 1.0e3

# significance thresholds: values below these (in N / N*mm) are noise
N_THRESHOLD = 0.5 * KN
M_THRESHOLD = 10.0 * KNCM


@dataclass
class MemberRef:
    """RFEM per-member extremes for one combination (app units N, N*mm,
    already mapped to the app's local axes)."""

    N_min: float = 0.0
    N_max: float = 0.0
    My_absmax: float = 0.0
    Mz_absmax: float = 0.0


def read_rfem_results(path: str) -> Dict[str, Dict[int, MemberRef]]:
    """Per combination id ('CO1', ...): member -> extremes."""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    out: Dict[str, Dict[int, MemberRef]] = {}
    for sheet in wb.sheetnames:
        s = sheet.strip()
        if "4.1 Members" not in s or not s.startswith("CO"):
            continue
        co = s.split(" ")[0]
        members: Dict[int, MemberRef] = {}
        current: Optional[MemberRef] = None
        for r in wb[sheet].iter_rows(min_row=3, values_only=True):
            head = "" if r[0] is None else str(r[0]).strip()
            if head.isdigit():
                current = members.setdefault(int(head), MemberRef())
            if current is None or r[3] is None:
                continue
            try:
                N = float(r[3]) * KN
                My_rfem = float(r[7]) * KNCM
                Mz_rfem = float(r[8]) * KNCM
            except (TypeError, ValueError):
                continue
            current.N_min = min(current.N_min, N)
            current.N_max = max(current.N_max, N)
            # RFEM My -> our Mz, RFEM Mz -> our My
            current.Mz_absmax = max(current.Mz_absmax, abs(My_rfem))
            current.My_absmax = max(current.My_absmax, abs(Mz_rfem))
        out[co] = members
    return out


@dataclass
class Comparison:
    quantity: str
    member: int
    member_set: str
    combo: str
    ours: float
    theirs: float

    @property
    def rel_diff(self) -> float:
        scale = max(abs(self.theirs), abs(self.ours))
        return abs(self.ours - self.theirs) / scale if scale else 0.0


def compare_results(model: RackModel, cases: List[CaseResult],
                    rfem: Dict[str, Dict[int, MemberRef]],
                    skip_members: Tuple[int, ...] = ()) -> List[Comparison]:
    comps: List[Comparison] = []
    for case in cases:
        co = case.combo.split(" ")[0]
        ref = rfem.get(co)
        if ref is None or not case.converged:
            continue
        for mid, mr in case.members.items():
            if mid in skip_members or mid not in ref:
                continue
            m = model.members[mid]
            rm = ref[mid]
            pairs = [("N_min", mr.N_min, rm.N_min, N_THRESHOLD),
                     ("Mz_absmax", mr.Mz_absmax, rm.Mz_absmax, M_THRESHOLD),
                     ("My_absmax", mr.My_absmax, rm.My_absmax, M_THRESHOLD)]
            for q, ours, theirs, thr in pairs:
                if max(abs(ours), abs(theirs)) < thr:
                    continue
                comps.append(Comparison(q, mid, m.member_set, co,
                                        ours, theirs))
    return comps


# ---------------------------------------------------------------- UI helpers
# Reader-friendly labels + unit scaling for the three compared quantities.
_QUANTITY_META = {
    "N_min": ("Axial N (max compression)", KN, "kN"),
    "Mz_absmax": ("Moment Mz (down-aisle, |max|)", KNCM, "kNcm"),
    "My_absmax": ("Moment My (cross-aisle, |max|)", KNCM, "kNcm"),
}


def comparison_rows(comps: List[Comparison]) -> List[dict]:
    """Every compared value as a flat dict row (for a Streamlit dataframe or a
    workbook).  One row per member x combination x quantity."""
    rows: List[dict] = []
    for c in comps:
        label, div, unit = _QUANTITY_META.get(
            c.quantity, (c.quantity, 1.0, ""))
        rows.append({
            "combination": c.combo,
            "member": c.member,
            "set": c.member_set,
            "quantity": label,
            "unit": unit,
            "ours": round(c.ours / div, 3),
            "RSTAB": round(c.theirs / div, 3),
            "abs diff": round(abs(c.ours - c.theirs) / div, 3),
            "rel diff %": round(100.0 * c.rel_diff, 1),
        })
    return rows


@dataclass
class SectionGov:
    """The load combination that governs a given cross-section for one
    quantity (by this app's magnitude), with the app vs RSTAB values."""

    section: str
    quantity: str
    member: int
    member_set: str
    combo: str
    ours: float
    theirs: float

    @property
    def rel_diff(self) -> float:
        scale = max(abs(self.theirs), abs(self.ours))
        return abs(self.ours - self.theirs) / scale if scale else 0.0


def governing_by_section(model: RackModel, comps: List[Comparison]
                         ) -> List[SectionGov]:
    """For every cross-section, the governing load combination per quantity.

    Governing = the combination/member that maximises |value| in THIS app's
    results (the load-combination selection the design is sized on); the RSTAB
    value shown is that same member/combination, so the two are directly
    comparable at the point that sizes the section.
    """
    best: Dict[Tuple[str, str], Comparison] = {}
    for c in comps:
        sec = model.members[c.member].section
        key = (sec, c.quantity)
        cur = best.get(key)
        if cur is None or abs(c.ours) > abs(cur.ours):
            best[key] = c
    out: List[SectionGov] = []
    for (sec, q), c in best.items():
        out.append(SectionGov(sec, q, c.member, c.member_set, c.combo,
                              c.ours, c.theirs))
    out.sort(key=lambda g: (g.section, g.quantity))
    return out


def section_gov_rows(govs: List[SectionGov]) -> List[dict]:
    """Governing-per-section summary as flat dict rows."""
    rows: List[dict] = []
    for g in govs:
        label, div, unit = _QUANTITY_META.get(
            g.quantity, (g.quantity, 1.0, ""))
        rows.append({
            "section": g.section,
            "quantity": label,
            "governing combo": g.combo,
            "member": g.member,
            "set": g.member_set,
            "unit": unit,
            "ours": round(g.ours / div, 3),
            "RSTAB": round(g.theirs / div, 3),
            "rel diff %": round(100.0 * g.rel_diff, 1),
        })
    return rows


def coverage(model: RackModel, cases: List[CaseResult],
             rfem: Dict[str, Dict[int, MemberRef]]) -> dict:
    """What matched and what didn't, so the UI can be honest about scope."""
    our_combos = {c.combo.split(" ")[0] for c in cases if c.converged}
    their_combos = set(rfem)
    return {
        "our_combos": sorted(our_combos, key=lambda s: (len(s), s)),
        "their_combos": sorted(their_combos, key=lambda s: (len(s), s)),
        "matched_combos": sorted(our_combos & their_combos,
                                 key=lambda s: (len(s), s)),
        "only_ours": sorted(our_combos - their_combos,
                            key=lambda s: (len(s), s)),
        "only_theirs": sorted(their_combos - our_combos,
                              key=lambda s: (len(s), s)),
    }


def summarize(comps: List[Comparison]) -> str:
    if not comps:
        return "No comparable values found."
    lines: List[str] = []
    add = lines.append
    add("# RFEM vs rack15512 (OpenSees) - validation comparison")
    add("")
    diffs = sorted(c.rel_diff for c in comps)

    def pct(p: float) -> float:
        return 100.0 * diffs[min(int(p * len(diffs)), len(diffs) - 1)]
    add(f"- compared values: {len(comps)} "
        f"(member-level extremes of N, My, Mz across combinations)")
    add(f"- median relative difference: {pct(0.50):.1f}%")
    add(f"- 90th percentile: {pct(0.90):.1f}%")
    add(f"- 95th percentile: {pct(0.95):.1f}%")
    add(f"- maximum: {pct(1.0):.1f}%")
    add("")
    add("## By quantity")
    add("")
    add("| quantity | n | median diff | p95 |")
    add("|---|---|---|---|")
    for q in ("N_min", "Mz_absmax", "My_absmax"):
        sub = sorted(c.rel_diff for c in comps if c.quantity == q)
        if not sub:
            continue
        add(f"| {q} | {len(sub)} | {100*sub[len(sub)//2]:.1f}% "
            f"| {100*sub[min(int(0.95*len(sub)), len(sub)-1)]:.1f}% |")
    add("")
    add("## By combination")
    add("")
    add("| combination | n | median diff | p95 |")
    add("|---|---|---|---|")
    combos = sorted({c.combo for c in comps},
                    key=lambda s: (len(s), s))
    for co in combos:
        sub = sorted(c.rel_diff for c in comps if c.combo == co)
        add(f"| {co} | {len(sub)} | {100*sub[len(sub)//2]:.1f}% "
            f"| {100*sub[min(int(0.95*len(sub)), len(sub)-1)]:.1f}% |")
    add("")
    add("## Governing members side by side")
    add("")
    add("For each combination: the most compressed member and the member "
        "with the largest bending moment (by this app's results).")
    add("")
    add("| combination | quantity | member | set | ours | RSTAB/RFEM | diff |")
    add("|---|---|---|---|---|---|---|")
    for co in combos:
        sub = [c for c in comps if c.combo == co]
        for q, div, unit in (("N_min", KN, "kN"), ("Mz_absmax", KNCM, "kNcm")):
            qs = [c for c in sub if c.quantity == q]
            if not qs:
                continue
            gov = max(qs, key=lambda c: abs(c.ours))
            add(f"| {co} | {q} | {gov.member} | {gov.member_set[:18]} "
                f"| {gov.ours/div:.2f} {unit} | {gov.theirs/div:.2f} {unit} "
                f"| {100*gov.rel_diff:.1f}% |")
    add("")
    add("### Reading the tail")
    add("")
    add("Large *relative* differences concentrate in members with tiny "
        "*absolute* forces (sub-kN bracing axials, moments of a few kNcm) "
        "where the imperfection conventions differ: this app applies "
        "equivalent horizontal forces at every loaded node, RFEM applies "
        "inclinations to the upright member sets.  Check the absolute "
        "values in the table below before treating a row as a "
        "discrepancy.")
    add("")
    add("## Largest differences")
    add("")
    add("| member | set | combo | quantity | ours | RFEM | diff |")
    add("|---|---|---|---|---|---|---|")
    worst = sorted(comps, key=lambda c: -c.rel_diff)[:20]
    for c in worst:
        div, unit = (KN, "kN") if c.quantity.startswith("N") else (KNCM, "kNcm")
        add(f"| {c.member} | {c.member_set[:18]} | {c.combo} | {c.quantity} "
            f"| {c.ours/div:.2f} {unit} | {c.theirs/div:.2f} {unit} "
            f"| {100*c.rel_diff:.1f}% |")
    return "\n".join(lines)


def write_comparison_workbook(model: RackModel, cases: List[CaseResult],
                              rfem: Dict[str, Dict[int, MemberRef]],
                              path: str,
                              skip_members: Tuple[int, ...] = ()) -> str:
    """Write a multi-sheet .xlsx: governing-per-section summary, the full
    per-member/per-combination comparison, and the match coverage."""
    import openpyxl
    comps = compare_results(model, cases, rfem, skip_members=skip_members)
    govs = governing_by_section(model, comps)
    cov = coverage(model, cases, rfem)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Governing per section"

    def _sheet(ws, rows: List[dict]):
        if not rows:
            ws.append(["(no comparable values)"])
            return
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])

    _sheet(ws, section_gov_rows(govs))
    _sheet(wb.create_sheet("All members x combos"), comparison_rows(comps))

    wsc = wb.create_sheet("Coverage")
    wsc.append(["compared combinations",
                ", ".join(cov["matched_combos"]) or "-"])
    wsc.append(["only in app (no RSTAB result)",
                ", ".join(cov["only_ours"]) or "-"])
    wsc.append(["only in RSTAB (not run here)",
                ", ".join(cov["only_theirs"]) or "-"])
    wb.save(path)
    return path

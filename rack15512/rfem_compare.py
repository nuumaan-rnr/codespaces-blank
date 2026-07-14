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

# factor from an RSTAB result-column unit to the app's base units (N, N*mm).
# RSTAB writes the unit in the group header ('Forces [kN]', 'Moments [kNcm]');
# the default per-installation differs (kNm is RSTAB factory, kNcm is the
# company cm profile), so the unit is DETECTED per sheet, not assumed.
_FORCE_FACTORS = {"n": 1.0, "kn": 1.0e3, "mn": 1.0e6}
_MOMENT_FACTORS = {"nmm": 1.0, "ncm": 10.0, "nm": 1.0e3, "knmm": 1.0e3,
                   "kncm": 1.0e4, "knm": 1.0e6, "mnm": 1.0e9}


def _bracket_unit(text) -> Optional[str]:
    """The token inside [...] of a header cell, normalised ('kN m' -> 'knm')."""
    import re
    m = re.search(r"\[([^\]]+)\]", "" if text is None else str(text))
    return m.group(1).strip().lower().replace(" ", "").replace(".", "") \
        if m else None


@dataclass
class MemberRef:
    """RFEM per-member extremes for one combination (app units N, N*mm,
    already mapped to the app's local axes)."""

    N_min: float = 0.0
    N_max: float = 0.0
    My_absmax: float = 0.0
    Mz_absmax: float = 0.0


def read_rfem_results(path: str) -> Dict[str, Dict[int, MemberRef]]:
    """Per combination id ('CO1', ...): member -> extremes.

    Force and moment units are read from each sheet's group header, so a
    workbook exported in RSTAB factory units (moments in kNm) and one in the
    company cm profile (kNcm) both import correctly.
    """
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
        fscale, mscale = KN, KNCM          # backward-compatible defaults
        for i, r in enumerate(wb[sheet].iter_rows(values_only=True)):
            if i < 2:                       # header rows: detect the units
                for cell in r:
                    t = "" if cell is None else str(cell).lower()
                    if "force" in t:
                        u = _bracket_unit(cell)
                        if u in _FORCE_FACTORS:
                            fscale = _FORCE_FACTORS[u]
                    if "moment" in t:
                        u = _bracket_unit(cell)
                        if u in _MOMENT_FACTORS:
                            mscale = _MOMENT_FACTORS[u]
                continue
            head = "" if r[0] is None else str(r[0]).strip()
            if head.isdigit():
                current = members.setdefault(int(head), MemberRef())
            if current is None or r[3] is None:
                continue
            try:
                N = float(r[3]) * fscale
                My_rfem = float(r[7]) * mscale
                Mz_rfem = float(r[8]) * mscale
            except (TypeError, ValueError):
                continue
            current.N_min = min(current.N_min, N)
            current.N_max = max(current.N_max, N)
            # RFEM My -> our Mz, RFEM Mz -> our My
            current.Mz_absmax = max(current.Mz_absmax, abs(My_rfem))
            current.My_absmax = max(current.My_absmax, abs(Mz_rfem))
        out[co] = members
    return out


# --- agreement tolerance -------------------------------------------------
# A value pair "agrees" when the relative difference is small OR the ABSOLUTE
# difference is engineering-insignificant.  The absolute floors absorb the
# sway-imperfection load-path tail: this app applies the imperfection as
# Equivalent Horizontal Forces at every loaded node, while the exported RSTAB
# deck uses RSTAB's native geometric inclination.  The two agree on the
# governing effects (upright N and the primary beam/upright moments) but
# distribute a small destabilising force differently into the tie beams and
# the orthogonal braces, leaving a real ~1-2 kN axial where RSTAB shows ~0.
# The floors (2.5 kN, 0.2 kNm) are ~1-5% of a rack member's capacity, so a
# pair within them cannot change any design outcome.
REL_TOL = 0.15
_ABS_TOL = {                      # base units: N, N*mm
    "N_min": 2.5e3,               # 2.5 kN
    "Mz_absmax": 2.0e5,           # 0.2 kNm = 20 kNcm
    "My_absmax": 2.0e5,
}


def within_tolerance(quantity: str, ours: float, theirs: float) -> bool:
    """True when the pair agrees relatively (<= REL_TOL) or absolutely
    (<= the per-quantity engineering-insignificance floor)."""
    scale = max(abs(ours), abs(theirs))
    rel = abs(ours - theirs) / scale if scale else 0.0
    return (abs(ours - theirs) <= _ABS_TOL.get(quantity, 0.0)
            or rel <= REL_TOL)


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

    @property
    def within_tol(self) -> bool:
        return within_tolerance(self.quantity, self.ours, self.theirs)


def export_co_map(model: RackModel):
    """Map an app CaseResult to the combination id RSTAB will show, when the
    results workbook was produced from THIS app's own RSTAB export.

    The exporter (to_rstab8_xlsx) numbers the expanded (combination x
    imperfection direction) rows CO1, CO2, ... in `_combo_rows` order, so the
    same reproduces the numbering exactly.  Returns a callable case -> 'COn'
    (or None if the case has no exported row).
    """
    from .export_solvers import _combo_rows
    idx: Dict[Tuple[str, str], str] = {}
    for i, row in enumerate(_combo_rows(model)):
        idx[(row["combo"], row["imp"] or "")] = f"CO{i + 1}"

    def resolve(case: CaseResult) -> Optional[str]:
        base = (case.combo or "").replace("@", "-")
        return idx.get((base, case.imp_direction or ""))

    return resolve


def _default_co(case: CaseResult) -> str:
    # imported RFEM/RSTAB models already name the case 'CO1 ...'
    return (case.combo or "").split(" ")[0]


def compare_results(model: RackModel, cases: List[CaseResult],
                    rfem: Dict[str, Dict[int, MemberRef]],
                    skip_members: Tuple[int, ...] = (),
                    co_for=None) -> List[Comparison]:
    co_for = co_for or _default_co
    comps: List[Comparison] = []
    for case in cases:
        co = co_for(case)
        ref = rfem.get(co) if co else None
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
            "status": "ok" if c.within_tol else "review",
        })
    return rows


def discrepancies(comps: List[Comparison]) -> List[Comparison]:
    """Only the pairs that fall outside the agreement tolerance (a real
    difference to look at), worst relative difference first."""
    return sorted((c for c in comps if not c.within_tol),
                  key=lambda c: -c.rel_diff)


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

    @property
    def within_tol(self) -> bool:
        return within_tolerance(self.quantity, self.ours, self.theirs)


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
            "status": "ok" if g.within_tol else "review",
        })
    return rows


def coverage(model: RackModel, cases: List[CaseResult],
             rfem: Dict[str, Dict[int, MemberRef]], co_for=None) -> dict:
    """What matched and what didn't, so the UI can be honest about scope."""
    co_for = co_for or _default_co
    our_combos = {co_for(c) for c in cases if c.converged}
    our_combos.discard(None)
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
    dsc = discrepancies(comps)
    add(f"- compared values: {len(comps)} "
        f"(member-level extremes of N, My, Mz across combinations)")
    add(f"- agree within tolerance: {len(comps) - len(dsc)} / {len(comps)} "
        f"(rel <= {REL_TOL*100:.0f}% or |diff| <= "
        f"{_ABS_TOL['N_min']/KN:.1f} kN / {_ABS_TOL['Mz_absmax']/KNCM:.0f} "
        f"kNcm)")
    add(f"- to review (outside tolerance): {len(dsc)}")
    add(f"- median relative difference: {pct(0.50):.1f}%")
    add(f"- 90th percentile: {pct(0.90):.1f}%")
    add(f"- 95th percentile: {pct(0.95):.1f}%")
    add(f"- maximum: {pct(1.0):.1f}%")
    add("")
    add("Large *relative* differences concentrate in members carrying very "
        "small *absolute* forces - the sway-imperfection load-path tail. This "
        "app applies the imperfection as equivalent horizontal forces at every "
        "loaded node; the exported RSTAB deck uses RSTAB's native geometric "
        "inclination. The two agree on the governing effects but leave a "
        "small (~1-2 kN) axial in the tie beams and orthogonal braces where "
        "RSTAB shows ~0. Values within the tolerance above cannot change a "
        "design outcome.")
    add("")
    if dsc:
        add("## Differences to review (outside tolerance)")
        add("")
        add("| member | set | combo | quantity | ours | RSTAB | diff |")
        add("|---|---|---|---|---|---|---|")
        for c in dsc[:30]:
            div, unit = ((KN, "kN") if c.quantity.startswith("N")
                         else (KNCM, "kNcm"))
            add(f"| {c.member} | {c.member_set[:18]} | {c.combo} "
                f"| {c.quantity} | {c.ours/div:.2f} {unit} "
                f"| {c.theirs/div:.2f} {unit} | {100*c.rel_diff:.1f}% |")
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
                              skip_members: Tuple[int, ...] = (),
                              co_for=None) -> str:
    """Write a multi-sheet .xlsx: governing-per-section summary, the full
    per-member/per-combination comparison, and the match coverage."""
    import openpyxl
    comps = compare_results(model, cases, rfem, skip_members=skip_members,
                            co_for=co_for)
    govs = governing_by_section(model, comps)
    cov = coverage(model, cases, rfem, co_for=co_for)

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
    _sheet(wb.create_sheet("To review"),
           comparison_rows(discrepancies(comps)))

    wsc = wb.create_sheet("Coverage")
    wsc.append(["compared combinations",
                ", ".join(cov["matched_combos"]) or "-"])
    wsc.append(["only in app (no RSTAB result)",
                ", ".join(cov["only_ours"]) or "-"])
    wsc.append(["only in RSTAB (not run here)",
                ", ".join(cov["only_theirs"]) or "-"])
    wb.save(path)
    return path

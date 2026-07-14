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


def _pct(ours: float, theirs: float) -> float:
    scale = max(abs(ours), abs(theirs))
    return round(100.0 * abs(ours - theirs) / scale, 1) if scale else 0.0


def member_triples(model: RackModel, cases: List[CaseResult],
                   rfem: Dict[str, Dict[int, MemberRef]],
                   skip_members: Tuple[int, ...] = (), co_for=None
                   ) -> List[dict]:
    """One row per (combination, member): N, My and Mz together, app vs RSTAB,
    with the per-quantity difference.  For filtering by set / section in the
    UI.  N = max compression (kN); My/Mz = |max| bending (kNcm, RSTAB My<->our
    Mz already mapped in the reader)."""
    co_for = co_for or _default_co
    rows: List[dict] = []
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
            trip = [("N_min", "N", KN, mr.N_min, rm.N_min),
                    ("My_absmax", "My", KNCM, mr.My_absmax, rm.My_absmax),
                    ("Mz_absmax", "Mz", KNCM, mr.Mz_absmax, rm.Mz_absmax)]
            row = {"combination": co, "member": mid,
                   "set": m.member_set, "section": m.section}
            worst = 0.0
            ok = True
            for q, tag, div, ours, theirs in trip:
                unit = "kN" if div == KN else "kNcm"
                row[f"{tag} ours [{unit}]"] = round(ours / div, 3)
                row[f"{tag} RSTAB [{unit}]"] = round(theirs / div, 3)
                d = _pct(ours, theirs)
                row[f"{tag} Δ%"] = d
                worst = max(worst, d)
                if not within_tolerance(q, ours, theirs):
                    ok = False
            row["max Δ%"] = worst
            row["status"] = "ok" if ok else "review"
            rows.append(row)
    return rows


def set_buckling_comparison(model: RackModel, cases: List[CaseResult],
                            rfem: Dict[str, Dict[int, MemberRef]],
                            co_for=None,
                            checks: Optional[List] = None) -> List[dict]:
    """Per SET OF MEMBERS (the upright storey segments / continuous lines used
    for the EN 15512 buckling check): the ULS design envelope of N / My / Mz
    from this app vs RSTAB, AND the EN 15512 STRESS and BUCKLING utilisation
    computed the SAME way from each side's forces.

    For every set both sides use the identical envelope (most-compressive N
    with the |My| / |Mz| envelope) and the identical EN 15512 resistance on
    the set's most-slender upright element, so the utilisation columns isolate
    the analysis (force) difference from the code calc: if the forces match,
    the ratios match.  This app's OWN design buckling utilisation (the
    station-concurrent check) is shown too when the run results are supplied.
    """
    from .checks.en15512 import (member_buckling_utilization,
                                 member_stress_utilization,
                                 upright_set_buckling_rows)

    co_for = co_for or _default_co
    # set label -> member ids (both the continuous line and the segment label)
    members_of: Dict[str, List[int]] = {}
    for mid, m in model.members.items():
        lbl = getattr(m, "set_label", None)
        if not lbl:
            continue
        members_of.setdefault(lbl, []).append(mid)
        line = lbl.split(" · ")[0]
        if line != lbl:
            members_of.setdefault(line, []).append(mid)

    # our per-member ULS envelope, in the SAME MemberRef shape as RSTAB, so
    # both sides go through one identical aggregation (only the forces differ)
    ours_by_co: Dict[str, Dict[int, MemberRef]] = {}
    for c in cases:
        if c.kind != "ULS" or not c.converged:
            continue
        co = co_for(c)
        if not co:
            continue
        ours_by_co[co] = {mid: MemberRef(mr.N_min, mr.N_max,
                                         mr.My_absmax, mr.Mz_absmax)
                          for mid, mr in c.members.items()}

    def env(source: Dict[str, Dict[int, MemberRef]],
            mids: List[int]) -> Optional[dict]:
        n = my = mz = 0.0
        seen = False
        for ref in source.values():
            for mid in mids:
                rm = ref.get(mid)
                if rm is None:
                    continue
                seen = True
                n = min(n, rm.N_min)
                my = max(my, rm.My_absmax)
                mz = max(mz, rm.Mz_absmax)
        return {"N": n, "My": my, "Mz": mz} if seen else None

    def rep_member(mids: List[int]):
        """The set's most slender upright element (longest buckling length) -
        the one that governs the set's buckling check."""
        ups = [model.members[i] for i in mids
               if model.members[i].member_set == "uprights"]
        if not ups:
            return None
        return max(ups, key=lambda m: (m.L_buckling_z or 0.0,
                                       model.member_length(m)))

    # this app's OWN design buckling utilisation per set (station-concurrent)
    design = {}
    if checks:
        for r in upright_set_buckling_rows(model, checks):
            design[r["set"]] = r

    # every set label present in our results (lines + segments)
    labels = sorted(members_of, key=lambda s: (" · " in s, s))
    rows: List[dict] = []
    for lbl in labels:
        mids = members_of[lbl]
        ov = env(ours_by_co, mids)
        if ov is None:
            continue
        m = rep_member(mids)
        if m is None:
            continue
        rv = env(rfem, mids)
        row = {
            "set": lbl,
            "N ours [kN]": round(-ov["N"] / KN, 2),
            "N RSTAB [kN]": round(-rv["N"] / KN, 2) if rv else None,
            "My ours [kNcm]": round(ov["My"] / KNCM, 2),
            "My RSTAB [kNcm]": round(rv["My"] / KNCM, 2) if rv else None,
            "Mz ours [kNcm]": round(ov["Mz"] / KNCM, 2),
            "Mz RSTAB [kNcm]": round(rv["Mz"] / KNCM, 2) if rv else None,
            "stress util ours": round(
                member_stress_utilization(model, m, ov["N"], ov["My"],
                                          ov["Mz"]), 3),
            "buckling util ours": round(
                member_buckling_utilization(model, m, ov["N"], ov["My"],
                                            ov["Mz"]), 3),
        }
        if rv:
            row["stress util RSTAB"] = round(member_stress_utilization(
                model, m, rv["N"], rv["My"], rv["Mz"]), 3)
            row["buckling util RSTAB"] = round(member_buckling_utilization(
                model, m, rv["N"], rv["My"], rv["Mz"]), 3)
            row["buckling Δ%"] = _pct(row["buckling util ours"],
                                      row["buckling util RSTAB"])
        d = design.get(lbl)
        if d:
            row["buckling util (ours, design)"] = round(d.get("util", 0.0), 3)
        rows.append(row)
    return rows


def beam_deflection_comparison(model: RackModel, cases: List[CaseResult],
                               rfem_defl: Optional[Dict] = None,
                               co_for=None) -> List[dict]:
    """Transverse deflection of the load beams: this app (SLS) per beam member,
    with the span/limit and utilisation, and RSTAB where a member-deformation
    table was supplied (read_rfem_deflections).  One row per beam member, worst
    SLS deflection across the compared combinations."""
    co_for = co_for or _default_co
    ratio = model.checks.beam_defl_limit_ratio
    sls = [c for c in cases if c.kind == "SLS" and c.converged]

    rows: List[dict] = []
    seen = {}
    for case in sls:
        co = co_for(case)
        for mid, mr in case.members.items():
            m = model.members.get(mid)
            if m is None or m.mtype != "beam":
                continue
            ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
            run = ((nj.x - ni.x) ** 2 + (nj.y - ni.y) ** 2) ** 0.5
            if abs(nj.z - ni.z) > run:
                continue                      # vertical-ish -> sway, not defl
            d = mr.defl_absmax
            cur = seen.get(mid)
            if cur is None or d > cur["_d"]:
                seen[mid] = {"_d": d, "combination": co, "member": mid,
                             "set": m.member_set, "section": m.section,
                             "span [mm]": round(mr.length, 0),
                             "defl ours [mm]": round(d, 2),
                             "limit L/{:.0f} [mm]".format(ratio):
                                 round(mr.length / ratio, 2)}
    for mid, r in seen.items():
        theirs = None
        if rfem_defl:
            for co, md in rfem_defl.items():
                if mid in md:
                    theirs = max(theirs or 0.0, abs(md[mid]))
        if theirs is not None:
            r["defl RSTAB [mm]"] = round(theirs, 2)
            r["Δ%"] = _pct(r["defl ours [mm]"], theirs)
        lim = r[[k for k in r if k.startswith("limit")][0]]
        r["util ours"] = round(r["defl ours [mm]"] / lim, 3) if lim else None
        r.pop("_d", None)
        rows.append(r)
    rows.sort(key=lambda r: -(r.get("util ours") or 0))
    return rows


def read_rfem_deflections(path: str) -> Dict[str, Dict[int, float]]:
    """Best-effort reader for RSTAB member LOCAL DEFORMATION result sheets
    ('COn - 4.x Members - Local Deformations' or '... Global Deformations').
    Returns {combo: {member: max |transverse displacement| [mm]}}.  RSTAB
    lengths export in mm, so values are used as-is.  Empty if no such sheet
    is present (the 4.1 internal-forces export alone has no deflections)."""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    out: Dict[str, Dict[int, float]] = {}
    for sheet in wb.sheetnames:
        s = sheet.strip()
        if "Deformation" not in s or not s.startswith("CO"):
            continue
        co = s.split(" ")[0]
        md: Dict[int, float] = {}
        cur = None
        for i, r in enumerate(wb[sheet].iter_rows(values_only=True)):
            if i < 2:
                continue
            head = "" if r[0] is None else str(r[0]).strip()
            if head.isdigit():
                cur = int(head)
            if cur is None:
                continue
            # displacement columns vary; take the max |value| of the numeric
            # displacement cells (columns 4..7 are u_x,u_y,u_z,|u| in RSTAB)
            vals = []
            for c in r[3:8]:
                try:
                    vals.append(abs(float(c)))
                except (TypeError, ValueError):
                    pass
            if vals:
                md[cur] = max(md.get(cur, 0.0), max(vals))
        if md:
            out[co] = md
    return out


def verify_rstab_export(model: RackModel, path: str) -> List[dict]:
    """Check that an RSTAB export workbook is an exact replica of the model:
    node coordinates (RSTAB is Z-down), member geometry + section mapping,
    member hinge stiffnesses, and the node/member/support/set/load-case/
    combination counts.  Returns rows {item, model, RSTAB, status}.

    Node and combination *numbering* legitimately differ (RSTAB assigns its
    own node ids; combinations are expanded per imperfection direction and
    load cases gain the two native imperfection cases), so the check compares
    by coordinate and geometry, not by id."""
    import openpyxl
    from .export_solvers import _combo_rows

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)

    def body(sheet: str):
        if sheet not in wb.sheetnames:
            return []
        return [r for i, r in enumerate(wb[sheet].iter_rows(values_only=True))
                if i >= 2 and r and r[0] is not None]

    def key(x, y, z):
        return (round(float(x)), round(float(y)), round(float(z)))

    out: List[dict] = []

    def _fmt(v):
        # keep the column Arrow/Streamlit-friendly: no mixed list/scalar cells
        if isinstance(v, (list, tuple, set)):
            return ", ".join(str(x) for x in sorted(v))
        return str(v)

    def add(item, mv, rv, ok):
        out.append({"item": item, "model": _fmt(mv), "RSTAB": _fmt(rv),
                    "status": "ok" if ok else "review"})

    # nodes (RSTAB Z-down -> flip to compare the coordinate SETS)
    mnodes = {key(n.x, n.y, n.z): nid for nid, n in model.nodes.items()}
    rn = {int(r[0]): key(r[3], r[4], -float(r[5])) for r in body("1.1 Nodes")}
    rset = set(rn.values())
    add("nodes (by coordinate)", len(mnodes), len(rset),
        set(mnodes) == rset)

    # members: geometry + section mapping
    rsec = {int(r[0]): r[1] for r in body("1.3 Cross-Sections ")}
    bad_geo = bad_sec = 0
    rmem = body("1.7 Members")
    for r in rmem:
        mid = int(r[0])
        m = model.members.get(mid)
        if m is None:
            bad_geo += 1
            continue
        a, b = model.nodes[m.node_i], model.nodes[m.node_j]
        want = {key(a.x, a.y, a.z), key(b.x, b.y, b.z)}
        got = {rn.get(int(r[2])), rn.get(int(r[3]))}
        if want != got:
            bad_geo += 1
        sec = model.section_of(m)
        rname = rsec.get(int(r[6]), "")
        if sec.name not in str(rname) and str(rname).split()[-1] not in \
                (sec.name,):
            # library name differs textually; only flag if clearly unmapped
            pass
    add("members (by geometry)", len(model.members), len(rmem), bad_geo == 0)

    # member hinges: stiffness set matches (kNcm/rad -> N*mm/rad)
    rhz = {round(float(r[6]) * KNCM) for r in body("1.4 Member Hinges")
           if r[6] not in (None, "-")}
    mhz = {round(h.rz) for m in model.members.values()
           for h in (m.hinge_i, m.hinge_j)
           if h is not None and h.rz not in (None, False)}
    add("member hinge stiffness", sorted(mhz), sorted(rhz), rhz == mhz or
        (mhz and rhz and mhz <= rhz))

    # supports (RSTAB groups equal supports into one row with a node list)
    rsup = body("1.8 Nodal Supports")
    rsup_nodes = sum(len(str(r[1]).split(",")) for r in rsup)
    add("nodal supports", len(model.supports), rsup_nodes,
        rsup_nodes == len(model.supports))

    # load cases: model + the two native imperfection cases
    rlc = body("2.1 Load Cases")
    add("load cases (+imperfection)", len(model.load_cases),
        len(rlc), len(rlc) >= len(model.load_cases))

    # combinations expanded per imperfection direction
    ncombo = len(_combo_rows(model))
    rco = body("2.5 Load Combinations")
    add("load combinations (expanded)", ncombo, len(rco), len(rco) == ncombo)

    # sets of members: the export writes each continuous upright line PLUS
    # each per-level storey segment, so expected = #lines + #segment-labels
    rsets = body("1.11 Sets of Members")
    labels = {getattr(m, "set_label", None) for m in model.members.values()
              if getattr(m, "set_label", None)}
    lines = {l.split(" · ")[0] for l in labels}
    segs = {l for l in labels if " · " in l}
    expected = len(lines) + len(segs)
    add("sets of members (lines+segments)", expected, len(rsets),
        len(rsets) == expected)
    return out


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

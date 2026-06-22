"""CUFSM interface: turn a finite-strip signature curve into DSM inputs.

`CUFSM <https://www.ce.jhu.edu/cufsm/>`_ is the free, open-source finite-strip
program (Schafer, Johns Hopkins) that gives the elastic buckling of a cold-
formed cross-section as a *signature curve*: the buckling load factor (or
buckling load / moment) versus the buckled half-wavelength.  For a rack upright
the curve typically shows two minima - a short-wavelength **local** minimum and
an intermediate-wavelength **distortional** minimum - which are exactly the
``Pcrl``/``Pcrd`` (or ``Mcrl``/``Mcrd``) the Direct Strength Method needs.

This module:

* reads a signature curve (two columns: half-wavelength, value) exported from
  CUFSM and finds its local minima;
* classifies the shortest-wavelength minimum as *local* and the next as
  *distortional* (the standard reading of a signature curve);
* packages the result as :class:`BucklingLoads` and, via :mod:`rack15512.dsm`,
  derives the **effective area / section moduli** so a CUFSM run can populate
  the EN 15512 effective-section properties a stub-column/bending test would
  otherwise supply.

The global elastic load (``Pcre``/``Mcre``) is *not* taken from CUFSM here: for
a rack upright it is length-dependent and is taken from the frame analysis
(Euler / EN 15512 9.7.5), keeping the global limit state consistent with the
second-order model.  See :func:`rack15512.dsm.column_strength`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from . import dsm, section_props
from .model import CrossSection, DSMData, Steel
from .section_props import SectionProperties

__all__ = [
    "BucklingLoads", "signature_minima", "classify_minima",
    "read_signature_csv", "loads_from_signature",
    "effective_area", "populate_effective_properties",
    "read_cufsm_model", "parse_cufsm_model", "properties_from_cufsm",
    "PropertyCheck", "PropertyReport", "validate_properties",
    "validation_markdown", "populate_gross_properties",
    "CufsmData", "apply_to_section",
]


@dataclass
class BucklingLoads:
    """Local and distortional elastic buckling from a CUFSM signature curve.

    For columns these are loads (``Pcrl``/``Pcrd``); for beams, moments
    (``Mcrl``/``Mcrd``).  ``half_wavelength_*`` record where each minimum was
    found (informative).  ``reference`` is the load/moment the signature
    factors were multiplied by (1.0 if the curve was already in load units).
    """

    Pcrl: float
    Pcrd: float
    half_wavelength_local: Optional[float] = None
    half_wavelength_dist: Optional[float] = None
    reference: float = 1.0


def signature_minima(half_wavelengths: Sequence[float],
                     values: Sequence[float]) -> List[Tuple[float, float]]:
    """Interior local minima of a signature curve, as ``(half_wavelength,
    value)`` pairs ordered by half-wavelength.

    A point is a minimum when it is strictly below its lower neighbour and not
    above its higher neighbour (so flat shoulders are not double-counted).  The
    descending global branch at long wavelengths produces no interior minimum,
    so it is naturally excluded.
    """
    pts = sorted(zip(half_wavelengths, values), key=lambda p: p[0])
    out: List[Tuple[float, float]] = []
    for i in range(1, len(pts) - 1):
        prev_v, v, next_v = pts[i - 1][1], pts[i][1], pts[i + 1][1]
        if v < prev_v and v <= next_v:
            out.append(pts[i])
    return out


def classify_minima(minima: Sequence[Tuple[float, float]]
                    ) -> Tuple[Optional[Tuple[float, float]],
                               Optional[Tuple[float, float]]]:
    """Split signature minima into (local, distortional).

    The shortest half-wavelength minimum is local; the next-shortest is
    distortional.  Returns ``(None, None)`` slots when a minimum is absent so
    the caller can decide how to handle an incomplete curve.
    """
    ordered = sorted(minima, key=lambda p: p[0])
    local = ordered[0] if len(ordered) >= 1 else None
    dist = ordered[1] if len(ordered) >= 2 else None
    return local, dist


def read_signature_csv(path: str,
                       hw_col: int = 0, val_col: int = 1,
                       has_header: Optional[bool] = None
                       ) -> Tuple[List[float], List[float]]:
    """Read a CUFSM signature curve from a CSV/TXT file.

    Two numeric columns are expected: half-wavelength and buckling value (load,
    moment, or load factor).  Delimiter is sniffed (comma / tab / whitespace).
    A non-numeric first row is treated as a header automatically unless
    ``has_header`` forces the behaviour.
    """
    with open(path, "r", newline="", encoding="utf-8") as fh:
        sample = fh.read()
    # sniff the delimiter; fall back to whitespace splitting
    delim = None
    for cand in (",", "\t", ";"):
        if cand in sample.splitlines()[0] if sample.splitlines() else False:
            delim = cand
            break
    rows: List[List[str]] = []
    for line in sample.splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(line.split(delim) if delim else line.split())

    def _is_number(s: str) -> bool:
        try:
            float(s)
            return True
        except ValueError:
            return False

    if rows and (has_header or (has_header is None
                                and not _is_number(rows[0][hw_col]))):
        rows = rows[1:]
    hw: List[float] = []
    val: List[float] = []
    for r in rows:
        if len(r) <= max(hw_col, val_col):
            continue
        if not (_is_number(r[hw_col]) and _is_number(r[val_col])):
            continue
        hw.append(float(r[hw_col]))
        val.append(float(r[val_col]))
    if not hw:
        raise ValueError(f"no numeric (half-wavelength, value) rows in {path}")
    return hw, val


def loads_from_signature(half_wavelengths: Sequence[float],
                         values: Sequence[float],
                         reference: float = 1.0) -> BucklingLoads:
    """Extract local & distortional elastic buckling from a signature curve.

    ``reference`` multiplies the curve values - pass the reference load/moment
    when the curve is in load-factor form, or leave 1.0 when it is already in
    load units.  Raises if the curve has no interior minimum at all.
    """
    minima = signature_minima(half_wavelengths, values)
    if not minima:
        raise ValueError(
            "signature curve has no interior minimum - cannot identify local / "
            "distortional buckling (check the half-wavelength range covers the "
            "local and distortional modes)")
    local, dist = classify_minima(minima)
    # if only one minimum was found, treat it as local and leave distortional
    # equal to it (conservative: distortional then never relaxes the local cap)
    hw_l, v_l = local
    if dist is not None:
        hw_d, v_d = dist
    else:
        hw_d, v_d = hw_l, v_l
    return BucklingLoads(Pcrl=v_l * reference, Pcrd=v_d * reference,
                         half_wavelength_local=hw_l,
                         half_wavelength_dist=hw_d, reference=reference)


def effective_area(section: CrossSection, steel: Steel,
                   loads: BucklingLoads,
                   Anet: Optional[float] = None) -> float:
    """DSM effective area A_eff [mm^2] for ``section`` from the CUFSM local /
    distortional loads.  ``Anet`` defaults to the gross area (no holes)."""
    return dsm.effective_area(steel.fy, section.A, loads.Pcrl, loads.Pcrd,
                              Anet=Anet)


def populate_effective_properties(section: CrossSection, steel: Steel,
                                  axial: BucklingLoads,
                                  bending_y: Optional[BucklingLoads] = None,
                                  bending_z: Optional[BucklingLoads] = None,
                                  Anet: Optional[float] = None,
                                  Sfnet_y: Optional[float] = None,
                                  Sfnet_z: Optional[float] = None,
                                  overwrite: bool = False) -> CrossSection:
    """Fill ``A_eff`` (and optionally ``Wy_eff``/``Wz_eff``) on ``section`` from
    CUFSM/DSM, so the existing EN 15512 effective-section checks use buckling
    properties derived from the signature curve instead of hand-supplied test
    values.

    ``axial`` is required (local/distortional axial loads); pass ``bending_y``/
    ``bending_z`` to also derive the effective moduli.  Existing non-``None``
    values are kept unless ``overwrite`` is set.  Returns the same section.
    """
    if overwrite or section.A_eff is None:
        section.A_eff = effective_area(section, steel, axial, Anet=Anet)
    if bending_y is not None and (overwrite or section.Wy_eff is None):
        section.Wy_eff = dsm.section_modulus_effective(
            steel.fy, section.Wely, bending_y.Pcrl, bending_y.Pcrd,
            Sfnet=Sfnet_y)
    if bending_z is not None and (overwrite or section.Wz_eff is None):
        section.Wz_eff = dsm.section_modulus_effective(
            steel.fy, section.Welz, bending_z.Pcrl, bending_z.Pcrd,
            Sfnet=Sfnet_z)
    return section


# =====================================================================
# CUFSM model geometry -> full section properties + EN 15512 validation
# =====================================================================
def parse_cufsm_model(lines: Sequence[str]):
    """Parse a CUFSM model (node + element mesh) from text lines.

    Two layouts are accepted:

    * **labelled blocks** - a line containing ``node``/``nodes`` then rows
      ``id, x, y`` (extra columns ignored), a line containing ``elem``/
      ``elements`` then rows ``id, node_i, node_j, t`` (or ``node_i, node_j,
      t``).  ``#`` and ``%`` start comments;
    * **raw CUFSM matrices** - no labels: 8-column rows are nodes
      ``[num x z ...]`` and 5-column rows are elements ``[num i j t mat]``.

    Returns ``(nodes, elems)`` = ``({id: (x, y)}, [(i, j, t), ...])``.
    """
    nodes: dict = {}
    elems: list = []
    mode = None                              # 'node' | 'elem' | None (heuristic)
    for raw in lines:
        line = raw.split("#", 1)[0].split("%", 1)[0].strip()   # drop comments
        if not line:
            continue
        if any(ch.isalpha() for ch in line):     # a header / label line
            low = line.lower()
            if "elem" in low:                     # check 'elem' before 'node'
                mode = "elem"
            elif "node" in low:
                mode = "node"
            continue                          # never parse an alpha line as data
        vals = []
        ok = True
        for tok in line.replace(",", " ").split():
            try:
                vals.append(float(tok))
            except ValueError:
                ok = False
                break
        if not ok or not vals:
            continue
        kind = mode
        if kind is None:                      # unlabelled: classify by width
            kind = "node" if len(vals) >= 8 or len(vals) == 3 else "elem"
        if kind == "node" and len(vals) >= 3:
            nodes[int(round(vals[0]))] = (vals[1], vals[2])
        elif kind == "elem":
            if len(vals) >= 4:                # id, i, j, t (, mat)
                i, j, t = int(round(vals[1])), int(round(vals[2])), vals[3]
            elif len(vals) == 3:              # i, j, t
                i, j, t = int(round(vals[0])), int(round(vals[1])), vals[2]
            else:
                continue
            elems.append((i, j, t))
    if not nodes or not elems:
        raise ValueError("could not parse a CUFSM model - need both node rows "
                         "and element rows (use [nodes] / [elements] labels, "
                         "or the raw 8-col node / 5-col element matrices)")
    return nodes, elems


def read_cufsm_model(path: str):
    """Read a CUFSM model file (see :func:`parse_cufsm_model`)."""
    with open(path, "r", encoding="utf-8") as fh:
        return parse_cufsm_model(fh.read().splitlines())


def properties_from_cufsm(source) -> SectionProperties:
    """Full thin-walled section properties from a CUFSM model: a file path, or
    a pre-parsed ``(nodes, elems)`` tuple."""
    if isinstance(source, (tuple, list)) and len(source) == 2 \
            and isinstance(source[0], dict):
        nodes, elems = source
    else:
        nodes, elems = read_cufsm_model(source)
    return section_props.thin_walled_properties(nodes, elems)


@dataclass
class PropertyCheck:
    """One row of the property validation: a quantity, the CUFSM value, the
    master value (or None), the relative difference and a status."""

    quantity: str
    cufsm: float
    master: Optional[float]
    unit: str
    pct: Optional[float] = None              # (cufsm-master)/master * 100
    status: str = "n/a"                      # OK | CHECK | n/a (master blank)


@dataclass
class PropertyReport:
    rows: List[PropertyCheck]
    tol: float

    @property
    def ok(self) -> bool:
        return all(r.status != "CHECK" for r in self.rows)


def validate_properties(props: SectionProperties, section: CrossSection,
                        tol: float = 0.05) -> PropertyReport:
    """Compare CUFSM-computed section properties with a master CrossSection.

    Area and torsion/warping/shear-centre are compared directly; the two
    principal second moments are matched to the master Iy/Iz by magnitude (so
    the local-axis naming convention does not matter).  ``tol`` is the relative
    tolerance flagged as CHECK (default 5%)."""
    rows: List[PropertyCheck] = []

    def add(name, cufsm_val, master_val, unit):
        pct = status = None
        if master_val is None or master_val == 0:
            status = "n/a (master blank)"
        else:
            pct = (cufsm_val - master_val) / master_val * 100.0
            status = "OK" if abs(pct) <= tol * 100.0 else "CHECK"
        rows.append(PropertyCheck(name, cufsm_val, master_val, unit, pct,
                                  status))

    add("A", props.A, section.A, "mm^2")
    # principal moments matched to the master pair by magnitude
    c_minor, c_major = sorted((props.I2, props.I1))
    m_minor, m_major = sorted((section.Iz, section.Iy))
    add("I_minor", c_minor, m_minor, "mm^4")
    add("I_major", c_major, m_major, "mm^4")
    add("J (It)", props.J, section.It_gross if section.It_gross else section.J,
        "mm^4")
    add("Cw (Iw)", props.Cw, section.Iw_gross, "mm^6")
    add("y0 (shear-centre offset)", math.hypot(props.x_sc, props.y_sc),
        section.y0, "mm")
    return PropertyReport(rows=rows, tol=tol)


def validation_markdown(report: PropertyReport) -> str:
    """Markdown table of a :func:`validate_properties` report."""
    out = [f"| Quantity | CUFSM | Master | Δ% | Status |",
           "|---|---:|---:|---:|---|"]
    for r in report.rows:
        m = "-" if r.master is None else f"{r.master:,.4g}"
        p = "-" if r.pct is None else f"{r.pct:+.1f}%"
        out.append(f"| {r.quantity} [{r.unit}] | {r.cufsm:,.4g} | {m} | {p} "
                   f"| {r.status} |")
    verdict = "all within tolerance" if report.ok else "differences to review"
    out.append("")
    out.append(f"*{verdict} (tol ±{report.tol*100:.0f}%).*")
    return "\n".join(out)


def populate_gross_properties(section: CrossSection, props: SectionProperties,
                              overwrite: bool = False) -> CrossSection:
    """Fill the gross torsion / warping / shear-centre fields EN 15512 9.7.5
    needs (``It_gross``, ``Iw_gross``, ``y0``) - and ``Iy_gross``/``Iz_gross``
    when missing - from the CUFSM geometry, so the flexural-torsional buckling
    check uses computed rather than estimated values.  Existing values are kept
    unless ``overwrite`` is set.  Returns the same section."""
    if overwrite or section.It_gross is None:
        section.It_gross = props.J
    if overwrite or section.Iw_gross is None:
        section.Iw_gross = props.Cw
    if overwrite or section.y0 is None:
        section.y0 = math.hypot(props.x_sc, props.y_sc)
    # map the principal pair onto the master's Iy/Iz by magnitude
    c_minor, c_major = sorted((props.I2, props.I1))
    if overwrite or section.Iy_gross is None:
        section.Iy_gross = c_major if section.Iy >= section.Iz else c_minor
    if overwrite or section.Iz_gross is None:
        section.Iz_gross = c_minor if section.Iy >= section.Iz else c_major
    return section


# =====================================================================
# CufsmData - CUFSM inputs attached to a section, applied in a build
# =====================================================================
@dataclass
class CufsmData:
    """CUFSM inputs associated with a section, applied automatically when the
    section is used in a build (``SectionLibrary.attach_cufsm`` /
    ``RackConfig.cufsm``).  Both parts are optional:

    model     : a CUFSM model file path, or a ``(nodes, elems)`` tuple -> the
                gross J / Cw / shear-centre / inertia (EN 15512 9.7.5 inputs).
    signature : the axial local/distortional source -> effective area + the
                DSM check.  Accepts a :class:`BucklingLoads`, a signature-curve
                file path, or a ``(Pcrl, Pcrd)`` pair [N].
    reference : scale applied to a signature-curve *file* (for load-factor
                curves; 1.0 when the file is already in load units).
    Anet      : net cross-section area through the perforations [mm^2].
    bending_y / bending_z : optional :class:`BucklingLoads` (Mcrl/Mcrd in their
                Pcrl/Pcrd slots) for the effective moduli and the DSM bending.
    """

    model: Optional[object] = None
    signature: Optional[object] = None
    reference: float = 1.0
    Anet: Optional[float] = None
    bending_y: Optional[BucklingLoads] = None
    bending_z: Optional[BucklingLoads] = None


def _resolve_axial(signature, reference: float) -> Optional[BucklingLoads]:
    """Coerce a CufsmData.signature into BucklingLoads."""
    if signature is None or isinstance(signature, BucklingLoads):
        return signature
    if isinstance(signature, str):
        hw, val = read_signature_csv(signature)
        return loads_from_signature(hw, val, reference=reference)
    pcrl, pcrd = signature                       # (Pcrl, Pcrd) pair
    return BucklingLoads(Pcrl=float(pcrl), Pcrd=float(pcrd))


def apply_to_section(section: CrossSection, steel: Steel, data: "CufsmData",
                     overwrite: bool = False) -> CrossSection:
    """Apply a :class:`CufsmData` to a section: populate the gross torsion /
    warping / shear-centre from the model, and the effective area + the
    :class:`~rack15512.model.DSMData` (local/distortional) from the signature,
    so the EN 15512 FT-buckling and the DSM check both pick them up.  Existing
    values are kept unless ``overwrite`` is set."""
    if data.model is not None:
        populate_gross_properties(section, properties_from_cufsm(data.model),
                                  overwrite=overwrite)
    axial = _resolve_axial(data.signature, data.reference)
    if axial is not None:
        populate_effective_properties(
            section, steel, axial=axial, bending_y=data.bending_y,
            bending_z=data.bending_z, Anet=data.Anet, overwrite=overwrite)
        if overwrite or section.dsm is None:
            kw = dict(Pcrl=axial.Pcrl, Pcrd=axial.Pcrd)
            if data.Anet is not None:
                kw["Anet"] = data.Anet
            if data.bending_z is not None:
                kw["Mcrl_z"] = data.bending_z.Pcrl
                kw["Mcrd_z"] = data.bending_z.Pcrd
            if data.bending_y is not None:
                kw["Mcrl_y"] = data.bending_y.Pcrl
                kw["Mcrd_y"] = data.bending_y.Pcrd
            section.dsm = DSMData(**kw)
    return section

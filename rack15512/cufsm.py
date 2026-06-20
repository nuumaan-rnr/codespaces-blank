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

import csv
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from . import dsm
from .model import CrossSection, Steel

__all__ = [
    "BucklingLoads", "signature_minima", "classify_minima",
    "read_signature_csv", "loads_from_signature",
    "effective_area", "populate_effective_properties",
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

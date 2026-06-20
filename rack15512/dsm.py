"""Direct Strength Method (DSM) member strengths from CUFSM elastic buckling.

This module turns the elastic buckling loads of a cold-formed (perforated)
section - the kind CUFSM produces from its signature curve - into nominal
member resistances for the local, distortional and global buckling limit
states.  It is the "sections/DSM" leg of the rack pipeline: CUFSM supplies the
length-independent local (``Pcrl``/``Mcrl``) and distortional (``Pcrd``/
``Mcrd``) elastic buckling loads, the global elastic load (``Pcre``/``Mcre``)
comes from the frame/member analysis already in this package, and the DSM
equations below combine them into a strength.

Basis: AISI S100-16 (North American Specification) Direct Strength Method -
columns Chapter E, beams Chapter F - together with the members-with-holes
provisions (net-section yield ``Pynet = Anet*Fy`` and the modified
distortional transition).  With ``Anet = Ag`` (no holes) the equations reduce
to the standard unperforated DSM.

EN 15512 context: EN 15512 / EN 1993-1-3 design the perforated upright through
an *effective cross-section* whose area and moduli normally come from stub-
column and bending tests.  DSM is an internationally validated analytical
alternative to those tests for the local and distortional limit states; the
research record (e.g. Moen & Schafer; the modified distortional curve for rack
uprights) specifically targets perforated rack sections.  Use it to *derive*
or *cross-check* the effective properties supplied to the EN checks - it does
not remove EN 15512's need for type-test validation of the final design.

Units are consistent (this package uses N, mm, MPa); the equations are
dimensionless in form so any consistent system works.  A resistance/partial
factor (AISI phi / Omega, or an EN gamma_M) is applied by the caller, not
here - these are *nominal* strengths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

__all__ = [
    "ColumnStrength", "BeamStrength",
    "column_strength", "beam_strength",
    "stub_column_strength", "effective_area",
    "section_modulus_effective",
]


# --------------------------------------------------------------------------
# Columns (axial compression) - AISI S100-16 Chapter E + holes
# --------------------------------------------------------------------------
@dataclass
class ColumnStrength:
    """Result of a DSM column (axial) evaluation.  All loads in force units.

    ``Pn`` is the governing nominal axial strength = min(Pne, Pnl, Pnd).
    ``governs`` names the controlling limit state.
    """

    Py: float          # squash load Ag*Fy
    Pynet: float       # net-section yield Anet*Fy
    Pcre: float        # global (flexural / torsional / flex-tors) elastic load
    Pcrl: float        # local elastic buckling load (from CUFSM)
    Pcrd: float        # distortional elastic buckling load (from CUFSM)
    Pne: float         # global nominal strength (E2)
    Pnl: float         # local nominal strength (E3)
    Pnd: float         # distortional nominal strength (E4)
    Pn: float          # governing nominal strength
    governs: str       # 'global' | 'local' | 'distortional'


def _pne(Py: float, Pcre: float) -> float:
    """Global column strength, AISI S100-16 E2.1 (flexural / torsional /
    flexural-torsional buckling).  ``Pcre`` is the least global elastic load."""
    if Pcre <= 0.0:
        return 0.0
    lam_c = (Py / Pcre) ** 0.5
    if lam_c <= 1.5:
        return (0.658 ** (lam_c ** 2)) * Py
    return (0.877 / lam_c ** 2) * Py


def _pnl(Pne: float, Pcrl: float, Pynet: float) -> float:
    """Local column strength, AISI S100-16 E3.2 (local-global interaction),
    with the members-with-holes cap Pnl <= Pynet (E3.2 for holes)."""
    if Pne <= 0.0:
        return 0.0
    lam_l = (Pne / Pcrl) ** 0.5 if Pcrl > 0.0 else 1e9
    if lam_l <= 0.776:
        pnl = Pne
    else:
        r = Pcrl / Pne
        pnl = (1.0 - 0.15 * r ** 0.4) * r ** 0.4 * Pne
    return min(pnl, Pynet)


def _pnd(Py: float, Pcrd: float, Pynet: float) -> float:
    """Distortional column strength, AISI S100-16 E4.2, with the members-with-
    holes modified transition (E4.2 for holes).  Reduces to the standard curve
    when Pynet == Py."""
    if Pcrd <= 0.0:
        return Py
    lam_d = (Py / Pcrd) ** 0.5

    def _curve(lam: float) -> float:
        if lam <= 0.561:
            return Py
        r = 1.0 / lam ** 2          # = Pcrd/Py
        return (1.0 - 0.25 * r ** 0.6) * r ** 0.6 * Py

    if Pynet >= Py:                 # no holes -> standard distortional curve
        return _curve(lam_d)

    # members with holes: linear transition between net yield and the curve
    lam_d1 = 0.561 * (Pynet / Py)
    lam_d2 = 0.561 * (14.0 * (Py / Pynet) ** 0.4 - 13.0)
    if lam_d <= lam_d1:
        return Pynet
    if lam_d <= lam_d2:
        r2 = 1.0 / lam_d2 ** 2
        Pd2 = (1.0 - 0.25 * r2 ** 0.6) * r2 ** 0.6 * Py
        return Pynet - ((Pynet - Pd2) / (lam_d2 - lam_d1)) * (lam_d - lam_d1)
    return _curve(lam_d)


def column_strength(Py: float, Pcre: float, Pcrl: float, Pcrd: float,
                    Pynet: Optional[float] = None) -> ColumnStrength:
    """DSM nominal axial strength of a (perforated) cold-formed column.

    Parameters
    ----------
    Py     : squash load of the gross section, ``Ag * Fy``.
    Pcre   : least global elastic buckling load (flexural / torsional /
             flexural-torsional).  For a rack upright take this from the frame
             analysis (Euler / EN 15512 9.7.5 N_cr), so the global limit state
             stays consistent with the second-order model.
    Pcrl   : local elastic buckling load (CUFSM signature-curve local minimum).
    Pcrd   : distortional elastic buckling load (CUFSM distortional minimum).
    Pynet  : net-section yield ``Anet * Fy``.  Defaults to ``Py`` (no holes).

    Returns a :class:`ColumnStrength`.  Divide ``Pn`` by the chosen resistance
    factor (AISI phi_c / Omega_c, or an EN gamma_M) to get the design value.
    """
    if Pynet is None:
        Pynet = Py
    Pne = _pne(Py, Pcre)
    Pnl = _pnl(Pne, Pcrl, Pynet)
    Pnd = _pnd(Py, Pcrd, Pynet)
    options = (("global", Pne), ("local", Pnl), ("distortional", Pnd))
    governs, Pn = min(options, key=lambda kv: kv[1])
    return ColumnStrength(Py=Py, Pynet=Pynet, Pcre=Pcre, Pcrl=Pcrl, Pcrd=Pcrd,
                          Pne=Pne, Pnl=Pnl, Pnd=Pnd, Pn=Pn, governs=governs)


def stub_column_strength(Py: float, Pcrl: float, Pcrd: float,
                         Pynet: Optional[float] = None) -> ColumnStrength:
    """Cross-section (stub-column) DSM strength: the local + distortional
    resistance with the global limit state removed (Pne -> Py).  This is the
    DSM analogue of the EN 15512 effective-section squash resistance and is
    what :func:`effective_area` divides by Fy."""
    if Pynet is None:
        Pynet = Py
    # Pne -> Py by passing a very large global elastic load.
    return column_strength(Py, Pcre=1e30, Pcrl=Pcrl, Pcrd=Pcrd, Pynet=Pynet)


def effective_area(fy: float, Ag: float, Pcrl: float, Pcrd: float,
                   Anet: Optional[float] = None) -> float:
    """Effective area A_eff [mm^2] from DSM, for use in the EN 15512 effective-
    section checks.  Defined as the stub-column (local + distortional) strength
    divided by Fy, so ``A_eff * fy`` reproduces the cross-section resistance.

    This lets a CUFSM analysis *populate* the ``A_eff`` that EN 15512 otherwise
    expects from a stub-column test.
    """
    Py = Ag * fy
    Pynet = (Anet if Anet is not None else Ag) * fy
    s = stub_column_strength(Py, Pcrl, Pcrd, Pynet)
    return s.Pn / fy


# --------------------------------------------------------------------------
# Beams (bending) - AISI S100-16 Chapter F + holes
# --------------------------------------------------------------------------
@dataclass
class BeamStrength:
    My: float          # first-yield moment Sf*Fy (gross)
    Mynet: float       # net-section yield Sfnet*Fy
    Mcre: float        # global (lateral-torsional) elastic moment
    Mcrl: float        # local elastic buckling moment (from CUFSM)
    Mcrd: float        # distortional elastic buckling moment (from CUFSM)
    Mne: float         # global nominal strength (F2)
    Mnl: float         # local nominal strength (F3)
    Mnd: float         # distortional nominal strength (F4)
    Mn: float          # governing nominal strength
    governs: str


def _mne(My: float, Mcre: float) -> float:
    """Global (lateral-torsional) beam strength, AISI S100-16 F2.1."""
    if Mcre <= 0.0:
        return 0.0
    if Mcre < 0.56 * My:
        return Mcre
    if Mcre <= 2.78 * My:
        return (10.0 / 9.0) * My * (1.0 - 10.0 * My / (36.0 * Mcre))
    return My


def _mnl(Mne: float, Mcrl: float, Mynet: float) -> float:
    """Local beam strength, AISI S100-16 F3.2, with the holes cap Mnl<=Mynet."""
    if Mne <= 0.0:
        return 0.0
    lam_l = (Mne / Mcrl) ** 0.5 if Mcrl > 0.0 else 1e9
    if lam_l <= 0.776:
        mnl = Mne
    else:
        r = Mcrl / Mne
        mnl = (1.0 - 0.15 * r ** 0.4) * r ** 0.4 * Mne
    return min(mnl, Mynet)


def _mnd(My: float, Mcrd: float, Mynet: float) -> float:
    """Distortional beam strength, AISI S100-16 F4.2.  For sections with holes
    the gross-section curve is used and capped by the net-section yield
    ``Mynet`` (conservative: the explicit perforated distortional transition is
    not claimed here)."""
    if Mcrd <= 0.0:
        return min(My, Mynet)
    lam_d = (My / Mcrd) ** 0.5
    if lam_d <= 0.673:
        mnd = My
    else:
        r = Mcrd / My
        mnd = (1.0 - 0.22 * r ** 0.5) * r ** 0.5 * My
    return min(mnd, Mynet)


def beam_strength(My: float, Mcre: float, Mcrl: float, Mcrd: float,
                  Mynet: Optional[float] = None) -> BeamStrength:
    """DSM nominal bending strength of a (perforated) cold-formed beam.

    ``My = Sf*Fy`` (gross extreme-fibre first yield), ``Mcre`` the global
    lateral-torsional elastic moment, ``Mcrl``/``Mcrd`` the CUFSM local /
    distortional elastic moments, ``Mynet = Sfnet*Fy`` (defaults to ``My``).
    """
    if Mynet is None:
        Mynet = My
    Mne = _mne(My, Mcre)
    Mnl = _mnl(Mne, Mcrl, Mynet)
    Mnd = _mnd(My, Mcrd, Mynet)
    options = (("global", Mne), ("local", Mnl), ("distortional", Mnd))
    governs, Mn = min(options, key=lambda kv: kv[1])
    return BeamStrength(My=My, Mynet=Mynet, Mcre=Mcre, Mcrl=Mcrl, Mcrd=Mcrd,
                        Mne=Mne, Mnl=Mnl, Mnd=Mnd, Mn=Mn, governs=governs)


def section_modulus_effective(fy: float, Sf: float, Mcrl: float, Mcrd: float,
                              Sfnet: Optional[float] = None) -> float:
    """Effective section modulus W_eff [mm^3] from DSM: the local + distortional
    bending resistance (no lateral-torsional reduction) divided by Fy, for use
    in the EN 15512 effective-section stress check."""
    My = Sf * fy
    Mynet = (Sfnet if Sfnet is not None else Sf) * fy
    s = beam_strength(My, Mcre=1e30, Mcrl=Mcrl, Mcrd=Mcrd, Mynet=Mynet)
    return s.Mn / fy

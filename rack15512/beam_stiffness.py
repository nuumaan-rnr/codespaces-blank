"""Calculated beam-to-upright connector rotational stiffness, used when no
tested connector value (master beam-stiffness import / connection test) is
available - the beam-stiffness analogue of rack15512.base_stiffness.

A beam-end connection cannot be stiffer than the beam it connects, so the
connection rotational stiffness is bounded by the beam's own flexural (line)
stiffness.  Following the EN 1993-1-8 connection-classification reference unit
E*I_b / L_b, the calculated connector stiffness is

        k_conn = factor * E * I_b / L_b      [N*mm/rad]

with I_b the beam strong-axis second moment (down-aisle / gravity bending, the
section's Iz), L_b the beam span and `factor` the end-rotation coefficient:

  * factor = 2  -> far end pinned (the classic "beam line" reference),
  * factor = 4  -> far end fixed,
  * factor = 6  -> double curvature (the down-aisle sway mechanism) - the
                   stiffest / upper-bound case ("maximum stiffness of the beam").

This is an estimate for preliminary design; a tested connector stiffness
(master beam-stiffness table or an EN 15512 connection test) should be used
when available.  Returned in N*mm/rad (the unit used throughout the model).
"""

from __future__ import annotations

from typing import Optional

import math


def derived_connector_stiffness(beam_section, E: float, span: float,
                                factor: float = 2.0) -> float:
    """Beam-end connector rotational stiffness [N*mm/rad] = factor * E*I_b/L_b.

    beam_section : the beam CrossSection (uses Iz, the strong/gravity axis).
    E            : beam steel modulus [MPa].
    span         : beam span L_b [mm] (the bay width).
    factor       : end-rotation coefficient (2 pinned, 4 fixed, 6 sway).
    """
    Iz = float(getattr(beam_section, "Iz", 0.0) or 0.0)
    L = float(span) if span and span > 0 else 1.0
    return max(float(factor) * float(E) * Iz / L, 1.0)


def bolt_shear_resistance(d: float, grade: str, gamma_M2: float = 1.25,
                          planes: int = 1) -> float:
    """Per-bolt shear resistance F_v,Rd [N] (EN 1993-1-8 3.6.1), the same
    basis as the bracing bolt check: A_s = 0.78*(pi/4)*d^2, alpha_v = 0.6,
    f_ub = 100*grade-lead (e.g. '8.8' -> 800 MPa)."""
    try:
        lead = int(str(grade).split(".")[0])
    except (ValueError, AttributeError, IndexError):
        lead = 8
    A_s = 0.78 * (math.pi / 4.0) * float(d) ** 2
    f_ub = 100.0 * lead
    return max(planes, 1) * 0.6 * A_s * f_ub / max(gamma_M2, 1e-6)


def bolt_tension_resistance(d: float, grade: str,
                            gamma_M2: float = 1.25) -> float:
    """Per-bolt tension resistance F_t,Rd [N] (EN 1993-1-8 Table 3.4):
    F_t,Rd = 0.9 * f_ub * A_s / gamma_M2, with A_s = 0.78*(pi/4)*d^2 and
    f_ub = 100*grade-lead.  Under a beam-end moment the connector bolts on the
    tension side go into TENSION (they resist the opening of the joint), so
    this - not the shear/bearing value - is the moment-couple resistance."""
    try:
        lead = int(str(grade).split(".")[0])
    except (ValueError, AttributeError, IndexError):
        lead = 8
    A_s = 0.78 * (math.pi / 4.0) * float(d) ** 2
    f_ub = 100.0 * lead
    return 0.9 * f_ub * A_s / max(gamma_M2, 1e-6)


def effective_connector_with_bolts(k_base: float, m_rd_base: Optional[float],
                                   n_bolts: int, *,
                                   table: Optional[list] = None,
                                   lever: Optional[float] = None,
                                   f_t_rd: Optional[float] = None):
    """Effective beam-end connector rotational stiffness [N*mm/rad] and moment
    capacity [N*mm] after adding `n_bolts` moment bolts.

    STIFFNESS.  A rack beam-end connector's rotational flexibility is dominated
    by the bending of the bracket and the perforated upright face - components
    that act IN SERIES with the (stiff) bolts, so the bolt stiffness does NOT
    add to the connector stiffness by any simple k_bolt*a^2 rule; the softest
    series component governs.  EN 15512 therefore requires the connector
    stiffness of each bolted configuration to be measured (Annex A bending
    test).  So the stiffness is raised ONLY when a tested `table`
    [[n_bolts, k, M_Rd], ...] provides it; otherwise k_eff = k_base (the bolts
    add capacity, not a calculated stiffness).

    MOMENT CAPACITY.  The bolts on the tension side resist the beam-end moment
    as a TENSION couple about the compression edge:
        M_Rd,eff = M_Rd_base + n_bolts * F_t,Rd * a          (a = `lever`)
    with F_t,Rd = `f_t_rd` the per-bolt tension resistance (EN 1993-1-8
    Table 3.4).  The concurrent shear V (beam reaction) shares the same bolts,
    so the usable moment is further limited by the connector M-V interaction
    (EN 15512 9.5.4, applied in the connector check) and the bolts must satisfy
    the tension+shear interaction (EN 1993-1-8 Table 3.4) - this M_Rd is the
    pure-bending upper bound before that reduction.

    Returns (k_eff, m_rd_eff).
    """
    if n_bolts <= 0:
        return k_base, m_rd_base
    if table:
        rows = sorted((r for r in table if int(r[0]) <= n_bolts),
                      key=lambda r: r[0])
        if rows:
            r = rows[-1]
            k = float(r[1]) if len(r) > 1 and r[1] else k_base
            mr = (float(r[2]) if len(r) > 2 and r[2] else m_rd_base)
            return k, mr
    a = float(lever) if lever and lever > 0 else 0.0
    m_eff = m_rd_base
    if m_rd_base is not None and f_t_rd and a:
        m_eff = m_rd_base + n_bolts * float(f_t_rd) * a
    return k_base, m_eff        # stiffness unchanged without a tested value

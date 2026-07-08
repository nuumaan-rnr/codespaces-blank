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


def bolt_bearing_stiffness(d: float, t: float, fu: float,
                           e1: Optional[float] = None) -> float:
    """Per-bolt slip / bearing spring stiffness [N/mm] (EN 1993-1-8 6.3.2,
    bearing component): S = E * k, with the coefficient k = 24*k_b*k_t*d*f_u/E,
    so S = 24*k_b*k_t*d*f_u.  k_b from the end distance (0.25*e1/d + 0.375,
    capped at 1.0/0.625), k_t = 1.5*t/d_M16 (d_M16 = 16 mm, capped 2.5).
    A code-referenced estimate for the connector plate; use a tested value
    when available."""
    d = float(d); t = float(t); fu = float(fu)
    if d <= 0 or t <= 0 or fu <= 0:
        return 0.0
    e1 = e1 if (e1 and e1 > 0) else 1.5 * d
    k_b = min(0.25 * e1 / d + 0.375, 0.625)
    k_t = min(1.5 * t / 16.0, 2.5)
    return 24.0 * k_b * k_t * d * fu


def effective_connector_with_bolts(k_base: float, m_rd_base: Optional[float],
                                   n_bolts: int, *,
                                   table: Optional[list] = None,
                                   k_bolt: Optional[float] = None,
                                   lever: Optional[float] = None,
                                   f_bolt: Optional[float] = None):
    """Effective beam-end connector rotational stiffness [N*mm/rad] and moment
    capacity [N*mm] after adding `n_bolts` moment bolts.

    1. If a tested `table` [[n, k, M_Rd], ...] has a row with n <= n_bolts, the
       nearest such row is used directly (EN 15512 Annex A, code-correct).
    2. Otherwise the bolts are a rotational spring group IN PARALLEL with the
       bare hook connector:
            k_eff    = k_base   + n_bolts * k_bolt * a^2
            M_Rd,eff = M_Rd_base + n_bolts * f_bolt * a
       with a = `lever` (bolt lever arm from the rotation centre).  Terms
       whose inputs are missing are simply not added (no stiffness invented).

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
    k_eff = k_base + (n_bolts * float(k_bolt) * a * a
                      if (k_bolt and a) else 0.0)
    m_eff = m_rd_base
    if m_rd_base is not None and f_bolt and a:
        m_eff = m_rd_base + n_bolts * float(f_bolt) * a
    return k_eff, m_eff

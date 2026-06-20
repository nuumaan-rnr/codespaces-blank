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

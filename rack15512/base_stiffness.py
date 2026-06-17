"""Calculated down-aisle base (floor-connection) rotational stiffness for a
storage-rack upright, used when no tested floor-connection table is available.

Formulas from Gilbert & Rasmussen, "Experimental test on steel storage rack
components", University of Sydney Research Report R899 (2009), section 5.5:

  * concrete-floor term (Eq 43, after Sarawit 2003):
        k_b = (7/25) . b . d^2 . E_c
    where b, d are the upright section depth and width [mm] and E_c is the
    floor (concrete) modulus [MPa];
  * upright term / ULS design value (Eq 46, after Godley 2007):
        k_h = E . I_c / h
    where E [MPa] and I_c [mm^4] are the upright modulus and down-aisle second
    moment and h [mm] is the distance from the floor to the first beam;
  * combined in series (Eq 45), floor flexibility + upright flexibility:
        k_base = 1 / (1/k_b + 1/k_h)

R899 notes the concrete term is much stiffer than the upright term, so the
series is governed by k_h and reduces to ~k_h.  All stiffnesses are returned in
N*mm/rad (the unit used throughout the model and the master tables).
"""

from __future__ import annotations


def concrete_modulus(f_ck: float = 25.0) -> float:
    """Concrete secant modulus E_cm [MPa] from the characteristic cylinder
    strength f_ck [MPa] (EN 1992-1-1 Table 3.1: E_cm = 22000*(f_cm/10)^0.3,
    f_cm = f_ck + 8).  ~31500 MPa at C25, close to the ~30000 MPa R899 uses."""
    return 22000.0 * ((float(f_ck) + 8.0) / 10.0) ** 0.3


def derived_base_stiffness(section, E: float, h: float,
                           f_ck: float = 25.0) -> float:
    """Down-aisle base rotational stiffness [N*mm/rad] from the R899 formulas.

    section : the upright CrossSection (uses depth_h, width_b, Iz).
    E       : upright steel modulus [MPa].
    h       : floor-to-first-beam height [mm].
    f_ck    : floor concrete characteristic strength [MPa] (-> E_c).

    Returns the series combination of the concrete-floor term (R899 Eq 43) and
    the upright term (R899 Eq 46); falls back to the upright term alone when the
    section has no plan dimensions.
    """
    Iz = float(section.Iz)
    h = float(h) if h and h > 0 else 1.0
    k_h = E * Iz / h                                 # R899 Eq 46 (Godley)
    b = section.depth_h
    d = section.width_b
    if b and d and b > 0 and d > 0:
        Ec = concrete_modulus(f_ck)
        k_b = (7.0 / 25.0) * float(b) * float(d) ** 2 * Ec   # R899 Eq 43
        return 1.0 / (1.0 / k_b + 1.0 / k_h)         # R899 Eq 45 (series)
    return k_h

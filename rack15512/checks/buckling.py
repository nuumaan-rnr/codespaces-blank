"""Flexural buckling reduction factor per EN 1993-1-1 6.3.1 (referenced by
EN 15512 for member checks)."""

from __future__ import annotations

import math

# Table 6.1 / 6.2 imperfection factors
ALPHA = {"a0": 0.13, "a": 0.21, "b": 0.34, "c": 0.49, "d": 0.76}


def chi(lambda_bar: float, curve: str = "b") -> float:
    """Buckling reduction factor chi for relative slenderness lambda_bar."""
    if lambda_bar <= 0.2:
        return 1.0
    alpha = ALPHA[curve]
    phi = 0.5 * (1.0 + alpha * (lambda_bar - 0.2) + lambda_bar**2)
    chi_val = 1.0 / (phi + math.sqrt(phi**2 - lambda_bar**2))
    return min(chi_val, 1.0)


def lambda_bar(A_eff: float, fy: float, N_cr: float) -> float:
    """Relative slenderness using the effective area (EN 1993-1-3 /
    EN 15512 approach for perforated cold-formed sections)."""
    return math.sqrt(A_eff * fy / N_cr)


def n_cr(E: float, I: float, L_cr: float) -> float:
    """Euler critical load for buckling length L_cr."""
    return math.pi**2 * E * I / L_cr**2


def n_cr_torsional(E: float, G: float, It: float, Iw: float,
                   i0_sq: float, L_T: float) -> float:
    """Critical load for torsional buckling about the shear centre
    (EN 15512 9.7.5.1 / EN 1993-1-3):
        Ncr,T = (1/i0^2) * (G*It + pi^2*E*Iw / L_T^2)."""
    return (G * It + math.pi**2 * E * Iw / L_T**2) / i0_sq


def n_cr_flex_tors(N_cr_y: float, N_cr_T: float, y0: float,
                   i0_sq: float) -> float:
    """Critical load for flexural-torsional buckling (EN 15512 9.7.5.1):
        beta = 1 - (y0/i0)^2
        Ncr,FT = Ncr,y/(2 beta) * [1 + Ncr,T/Ncr,y
                 - sqrt((1 - Ncr,T/Ncr,y)^2 + 4 (y0/i0)^2 Ncr,T/Ncr,y)]."""
    beta = 1.0 - y0 * y0 / i0_sq
    if beta <= 1.0e-9:
        return min(N_cr_y, N_cr_T)
    r = N_cr_T / N_cr_y
    disc = (1.0 - r) ** 2 + 4.0 * (y0 * y0 / i0_sq) * r
    return N_cr_y / (2.0 * beta) * (1.0 + r - math.sqrt(disc))


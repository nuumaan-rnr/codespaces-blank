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

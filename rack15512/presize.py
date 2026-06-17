"""Static (closed-form) upright pre-sizing.

Given the calculated axial load on an upright and its buckling length, rank the
master upright sections by the SAME EN 1993-1-1 / EN 15512 column-buckling
utilisation the analysis uses (rack15512.checks.en15512._buckling_checks), so the
section can be chosen in one or two iterations instead of trial-and-error.

Drive-in / radio-shuttle uprights are pinned-pinned (K = 1.0); the buckling
length is the unbraced segment.  The closed-form check reuses
rack15512.checks.buckling and the flexural-torsional helper _chi_ft, so a section
this tool reports as passing will pass the analysis (the axial demand is
gravity-dominated and barely section-dependent).
"""

from __future__ import annotations

from typing import Callable, Dict, List

from .checks import buckling
from .checks.en15512 import _chi_ft
from .model import CrossSection, Steel


def upright_utilisation(sec: CrossSection, mat: Steel, Lcr_y: float, Lcr_z: float,
                        N: float, My: float = 0.0, Mz: float = 0.0, *,
                        gamma_M1: float = 1.0, gamma_M0: float = 1.0,
                        k_M: float = 1.0, beta_T: float = 0.7) -> Dict:
    """Closed-form column utilisation for one section, mirroring
    en15512._buckling_checks.  N is the axial COMPRESSION magnitude [N] (>0),
    My/Mz the concurrent moments [N*mm].  Returns chi_min, N_b_Rd, the buckling
    and cross-section-stress utilisations and the governing axis."""
    Ncr_y = buckling.n_cr(mat.E, sec.Iy, Lcr_y)
    Ncr_z = buckling.n_cr(mat.E, sec.Iz, Lcr_z)
    lam_y = buckling.lambda_bar(sec.area_eff, mat.fy, Ncr_y)
    lam_z = buckling.lambda_bar(sec.area_eff, mat.fy, Ncr_z)
    chi_y = buckling.chi(lam_y, sec.buckling_curve_y)
    chi_z = buckling.chi(lam_z, sec.buckling_curve_z)
    chi_min = min(chi_y, chi_z)
    gov = "y" if chi_y <= chi_z else "z"
    # flexural-torsional buckling (EN 15512 9.7.5) when the gross torsion /
    # warping / shear-centre data is available (torsional length beta_T * Lcr_y)
    chi_ft = _chi_ft(sec, mat, Lcr_y, Ncr_y, beta_T)
    if chi_ft is not None and chi_ft < chi_min:
        chi_min, gov = chi_ft, "FT"

    n = abs(N)
    Nb_rd = chi_min * sec.area_eff * mat.fy / gamma_M1
    My_rd = sec.mod_y_eff * mat.fy / gamma_M1
    Mz_rd = sec.mod_z_eff * mat.fy / gamma_M1
    util_b = n / Nb_rd if Nb_rd > 0 else 99.0
    util_b += k_M * abs(My) / My_rd + k_M * abs(Mz) / Mz_rd

    # cross-section resistance (gamma_M0)
    N_rd = sec.area_eff * mat.fy / gamma_M0
    Mys_rd = sec.mod_y_eff * mat.fy / gamma_M0
    Mzs_rd = sec.mod_z_eff * mat.fy / gamma_M0
    util_s = n / N_rd if N_rd > 0 else 99.0
    util_s += abs(My) / Mys_rd + abs(Mz) / Mzs_rd

    return {"chi_min": chi_min, "N_b_Rd": Nb_rd, "gov": gov,
            "util_buckling": util_b, "util_stress": util_s,
            "util": max(util_b, util_s),
            "lambda_y": lam_y, "lambda_z": lam_z}


def suggest_uprights(lib, fy_of: Callable[[str], float], *, N: float,
                     Lcr_y: float, Lcr_z: float, E: float = 210000.0,
                     G: float = 81000.0, gamma_M1: float = 1.0,
                     gamma_M0: float = 1.0, k_M: float = 1.0,
                     beta_T: float = 0.7, My: float = 0.0, Mz: float = 0.0
                     ) -> List[Dict]:
    """Rank the master upright sections for a given axial load and buckling
    lengths.  fy_of(name) returns the section's design yield [MPa].  Rows are
    sorted by area (lightest first); the lightest passing (util <= 1) row carries
    recommended=True."""
    names = lib.names("upright") or lib.names()
    rows: List[Dict] = []
    for name in names:
        try:
            sec = lib.get(name)
        except (KeyError, ValueError):
            continue
        mat = Steel("steel", E=E, fy=float(fy_of(name)), G=G)
        u = upright_utilisation(sec, mat, Lcr_y, Lcr_z, N, My, Mz,
                                gamma_M1=gamma_M1, gamma_M0=gamma_M0,
                                k_M=k_M, beta_T=beta_T)
        rows.append({"name": name, "area": sec.area_eff, "fy": mat.fy,
                     "passes": u["util"] <= 1.0 + 1e-9, "recommended": False,
                     **u})
    rows.sort(key=lambda r: (r["area"], r["name"]))
    for r in rows:                                # lightest passing = recommended
        if r["passes"]:
            r["recommended"] = True
            break
    return rows


def static_upright_demand(cfg) -> Dict:
    """Pre-run static axial-demand estimate per upright, plus default pinned-
    pinned (K = 1.0) buckling lengths, derived from the configuration.  All
    values are editable by the user; this is just a transparent starting point.

    Worst upright ~ k_dist * average (interior columns carry up to ~2x the mean).
    """
    gQ = getattr(cfg, "gamma_Q", 1.4)
    k_dist = 2.0                                  # worst / average upright factor
    # storage-level heights (gaps) from cfg.levels, else cfg.beam_levels deltas
    if getattr(cfg, "levels", None):
        gaps = [ls.gap for ls in cfg.levels]
        n_levels = len(gaps)
    else:
        bl = sorted(getattr(cfg, "beam_levels", []) or [2000.0])
        prev, gaps = 0.0, []
        for z in bl:
            gaps.append(z - prev)
            prev = z
        n_levels = len(bl)
    H = float(getattr(cfg, "frame_height", 0.0) or 0.0) or (sum(gaps) + 1000.0)
    # cross-aisle (local y) is braced by the frame ladder at the bracing pitch
    Lcr_ca = float(getattr(cfg, "bracing_pitch", 600.0) or 600.0)
    system = getattr(cfg, "system_type", "selective")
    # down-aisle (local z):
    #  * drive-in / shuttle: the upright is unbraced down-aisle between the
    #    semi-rigid base and the portal top, so the down-aisle buckling length is
    #    the full frame height (K = 1.0, pinned-pinned) - the conservative worst
    #    case, matching the full-run analysis;
    #  * selective: restrained at every beam level by the moment frame -> the
    #    largest beam-level gap.
    if system != "selective":
        Lcr_da = H
    else:
        top_seg = max(H - sum(gaps), 0.0)
        Lcr_da = max(gaps + [top_seg]) if (gaps or top_seg) else 2000.0

    if system != "selective":                    # drive-in / shuttle
        nL = int(getattr(cfg, "n_lanes", 3))
        n_deep = int(getattr(cfg, "n_deep", 6))
        wpp = float(getattr(cfg, "weight_per_pallet", 10000.0))
        P = gQ * nL * n_deep * wpp * n_levels
        n_up = (nL + 1) * (2 * (n_deep + 1))
    else:                                         # selective pallet racking
        n_bays = int(getattr(cfg, "n_bays", 5))
        n_modules = 2 if getattr(cfg, "module", "single") == "back-to-back" else 1
        sides = 4 if n_modules == 2 else 2
        loads = [getattr(l, "pallet_load", 0.0) for l in
                 (getattr(cfg, "levels", None) or [])]
        per_level = sum(loads) if loads else (20000.0 * n_levels)
        P = gQ * per_level * n_bays * n_modules
        n_up = (n_bays + 1) * sides

    n_avg = P / n_up if n_up else 0.0
    # Lcr_y pairs with Iy = cross-aisle; Lcr_z pairs with Iz = down-aisle
    return {"N_design": k_dist * n_avg, "N_avg": n_avg, "k_dist": k_dist,
            "Lcr_y": Lcr_ca, "Lcr_z": Lcr_da, "Lcr_ca": Lcr_ca, "Lcr_da": Lcr_da,
            "fy": float(getattr(cfg, "steel_fy", 355.0)), "n_uprights": n_up,
            "P_total": P, "n_levels": n_levels}

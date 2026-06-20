"""Racks & Rollers branding - colours, logo and company details used by
the app and the reports."""

from __future__ import annotations

import base64
import os

COMPANY = "Racks & Rollers"
TAGLINE = "Storage Technologies and Automation"
WEBSITE = "www.racksandrollers.com"
PRODUCT = "EN 15512 SPR Design"
# Build marker — shown in the sidebar so you can confirm which code is running.
BUILD = "2026-06-19f · Design-stiffness reduction E/gamma_M1 for 2nd-order stability (RSTAB 'Materials (partial factor gamma_M)'): AnalysisSettings.stiffness_gamma_m (1.0 default; 1.1 matches RSTAB) - validated SPR_RSTAB CO1 sway 162.5 vs 167.1 mm, reactions 334 vs 336 kN; placement combo 1.26; charts use E/1.1 + ULS1/ULS2 governing. EN 1993-1-1 5.3.2(3) sway imperfection reduction phi=phi_s*alpha_h*alpha_m (RSTAB inclination dialog): alpha_h=2/sqrt(h), alpha_m=sqrt(0.5(1+1/m)); per-direction Phi0 (e.g. DA 1/200->1/357, CA 1/300->1/535), no phi_min floor when applied. Upright max-levels chart: largest number of beam levels (start 3, climb to 7) an UNBRACED 3-bay down-aisle semi-rigid moment frame carries at a capped 3000 kg/level - non-convergence/over-utilisation => rack too tall, reduce levels; real N+My+Mz interaction, fy=355, gamma_M1=1.1; parallel + resumable. Engine lean fast_solve path (opt-in, default off) for chart sweeps. Placement & accidental loads now default to the governing INTERIOR upright frame (SPR and drive-in); explicit load_frame still pins a line. RSTAB-matching options: EN1993 flat imperfection (1/300) vs EN15512 amplified; beam-connector stiffness override at both beam ends; nonlinear axial-dependent base (tearing under uplift); connector laws on the rotational DOF (translations tied): linear, nonlinear-elastic M-phi, and plastic (Hysteretic). 2nd-order P-Delta fix + robust near-critical solver; validated vs RSTAB CO1. EN 15512 gamma_M1=1.1; STAAD/RSTAB export"

# brand palette (sampled from the logo)
TEAL = "#0C8490"          # primary mark
TEAL_LIGHT = "#309CA8"    # subtitle / accents
GREY = "#545454"          # wordmark text
GREY_LIGHT = "#848484"
BG_TINT = "#EAF3F4"       # very light teal tint for panels

LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "rnr_logo.png")


def logo_bytes() -> bytes | None:
    try:
        with open(LOGO_PATH, "rb") as f:
            return f.read()
    except OSError:
        return None


def logo_data_uri() -> str:
    data = logo_bytes()
    if not data:
        return ""
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")

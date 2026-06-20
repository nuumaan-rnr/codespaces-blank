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
BUILD = "2026-06-19c · Model-based upright load charts: max stable working load by load-reduction search (non-convergence => reduce load), single-storey 3-bay sub-assemblage at each Lcr_DA, real N+My+Mz interaction, fy=355, gamma_M1=1.1; parallel + resumable. Engine lean fast_solve path (opt-in, default off) for chart sweeps. Placement & accidental loads now default to the governing INTERIOR upright frame (SPR and drive-in); explicit load_frame still pins a line. RSTAB-matching options: EN1993 flat imperfection (1/300) vs EN15512 amplified; beam-connector stiffness override at both beam ends; nonlinear axial-dependent base (tearing under uplift); connector laws on the rotational DOF (translations tied): linear, nonlinear-elastic M-phi, and plastic (Hysteretic). 2nd-order P-Delta fix + robust near-critical solver; validated vs RSTAB CO1. EN 15512 gamma_M1=1.1; STAAD/RSTAB export"

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

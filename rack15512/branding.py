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
BUILD = "2026-06-19 · Stiffener fix: tie the stiffener twist (rz) to the upright so the interface no longer leaves a singular rigid-body torsion mode (was producing runaway ~1e6 mm displacements and stray geometry in the viewer); partial-composite member with per-section mount_offset from the master; M8 8.8 bolts at 300/600 mm; type 1 closed-section FT credit; stiffener buckling length = bolt pitch, reported as its own set"

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

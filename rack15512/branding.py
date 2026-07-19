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
BUILD = "2026-07-13c · 2C stitching convention confirmed and recorded: back-to-back is the default assembly (not boxed), STITCH-BOLTED every 500 mm with one vertical bolt row at 50 mm pitch whose count follows the beam height (stitch_bolt_count: 150 -> 3, 200 -> 4, 300 -> 6 bolts; never fewer than 2), rarely welded - so the conservative OPEN torsion constant stands (a continuously welded box can be entered in the master with its closed J). Each generated 2C carries the convention in its description plus an EN 1993-1-1 6.4 note when the 500 mm stitch spacing exceeds 15 i_min of one channel (treat minor-axis compression as built-up); major-axis Iz = 2x is exact regardless of stitching since the equal channels share the neutral axis. Previous: Mezzanine SECTION FAMILIES: on-the-fly parametric sections by CODE (master-library names always win) - SHS{h}x{t} / RHS{h}x{b}x{t} columns (thin-walled midline, closed Bredt torsion), 1C{h}x{b}x{lip}x{t} lipped channels with optional r{radius} corner reduction per EN 1993-1-3 5.1(3), 2C coupled channels (back-to-back default, suffix B = boxed toe-to-toe; MAJOR axis Iz doubles exactly, Iy by parallel axis, conservative open torsion for stitch-bolted assemblies) and 2x2C twin assemblies; all beam codes keep Iz = MAJOR = gravity bending so stress/deflection/buckling check the strong axis. 1C FLOOR PANELS laid flat: mz_panel_section adds the panel self-weight (A x gamma / covered web width) to the floor dead load and models one representative pin-ended panel strip per floor ROTATED so gravity bending is about the MINOR axis (vecxz), stress+deflection checked like any beam (verified: strip My >> Mz). Form: section-code inputs for column / primary / secondary / joist / panel. Previous: NEW SYSTEM TYPE: Structural Mezzanine (rack15512/mezzanine.py, system_type mezzanine) alongside Selective and Drive-in. Column grid (bays x/y, bay sizes, 1-6 floors at a storey height) framed in up to three layers: continuous COLUMNS (buckling-checked per storey via checks.buckling_sets=[columns], set labels Column A1...), PRIMARY beams column-to-column along X or Y with moment / pinned / semi-rigid (k) column connections, pin-ended SECONDARY beams at a chosen spacing (also on the column lines as ties), and an optional pin-ended JOIST layer between the secondaries. FLOORING catalogue (chequered plate 3/4 mm, chipboard, plywood, grating, composite deck+concrete, custom) + extra dead + live load [kN/m2] applied as tributary UDLs on the topmost layer - totals verified exact (q x area); member self-weight from each section. Stability: vertical X-brace pairs in the outer bays of the perimeter lines (braced bays per corner) or, with bracing off, an automatic moment frame; pinned or fixed bases. ULS (gamma_G dead + gamma_Q live, 2nd order) + SLS combinations, EHF sway imperfections in both directions. New form family Structural mezzanine with the full grid / framing / flooring / connection / bracing inputs; deflection checks run on all beam layers (primary-beam deflection is per segment between secondary landings - see the module docstring), beams assumed laterally restrained by the decking. Previous highlights: SAP2000 import/export validated 1:1 against SAP 26 (exact table schemas, General sections with the full property set, base springs, connector partial fixity, EHF imperfection patterns, linear BUCKLING case; forces/deflections match SAP to 0.1-2 percent); RSTAB results comparison in-app (unit-aware reader, tolerance classification, per-member N/My/Mz, station-concurrent buckling+stress per upright, SLS beam deflection); RSTAB 8 / STAAD / SAP2000 solver exports; axial-dependent base stiffness; EN 15512 checks with concurrent-station buckling and torsional lengths from all twist restraints. Full history: git log on the app repository."

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

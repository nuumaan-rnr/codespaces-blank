"""Racks & Rollers branding - colours, logo and company details used by
the app and the reports."""

from __future__ import annotations

import base64
import os

COMPANY = "Racks & Rollers"
TAGLINE = "Storage Technologies and Automation"
WEBSITE = "www.racksandrollers.com"
PRODUCT = "EN 15512 SPR Design"
# Short marker shown in the sidebar (keep this terse - just enough to confirm
# which build is running). Bump VERSION and set BUILD_DATE on every release;
# put the actual change description in BUILD below instead, which is kept
# for internal/git history and is not displayed in the UI.
VERSION = "1.1.0"
BUILD_DATE = "2026-08-14"
# Full build history - internal reference only (not shown in the UI; see
# VERSION / BUILD_DATE above for the sidebar marker).
BUILD = "2026-08-14c · Analysis runs now survive navigation: every Run button "
"used to call run_configuration() inline on Streamlit's main script thread, "
"and Streamlit cancels whatever script execution is in flight on ANY click "
"(a prior thread-based background attempt, ui.run_cancellable_poll, was "
"already documented as unsafe for OpenSees specifically - the solver holds "
"process-global C-extension state, so a worker thread starves/corrupts under "
"the constant rerun-polling). Fixed by running the analysis as a genuinely "
"separate OS process: rack15512.background_run.start_run() launches "
"`python -m rack15512._bg_worker` (a plain subprocess, not "
"multiprocessing.Process - spawn's child bootstrap replays the parent's "
"__main__, which under real Streamlit IS app_streamlit.py itself with no "
"__main__ guard, so it would re-execute the whole app script and crash); "
"progress/completion are written to a `_run_status.json` file inside the "
"configuration's own directory (atomic temp-file + os.replace) and polled by "
"ui.run_in_background(), so watching a run survives navigating away, a full "
"page refresh, or even a different browser session opening the same "
"configuration. Cancel is a small on-disk flag file for the same reason. "
"Verified live: started a run, immediately clicked to a different page, and "
"confirmed it finished and saved results anyway. Also: on selecting a beam "
"level's load in Configuration, the beam section now auto-populates from a "
"closed-form simply-supported UDL bending check (rack15512.presize."
"suggest_beams/beam_bending_utilisation, major-axis Welz per the app's "
"gravity-bending convention) at a 1.2 safety factor, driven by that level's "
"load and the bay span - mirrors the existing upright suggester's ranking "
"logic but applies automatically (no Apply click) by reading the load "
"widget before the beam selectbox is instantiated, so no rerun is needed; a "
"manual beam override survives unrelated edits (gap, etc.) since the "
"suggestion only re-fires when the load or span actually changes, and it's "
"seeded from the saved value so opening an existing configuration never "
"silently overrides a prior deliberate choice. Previous: 2026-08-14 · "
"Sign-in + role-based access ahead of internal deployment: rack15512.auth (UserStore, PBKDF2-HMAC hashing, no external auth dependency) gates the whole app behind a login screen - nothing renders until st.session_state['user'] is set. Two roles: admin sees Section masters (library management) + the new User Access page (add/remove users, change role, reset password - can't demote/delete the last admin or delete yourself) + the full projects workflow; a plain user sees the projects dashboard only, but can still SELECT an existing master when building a configuration (only master-library MANAGEMENT is admin-gated). First boot seeds one admin from ADMIN_USERNAME/ADMIN_PASSWORD env vars (or a generated one-time password printed to the server log). Sidebar now shows the signed-in user's name + role + a Log out button. No persistent login cookie (session-only) - a manual page refresh requires signing in again, a deliberate simplicity/dependency tradeoff for a 2-3 person internal tool. Verified end-to-end with a live headless-browser run: wrong password rejected, admin sees the admin nav and can add/demote/delete users, a newly-added plain user sees neither Section masters nor User access. Previous: 2026-08-10b · Utilisation-targeted load chart model_util_point() now CLIMBS level count to maximise total frame capacity (n_levels x load/level) instead of settling wherever the seed landed: some governing criteria (e.g. beam DEFLECTION) barely depend on level count, so capacity keeps rising with added levels until BUCKLING/STRESS/ALPHA_CR (which do grow with stacked height) cap it - the climb picks the peak, bounded by new min_levels/max_levels and a load-per-level floor_kg/cap_kg range (all overridable; alpha_cr/BUCKLING/STRESS remain ULS-only, DEFLECTION is maxed over every SLS imperfection-direction sub-case). n_bays is also overridable per run (module stays 'single' - never back-to-back). A cap-load-first, then previous-level-reuse fast path keeps the per-point FEA cost bounded despite the wider search. Previous: 2026-08-10 · Utilisation-targeted load chart now enforces FOUR governing criteria together (alpha_cr >= 1.8 sway stability, upright BUCKLING <= 0.99, beam DEFLECTION <= min(span/200, 15 mm net, SLS1), STRESS <= 0.99 over ALL members not just the upright): generate_util_based()/model_util_point() tune load-per-level and level count so the max of these four utilisations lands in the 0.97-0.99 band, xlsx gains a deflection_util column and the governs column now reports STRESS/BUCKLING/DEFLECTION/ALPHA_CR. Previous: 2026-07-13d · Upright STIFFENER now MONOLITHIC by default (SPR): the industry assumption - the reinforced upright segments (up to the reinforce height) carry a composite EQUIVALENT SECTION on the single upright member line: A and A_eff summed, down-aisle Iz summed, cross-aisle Iy by the PARALLEL-AXIS theorem about the combined centroid (centroid gap = master mount_offset or the config offset), section moduli from the true extreme fibres, W_eff = composite modulus x the upright's own Weff/Wel local-buckling knockdown, type-1 closing profiles keep the closed-cell torsion credit (Bredt It, small Iw, y0=0), design fy = min(upright, stiffener). No extra members, links or supports - one member line, exactly how RSTAB/industry models it (the previous partial-composite model under-delivered vs that assumption). The bolted separate model remains as stiffener_modelling=separate (offset member + bolt-shear interface links); new form selector. Verified: monolithic governing zone buckling utilisation <= separate. Previous: 2C stitching convention confirmed and recorded: back-to-back is the default assembly (not boxed), STITCH-BOLTED every 500 mm with one vertical bolt row at 50 mm pitch whose count follows the beam height (stitch_bolt_count: 150 -> 3, 200 -> 4, 300 -> 6 bolts; never fewer than 2), rarely welded - so the conservative OPEN torsion constant stands (a continuously welded box can be entered in the master with its closed J). Each generated 2C carries the convention in its description plus an EN 1993-1-1 6.4 note when the 500 mm stitch spacing exceeds 15 i_min of one channel (treat minor-axis compression as built-up); major-axis Iz = 2x is exact regardless of stitching since the equal channels share the neutral axis. Previous: Mezzanine SECTION FAMILIES: on-the-fly parametric sections by CODE (master-library names always win) - SHS{h}x{t} / RHS{h}x{b}x{t} columns (thin-walled midline, closed Bredt torsion), 1C{h}x{b}x{lip}x{t} lipped channels with optional r{radius} corner reduction per EN 1993-1-3 5.1(3), 2C coupled channels (back-to-back default, suffix B = boxed toe-to-toe; MAJOR axis Iz doubles exactly, Iy by parallel axis, conservative open torsion for stitch-bolted assemblies) and 2x2C twin assemblies; all beam codes keep Iz = MAJOR = gravity bending so stress/deflection/buckling check the strong axis. 1C FLOOR PANELS laid flat: mz_panel_section adds the panel self-weight (A x gamma / covered web width) to the floor dead load and models one representative pin-ended panel strip per floor ROTATED so gravity bending is about the MINOR axis (vecxz), stress+deflection checked like any beam (verified: strip My >> Mz). Form: section-code inputs for column / primary / secondary / joist / panel. Previous: NEW SYSTEM TYPE: Structural Mezzanine (rack15512/mezzanine.py, system_type mezzanine) alongside Selective and Drive-in. Column grid (bays x/y, bay sizes, 1-6 floors at a storey height) framed in up to three layers: continuous COLUMNS (buckling-checked per storey via checks.buckling_sets=[columns], set labels Column A1...), PRIMARY beams column-to-column along X or Y with moment / pinned / semi-rigid (k) column connections, pin-ended SECONDARY beams at a chosen spacing (also on the column lines as ties), and an optional pin-ended JOIST layer between the secondaries. FLOORING catalogue (chequered plate 3/4 mm, chipboard, plywood, grating, composite deck+concrete, custom) + extra dead + live load [kN/m2] applied as tributary UDLs on the topmost layer - totals verified exact (q x area); member self-weight from each section. Stability: vertical X-brace pairs in the outer bays of the perimeter lines (braced bays per corner) or, with bracing off, an automatic moment frame; pinned or fixed bases. ULS (gamma_G dead + gamma_Q live, 2nd order) + SLS combinations, EHF sway imperfections in both directions. New form family Structural mezzanine with the full grid / framing / flooring / connection / bracing inputs; deflection checks run on all beam layers (primary-beam deflection is per segment between secondary landings - see the module docstring), beams assumed laterally restrained by the decking. Previous highlights: SAP2000 import/export validated 1:1 against SAP 26 (exact table schemas, General sections with the full property set, base springs, connector partial fixity, EHF imperfection patterns, linear BUCKLING case; forces/deflections match SAP to 0.1-2 percent); RSTAB results comparison in-app (unit-aware reader, tolerance classification, per-member N/My/Mz, station-concurrent buckling+stress per upright, SLS beam deflection); RSTAB 8 / STAAD / SAP2000 solver exports; axial-dependent base stiffness; EN 15512 checks with concurrent-station buckling and torsional lengths from all twist restraints. Full history: git log on the app repository."

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

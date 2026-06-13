# SPR Design Tool — Instruction Sheet

**Selective Pallet Racking (SPR) structural design per EN 15512** —
3D second-order analysis (OpenSees engine) with semi-rigid connections,
for **single-deep modules** or **back-to-back modules** within a row.
The bundled reference example (`examples/SPR_CHECK_Data.xlsx`) is a
back-to-back module in **non-seismic** condition, cross-validated against
RSTAB/RFEM results (member forces agree to ~0.5% median, see
`out_rfem/validation.md`).

Units everywhere: **N, mm, MPa**. Axes: **X = down-aisle, Y = cross-aisle
(CA), Z = up**.

---

## 1. Installation on a local desktop

Requirements: **Python 3.9–3.12 (3.11 recommended)** on Windows or Linux
(OpenSeesPy ships pre-built wheels for both; macOS support varies).

```bash
git clone https://github.com/nuumaan-rnr/codespaces-blank.git
cd codespaces-blank
git checkout claude/storage-rack-fea-en15512-1fr70w

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux:
source .venv/bin/activate

pip install -r requirements.txt        # openseespy, numpy, matplotlib, openpyxl
pip install streamlit                  # for the UI
```

Linux only — OpenSeesPy needs the system solver libraries:

```bash
sudo apt-get install libblas3 liblapack3
```

Verify:

```bash
python -c "import openseespy.opensees as o; o.model('basic','-ndm',3,'-ndf',6); print('engine OK')"
python -m pytest tests/                # full validation suite (~4 min)
```

---

## 2. Running the tool

### Interactive UI (dashboard)

```bash
streamlit run app_streamlit.py         # opens http://localhost:8501
```

The app opens on a **Dashboard**: a left menu (Dashboard · Section masters)
with the saved **projects** listed on the right. From there:

- **Create new project** — enter name/client/location/engineer and a first
  system, then add configurations.
- **Open** a project — see its systems and configurations with their
  pass/fail verdict; **Open** a configuration to view its 3D model and
  cross-aisle frame elevation plus saved results (verdict, governing
  check, per-check utilisation, plots, full report), or **Run / re-run**
  it; **Edit** to reopen the configuration form pre-filled.
- **New configuration** (in a system) — the full form: geometry, per-level
  beams, cross-aisle bracing including the **first-diagonal side
  (outer/inner)**, connections, base/footplate, loads with **toggles to
  include/exclude placement and accidental loads**, imperfection and
  factors. **Preview model**, **Save**, or **Save & run** (a post-run
  popup lists the load cases, load combinations, per-case convergence and
  max member-stress utilisation).

After a run, the configuration's **Results** tab gives an **interactive 3D
viewer** (Plotly): hover a member for its forces (N, My, Mz, V) or a ◆
support for its reaction components (the irregular node numbers are shown
on hover), a **deformation-scale slider**, and an **envelope / case
selector** — pick the **ULS** or **SLS** envelope (the worst over all
combinations of that kind), a per-combination envelope, or an individual
case. Moments are drawn on the tension side and the deformed shape shows
the true member curvature.
- **Section masters** page — import a master once, then edit or delete its
  sections.

### Command line

```bash
python -m rack15512 example --master examples/Master.xlsx --outdir out
python -m rack15512 run my_model.json --outdir out
python -m rack15512 sections --master examples/Master.xlsx --role upright
python -m rack15512 rfem SPR_CHECK_Data.xlsx --master Master.xlsx --compare
```

### Section masters (in-app database)

Masters live **inside the system**, not in the spreadsheet: import an Excel
master once into the store, then add / edit / delete sections in place. The
data is held as JSON under a `masters/` directory; configurations reference
a stored master by id, so a master update flows to everything that uses it.

```bash
python -m rack15512 master import examples/Master.xlsx --name "Standard SPR"
python -m rack15512 master list
python -m rack15512 master show standard-spr --role upright
python -m rack15512 master set standard-spr UP0016 fy 355   # edit a field
python -m rack15512 master delete-section standard-spr UP0026
python -m rack15512 master delete standard-spr               # remove master
```

In the Streamlit app the **Section masters** tab imports, views, edits and
deletes sections; the sidebar then offers any stored master as the source
(no re-upload). Build configurations against `--master-id` so they always
use the latest stored data:

```bash
python -m rack15512 project add-config <project> <system> "Cfg" \
       --master-id standard-spr
```

### Projects (record systems & configurations)

Work is organised as **Project → System → Configuration**: a project (the
job) holds one or more systems (e.g. each aisle/rack run), and each system
holds many configurations (parameter sets). Everything is stored under a
`projects/` directory; each configuration keeps its RackConfig, a reference
to the section master, and — once run — a result summary plus the report
and plots.

```bash
python -m rack15512 project new "Acme DC Phase 2" --client "Acme" \
       --location "Mumbai" --engineer "R. Nair"
python -m rack15512 project add-system acme-dc-phase-2 "Aisle 1"
python -m rack15512 project add-config acme-dc-phase-2 aisle-1 \
       "UP0016 D-frame" --master examples/Master.xlsx
python -m rack15512 project run acme-dc-phase-2 aisle-1 up0016-d-frame
python -m rack15512 project show acme-dc-phase-2      # tree + verdicts
python -m rack15512 project list                      # all projects
```

Directory layout:

```
projects/
  acme-dc-phase-2/
    project.json                 # project + systems + configurations + results
    aisle-1/
      up0016-d-frame/
        config.json              # the RackConfig parameters
        model.json, report.md    # written after a run
        model.png, utilization.png, ...
```

In the Streamlit app, build a configuration in the sidebar and press
**Save configuration to project**; the **Projects** tab lists every
project/system/configuration with its recorded verdict and lets you re-run
any configuration. (The `projects/` directory is your working data and is
git-ignored.)

### Python script

```python
from rack15512 import (LevelSpec, RackConfig, build_rack, load_master,
                       run_all, run_checks, write_report)

cfg = RackConfig(
    name="SPR back-to-back module (non-seismic)",
    module="back-to-back", n_bays=3, bay_width=2700, depth=1000,
    b2b_gap=250, frame_height=6500,
    bracing_type="D", bracing_start=150, bracing_pitch=600,
    master=load_master("examples/Master.xlsx"),
    upright_section="UP0016", brace_section="C 36X21X1.5",
    base_stiffness="auto",
    levels=[LevelSpec(gap=1500, beam_section="RHS 112x50x2.0",
                      pallet_load=20000)] * 4)
model  = build_rack(cfg)        # creates nodes/members/loads/combinations
cases  = run_all(model)         # 2nd-order OpenSees analysis, all combos
checks = run_checks(model, cases)
print(write_report(model, cases, checks))
```

---

## 3. UI inputs (sidebar)

```
┌─ Section master ───────────────────────────────┐
│ Master file (.xlsx/.csv/.json)  [Master.xlsx]  │
│ Upright       [UP0016          ▼]              │
│ Bracing       [C 36X21X1.5     ▼]              │
├─ Geometry ─────────────────────────────────────┤
│ Module type      (•) Back-to-back  ( ) Single  │
│ Bays (down-aisle)            [ 3      ]        │
│ Beam span / bay width [mm]   [ 2700   ]        │
│ Frame depth [mm]             [ 1000   ]        │
│ Back-to-back gap [mm]        [ 250    ]        │
│ Number of beam levels (1-20) [ 4      ]        │
│   L1: gap [1500] beam [RHS 112x50x2.0] [20 kN] │
│   L2: gap [1500] beam [RHS 112x50x2.0] [20 kN] │
│   L3: gap [1500] beam [RHS 100x50x1.6] [15 kN] │
│   L4: gap [1500] beam [RHS 100x50x1.6] [15 kN] │
│ Frame height [mm]            [ 6500   ]        │
├─ Cross-aisle bracing ──────────────────────────┤
│ Type            (•) D (zigzag)  ( ) X (crossed)│
│ Different pattern below level 1   [same     ▼] │
│ First horizontal above floor [mm]  [ 150 ]     │
│ Diagonal pitch [mm]                [ 600 ]     │
├─ Upright splice (auto if H > 11 m) ────────────┤
│ [x] Add splice + connection check              │
│ Splice elevation [mm]            [ 6000 ]      │
│ Bolt [M12 ▼] grade [4.6 ▼]                     │
│ rows x cols / side  [2] x [1]                  │
│ e1 [30]  e2 [20]  p1 [60]  p2 [0]              │
│ Sleeve thickness [mm] (0 = wall)  [ 0 ]        │
├─ Steel & connections ──────────────────────────┤
│ Default fy [MPa]                   [ 355  ]    │
│ (connector k / M_Rd / phi_l auto from beam     │
│  master; fields below = fallback)              │
│ Fallback connector stiffness [kNm/rad] [100 ]  │
│ Fallback connector M_Rd [kNm]          [ 2.5]  │
│ Fallback connector looseness [mrad]    [ 0  ]  │
│ [x] Base stiffness from master BASE_STIFFNESS  │
├─ Bracing connection & footplate ───────────────┤
│ Bracing area factor in analysis    [ 0.15 ]    │
│ Connection bolt size  [M12 ▼]  grade [4.6 ▼]   │
│ Bolts per brace end                [ 1    ]    │
│ Floor concrete f_ck [MPa]          [ 25   ]    │
│ Base plate fy [MPa]                [ 250  ]    │
│ Actual base plate b x d x t [mm]   [150|130|6] │
├─ Loads ────────────────────────────────────────┤
│ (pallet loads are per level, see beam levels)  │
│ Beam dead load [N/mm]              [ 0.05 ]    │
│ Placement load [kN]                [ 0.5  ]    │
│ Accidental load X / Y [kN]   [1.25] / [2.5]    │
│ Accidental load height [mm]        [ 400  ]    │
├─ Imperfection & factors ───────────────────────┤
│ Out-of-plumb phi_s (1/x)           [ 350  ]    │
│ gamma_G [1.3]   gamma_Q [1.4]                  │
│ Analysis  [Second order (EN 15512) ▼]          │
│           ▶ Run analysis ◀                     │
└────────────────────────────────────────────────┘
```

### Input reference

| Input | Unit | Meaning |
|---|---|---|
| Master file | – | Your section master: all uprights/beams/braces with full properties + per-upright BASE_STIFFNESS tables. Sections are picked by name per role. |
| Module type | – | `Single` = one rack (2 upright lines); `Back-to-back` = two racks tied with row spacers at every beam level (4 upright lines). |
| Bays | – | Number of bays in the down-aisle direction (uprights = bays + 1 frame lines). |
| Beam span / bay width | mm | Upright centreline spacing = pallet-beam span. |
| Frame depth | mm | Front-to-rear upright spacing of one rack frame. |
| Back-to-back gap | mm | Clear gap between the two racks of a back-to-back module. |
| Beam levels (1–20) | – | **Per level**: the beam gap (level-to-level spacing), the beam section from the master, and the pallet load — every level can differ. The model scales to 20 levels. |
| Frame height | mm | Total upright length (≥ top beam level). |
| Bracing type | – | CA frame pattern: `D` zigzag or `X` crossed pairs. |
| First diagonal connects to | – | `outer` (aisle side, default) or `inner` upright, for the first diagonal just above the bottom horizontal; both frames of a back-to-back module are mirrored accordingly. Exposed as a radio in the configuration form. |
| First horizontal | mm | Height of the bottom horizontal strut (default 150). |
| Diagonal pitch | mm | Height of each diagonal panel (default 600, customizable). Diagonals run up to the last position that fits; one closing horizontal there; no intermediate horizontals. |
| fy | MPa | Default yield strength; sections from an .xlsx master carry their own fy. |
| Connector stiffness / M_Rd / looseness | kNm/rad, kNm, mrad | Taken **automatically from BEAM_MASTER per selected beam** (Annex A test data travels with the beam type, level by level). The UI fields are fallbacks for beams without connector columns. Looseness feeds the sway imperfection (largest value in use). |
| Base stiffness | kNm/rad or auto | Floor connection; `auto` interpolates the master's k_b(N) table at the estimated upright load. |
| Pallet load | kN | Total unit load per bay per level **per module** (split between front/rear beam as UDL). |
| Beam dead load | N/mm | Self weight of each beam. |
| Placement load | kN | EN 15512 horizontal placement load at the top level (applied in X and Y combos). |
| Accidental load X / Y / height | kN, mm | EN 15512 accidental impact on the corner upright (defaults 1.25 kN down-aisle, 2.5 kN cross-aisle at 400 mm). Combined as ULS-accX/ULS-accY at **gamma = 1.0** with dead + pallet loads (accidental design situation). |
| Include placement / accidental loads | – | Toggles to drop the placement and/or accidental load cases and their combinations entirely (leaving only the gravity ULS1/SLS1 pair when both are off). |
| phi_s | 1/x | Erection out-of-plumb; sway imperfection phi = sqrt(0.5+1/n_cols)·(2·phi_s+phi_l) applied as equivalent horizontal forces in ±X and ±Y. |
| gamma_G / gamma_Q | – | Partial factors → ULS 1.3G+1.4Q, SLS 1.0 (EN 15512 defaults, editable). |
| Analysis | – | Second order (P-Delta, EN 15512 requirement) or first order for comparison. |
| Bracing area factor | – | Connection-flexibility modification: only this fraction of the brace area (default **15%**) acts in the **analysis stiffness**; all strength checks use the full section. |
| Bolt size / grade / count | – | Bracing end-connection bolts for the BRACE_BOLT check (M8–M16; grades 4.6–10.9). |
| f_ck / plate fy | MPa | Floor concrete grade (f_jd = 0.85·f_ck/1.5 unless overridden) and base-plate steel for the BASEPLATE check. |
| Actual base plate b×d×t | mm | Leave at 0 to use the **standard footplate for the upright depth** (90 mm upright → 100×145×4, 120 mm → 100×176×4); enter values to verify a specific plate. The report always also states the minimum required size/thickness. |

---

## 4. Outputs

UI tabs / CLI output directory:

| Output | Content |
|---|---|
| **Model** tab / `model.png`, `frame_elevation.png` | 3D geometry plot, CA frame elevation (compare with the frame drawing), table of the selected sections with the properties actually sent to the solver, model JSON download. |
| **Results** tab / `deformed_*.png`, `moment_*.png`, `axial_*.png` | Per combination: sway X/Y, estimated alpha_cr, deformed shape, member force diagrams (Mz, My, N, Vy, Vz, T), support reactions. |
| **EN 15512 checks** tab / `utilization.png` | PASS/FAIL verdict with governing member, colour-coded 3D utilization plot, full sortable check table. |
| **Report** tab / `report.md` | **Load-combinations table with the factors of every combination** (e.g. ULS1 = 1.3 x dead + 1.4 x pallets, imp ±x/±y; ULS4 = 1.0 x dead + 1.0 x pallets + 1.0 x accidental_x), analysis-case summary (sway, alpha_cr), **utilization-by-level table**, then all checks grouped by type, worst first. |

### Checks performed (per EN 15512, as configured for SPR)

| Check | Applies to | Rule |
|---|---|---|
| STRESS | all members (ULS) | \|N\|/(A_eff·fy/γM0) + \|My\|/(Wy_eff·fy/γM0) + \|Mz\|/(Wz_eff·fy/γM0) ≤ 1 at every station — covers the maximum-moment check of the beams. |
| BUCKLING | **uprights only** (ULS) | Flexural buckling about **both axes plus flexural-torsional** (χ_FT from IT, Iw, y0 when present in the master — it often governs), χ per EN 1993-1-1 §6.3.1 / EN 15512 9.7.5. Buckling lengths assigned automatically **from the model, per level band**: **major axis = the beam gap of that level**; **minor axis (CA) = the largest unsupported length between the bracing connection points on that upright within that band** — e.g. X bracing up to level 1 gives Lcr = pitch there and the D zone above gives 2×pitch. Torsional length = β_T·(bracing spacing), β_T = 0.7. χ_min of the three governs the N + My + Mz interaction (EN 15512 9.7.6.3 simplified rule). |
| CONNECTOR | beam end connectors (ULS) | EN 15512 9.5.4 combined bending + shear: MSd/MRd + (VSd − MRd/a)/VRd ≤ 1 when the connector shear resistance VRd and arm a are in the beam master; otherwise \|M_Ed\| ≤ M_Rd. |
| BRACE_BOLT | bracing end connections (ULS) | Brace axial force ≤ n_bolts × **min( bolt shear, bearing on the brace, bearing on the upright )** per EN 1993-1-8: Fb,Rd = k1·αb·fu·d·t/γM2 with αb = min(e1/3d0, fub/fu, 1), k1 = min(2.8·e2/d0−1.7, 2.5) — **e1/e2/t/fu of both plies come from the masters** (upright sheet columns e1/e2/t-wall; bracing sheet rows end-dist e1/e2, Thk, Fu). The governing component is named in the report. |
| BRACE_BUCKLING | bracing members (ULS) | Compression buckling of the frame-bracing members (EN 15512 10.4): flexural about both axes **plus flexural-torsional** (using IT, Iw, y0 from the bracing master), buckling curve `c`, full section area (the 15% factor is analysis-stiffness only). |
| BASEPLATE | footplate / contact pressure (ULS) | **EN 15512 9.9 / 9.10.1**: floor strength **fj = 2.5·f_ck/γc** (≈ 41.7 MPa for C25, not the 0.85·f_ck of EN 1992); the upright compression spreads under the wall over a strip of half-width e = t·√(fy/(3·fj)) (capped at the plate overhang), giving the contact area Abas; check N_Sd ≤ fj·Abas. Standard 3–4 mm footplates verify. The base moment is **not** included here — it is the separate BASE_RESTRAINT check. |
| BASE_RESTRAINT | upright base (ULS) | EN 15512 10.5.1 partial restraint: MSd,y / MRd(NSd) ≤ 1, with the load-dependent base moment resistance MRd(NSd) interpolated from the floor-connection test table (BASE_STIFFNESS sheet). |
| ANCHORAGE | upright base (ULS) | EN 15512 7.6 / 9.10.4: net base uplift vs the anchor tension capacity; the minimum 3 kN tension + 5 kN shear per connection is flagged. |
| SPLICE | upright splices (ULS) | When the frame is taller than 11 m a splice is added (auto at H/2, or at the entered elevation). The bolt group per side (user inputs: bolt size, grade, rows×cols, e1, e2, p1, p2, sleeve t) is verified per EN 1993-1-8 with the elastic bolt-group method for the concurrent N, V and M at the splice elevation; per-bolt resistance = min(shear, bearing on the lesser of the upright wall / sleeve thickness), end- and inner-bolt bearing factors from e1/p1 and e2/p2. |
| DEFLECTION | pallet beams (SLS) | transverse deflection ≤ span/200 (configurable). |
| SWAY | frame (SLS) | max sway in X and in Y ≤ H/200 (configurable). |
| ALPHA_CR | frame (info) | sway-sensitivity report from the 1st/2nd-order amplification; second-order effects are already inside the results. |

Beams are **not** buckling-checked (stress / maximum moments / deflection
only); bracing is checked for stress.

### Utilization by level

`report.md` contains a per-level table — beams and connectors **at** each
level, uprights and bracing of the storey **below** it:

```
| level | elevation [mm] | uprights              | beams                | connectors            | bracing |
|   1   |      1500      | 0.706 PASS (BUCKLING) | 0.752 PASS (STRESS)  | 0.710 PASS (CONNECTOR)| 0.045 … |
|   2   |      3000      | 0.574 PASS (BUCKLING) | 0.745 PASS (STRESS)  | 0.676 PASS (CONNECTOR)| 0.026 … |
```

---

## 5. Runtime (measured)

Back-to-back module, 3 bays × 4 levels (272 nodes, 416 members,
5 combinations → 14 second-order cases incl. ±X/±Y imperfections, each
with a first-order companion for alpha_cr):

| Step | Time |
|---|---|
| Create model from inputs | < 0.1 s |
| Run analysis (all combinations, 2nd order) | ~ 170 s (~12 s per case) |
| Read results + EN 15512 checks | < 1 s |
| Report + plots | ~ 5 s |
| **Total** | **~ 3 minutes** |

A single module is roughly half that; first-order runs take a few seconds
total. The imported RSTAB reference model (528 members, 10 combinations)
completes with full validation in ~13 minutes. Times scale roughly
linearly with members × combinations × imperfection directions.

---

## 6. Importing an existing RSTAB/RFEM model

```bash
python -m rack15512 rfem SPR_CHECK_Data.xlsx --master Master.xlsx --compare --outdir out_rfem
```

Converts the .xlsx data export (axes, units, hinge/axis conventions,
loads, imperfections, combinations) and re-analyses it; `--compare`
writes `validation.md` against the export's own result sheets. **Pass
`--master`**: RSTAB does not export the nonlinear load-dependent floor
springs — they are restored from the BASE_STIFFNESS table (without them a
pinned-base model can correctly show sway instability at ULS).

## 7. Troubleshooting

- *"second-order analysis did not converge"* in a check row — the
  structure is at/near elastic sway instability under that combination
  (alpha_cr ≈ 1). Check base stiffness (use `auto` with your master) and
  connector stiffness before increasing sections.
- OpenSeesPy import errors on Linux → install `libblas3 liblapack3`;
  on any OS → use Python 3.11 in a fresh venv.
- Section not found → `python -m rack15512 sections --master ...` lists
  the master contents; names must match exactly.

---
*This software is an engineering aid. Verify all defaults (factors,
imperfections, limits) against the EN 15512 edition and national
provisions applicable to your project; section and connector properties
must come from tests per the standard. The current scope is non-seismic
design (EN 16681 seismic checks are not implemented).*

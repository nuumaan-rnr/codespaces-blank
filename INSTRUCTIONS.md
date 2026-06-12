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

### Interactive UI

```bash
streamlit run app_streamlit.py         # opens http://localhost:8501
```

### Command line

```bash
python -m rack15512 example --master examples/Master.xlsx --outdir out
python -m rack15512 run my_model.json --outdir out
python -m rack15512 sections --master examples/Master.xlsx --role upright
python -m rack15512 rfem SPR_CHECK_Data.xlsx --master Master.xlsx --compare
```

### Python script

```python
from rack15512 import RackConfig, build_rack, load_master, run_all, run_checks, write_report

cfg = RackConfig(
    name="SPR back-to-back module (non-seismic)",
    module="back-to-back", n_bays=3, bay_width=2700, depth=1000,
    b2b_gap=250, beam_levels=[1500, 3000, 4500, 6000], frame_height=6500,
    bracing_type="D", bracing_start=150, bracing_pitch=600,
    master=load_master("examples/Master.xlsx"),
    upright_section="UP0016", beam_section="RHS 112x50x2.0",
    brace_section="C 36X21X1.5", base_stiffness="auto",
    pallet_load_per_level=20000)
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
│ Pallet beam   [RHS 112x50x2.0  ▼]              │
│ Bracing       [C 36X21X1.5     ▼]              │
├─ Geometry ─────────────────────────────────────┤
│ Module type      (•) Back-to-back  ( ) Single  │
│ Bays (down-aisle)            [ 3      ]        │
│ Beam span / bay width [mm]   [ 2700   ]        │
│ Frame depth [mm]             [ 1000   ]        │
│ Back-to-back gap [mm]        [ 250    ]        │
│ Number of beam levels        [ 4      ]        │
│   Level 1 elevation [mm]     [ 1500   ]        │
│   Level 2 elevation [mm]     [ 3000   ]        │
│   Level 3 elevation [mm]     [ 4500   ]        │
│   Level 4 elevation [mm]     [ 6000   ]        │
│ Frame height [mm]            [ 6500   ]        │
├─ Cross-aisle bracing ──────────────────────────┤
│ Type            (•) D (zigzag)  ( ) X (crossed)│
│ First horizontal above floor [mm]  [ 150 ]     │
│ Diagonal pitch [mm]                [ 600 ]     │
├─ Steel & connections ──────────────────────────┤
│ Default fy [MPa]                   [ 355  ]    │
│ Connector stiffness [kNm/rad]      [ 65.7 ]    │
│ Connector M_Rd [kNm]               [ 2.5  ]    │
│ Connector looseness phi_l [mrad]   [ 0    ]    │
│ [x] Base stiffness from master BASE_STIFFNESS  │
├─ Loads ────────────────────────────────────────┤
│ Pallet load per bay per level [kN] [ 20   ]    │
│ Beam dead load [N/mm]              [ 0.05 ]    │
│ Placement load [kN]                [ 0.5  ]    │
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
| Beam levels | mm | Elevation of **each** beam level individually (level-to-level beam gap is taken from these). |
| Frame height | mm | Total upright length (≥ top beam level). |
| Bracing type | – | CA frame pattern: `D` zigzag or `X` crossed pairs. |
| First horizontal | mm | Height of the bottom horizontal strut (default 150). |
| Diagonal pitch | mm | Height of each diagonal panel (default 600, customizable). Diagonals run up to the last position that fits; one closing horizontal there; no intermediate horizontals. |
| fy | MPa | Default yield strength; sections from an .xlsx master carry their own fy. |
| Connector stiffness / M_Rd / looseness | kNm/rad, kNm, mrad | Beam-to-upright connector from EN 15512 Annex A tests. Looseness feeds the sway imperfection. |
| Base stiffness | kNm/rad or auto | Floor connection; `auto` interpolates the master's k_b(N) table at the estimated upright load. |
| Pallet load | kN | Total unit load per bay per level **per module** (split between front/rear beam as UDL). |
| Beam dead load | N/mm | Self weight of each beam. |
| Placement load | kN | EN 15512 horizontal placement load at the top level (applied in X and Y combos). |
| phi_s | 1/x | Erection out-of-plumb; sway imperfection phi = sqrt(0.5+1/n_cols)·(2·phi_s+phi_l) applied as equivalent horizontal forces in ±X and ±Y. |
| gamma_G / gamma_Q | – | Partial factors → ULS 1.3G+1.4Q, SLS 1.0 (EN 15512 defaults, editable). |
| Analysis | – | Second order (P-Delta, EN 15512 requirement) or first order for comparison. |

---

## 4. Outputs

UI tabs / CLI output directory:

| Output | Content |
|---|---|
| **Model** tab / `model.png`, `frame_elevation.png` | 3D geometry plot, CA frame elevation (compare with the frame drawing), table of the selected sections with the properties actually sent to the solver, model JSON download. |
| **Results** tab / `deformed_*.png`, `moment_*.png`, `axial_*.png` | Per combination: sway X/Y, estimated alpha_cr, deformed shape, member force diagrams (Mz, My, N, Vy, Vz, T), support reactions. |
| **EN 15512 checks** tab / `utilization.png` | PASS/FAIL verdict with governing member, colour-coded 3D utilization plot, full sortable check table. |
| **Report** tab / `report.md` | Analysis-case summary (sway, alpha_cr), **utilization-by-level table**, then all checks grouped by type, worst first. |

### Checks performed (per EN 15512, as configured for SPR)

| Check | Applies to | Rule |
|---|---|---|
| STRESS | all members (ULS) | \|N\|/(A_eff·fy/γM0) + \|My\|/(Wy_eff·fy/γM0) + \|Mz\|/(Wz_eff·fy/γM0) ≤ 1 at every station — covers the maximum-moment check of the beams. |
| BUCKLING | **uprights only** (ULS) | Flexural buckling about **both axes**, χ per EN 1993-1-1 §6.3.1. Buckling lengths assigned automatically: **major axis = the beam gap of that level band** (floor→L1, L1→L2, …); **minor axis (CA) = largest unsupported length between the bracing connection points on that upright** (for a D-pattern the diagonals meet each upright every other pitch → 2×pitch). χ_min of the two governs the interaction with the moments. |
| CONNECTOR | beam end connectors (ULS) | \|M_Ed\| ≤ M_Rd from the connector test. |
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

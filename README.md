# rack15512 — 3D storage-rack analysis & EN 15512 design checks

Structural analysis app for steel storage racks (adjustable pallet racking)
per **EN 15512**: full **3D** second-order elastic global analysis with
**semi-rigid connections**, global sway imperfections in both rack
directions, a **section master library**, and automated design checks
(stress, buckling about both axes, connector moment, deflection, sway).

Global axes: **X = down-aisle, Y = cross-aisle (depth), Z = up**.
Units everywhere: **N, mm, MPa (N/mm²), N·mm, rad**.

## Why OpenSees as the FEA engine

The engine is [OpenSees](https://opensees.berkeley.edu/) (via
[OpenSeesPy](https://openseespydoc.readthedocs.io/)). It natively covers
everything EN 15512 requires for rack global analysis, and is open source,
scriptable and battle-tested:

| EN 15512 requirement | OpenSees feature used |
|---|---|
| Semi-rigid beam-to-upright connectors (Annex A tests) | zero-length rotational springs about the member's local axes, with the tested stiffness |
| Semi-rigid floor connections | rotational spring supports (zero-length to fixed ground node), rocking about both horizontal axes |
| Second-order (P-Delta) global analysis | `PDelta` geometric transformation + incremental Newton–Raphson; members subdivided to capture P-little-delta |
| Truss bracing (cross-aisle frames, spine bracing) | `corotTruss` (geometrically nonlinear truss) |
| Sway imperfections | equivalent horizontal forces (EHF) or initial out-of-plumb geometry, in ±X and ±Y |
| Beam and truss members, arbitrary sections, steel grades | 3D elastic beam-column elements (A, Iy, Iz, J) with user properties |

## Section master library

Keep ONE master file with all your sections and their full properties,
tagged by **role** (`upright` / `beam` / `bracing` / …). Members are
assigned by section name and the library hands the complete, solver-ready
property set to the model — gross + effective areas and moduli, both
bending axes, torsion, and the EN 1993-1-1 buckling curve per axis.

### .xlsx master workbook

The native format is the engineering master workbook
(`examples/Master.xlsx`) with sheets, in cm/kN units as maintained:

- **UPRIGHT_MASTER** — Aeff, Iyy/Izz, Weff,y/Weff,z, fy, wall t per
  upright (workbook Iyy = major axis → model local z; upright torsion J is
  estimated as A·t²/3 since it is not tabulated)
- **BEAM_MASTER** — RHS h×b×t, major-axis I and Wel, fy, section M_Rd
  (minor axis, area and J are computed from the RHS geometry)
- **BRACING_MASTER** — C-channel area, Iyy/Izz, Zyy/Zzz, IT (St-Venant J),
  fy (transposed layout; duplicate names are suffixed `#2`)
- **BASE_STIFFNESS** — per upright, the EN 15512 load-dependent floor
  connection: N vs k_b vs M_Rd. With `base_stiffness="auto"` the builder
  interpolates k_b at the estimated ULS upright axial load.

Per-section fy values from the workbook are honoured automatically via
dedicated material entries.

```python
from rack15512 import load_master
mw = load_master("examples/Master.xlsx")
mw.library.names("upright")                # UP0002 ... UP0026
k, m_rd = mw.base_stiffness("UP0008", 45e3)  # floor spring at N = 45 kN
```

### CSV / JSON master

Canonical CSV header:

```
name, role, A, Iy, Iz, J, Wely, Welz,
A_eff, Wy_eff, Wz_eff, curve_y, curve_z, material, description
```

`A_eff/Wy_eff/Wz_eff` may be blank (gross values used); curves default to
`b`. If your master uses different column names, pass a mapping:

```python
from rack15512 import SectionLibrary
lib = SectionLibrary.from_csv("my_master.csv", mapping={
    "Profile": "name", "Type": "role", "Area": "A", "IYY": "Iy",
    "IZZ": "Iz", "Torsion": "J", "WY": "Wely", "WZ": "Welz"})
lib.names("upright")          # all uprights in the master
lib.get("UP-100x100x2.0")     # full CrossSection, ready for the solver
```

A bundled example master (`rack15512/data/sections_master.csv`, generic
demonstration values) ships with the package — replace it with your tested
section data.

**Axis convention for section properties** (member local axes):
horizontal members get local y ≈ vertical, so gravity bending of pallet
beams engages **Iz/Welz**; vertical uprights get local y = +X (down-aisle)
and local z = +Y, so down-aisle frame bending engages **Iz** and
cross-aisle bending **Iy**. Override per member with `vecxz` if your
section axes differ.

## What the app does

1. **Inputs**: nodes (x, y, z), members (beam/truss) with sections from the
   master, member sets, semi-rigid supports (any of the 6 DOFs fixed, free
   or a spring), hinges with rotational stiffness about each local axis
   (plus optional M_Rd and looseness), load cases, combinations, sway
   imperfections — via JSON file, Python API, or the Streamlit UI.
2. **Analysis**: every combination is assembled with its partial factors;
   ULS combinations get the EN 15512 sway imperfection applied in ±X and
   ±Y; a geometrically nonlinear (second-order) OpenSees analysis is run,
   plus a first-order companion to report the sway amplification and an
   estimate of the elastic critical load factor α_cr.
3. **Results**: 6-DOF displacements, reactions, member force stations
   (N, Vy, Vz, T, My, Mz) and chord deflections — viewable as 3D PNG plots
   or interactively in the UI.
4. **EN 15512 checks**:
   - **STRESS** — `|N|/(A_eff·fy/γM0) + |My|/(Wy_eff·fy/γM0) + |Mz|/(Wz_eff·fy/γM0) ≤ 1`
     at every station
   - **BUCKLING** — flexural buckling about both axes, χ from the
     EN 1993-1-1 §6.3.1 curves (a0…d per axis), configurable buckling
     lengths, with moment interaction
   - **CONNECTOR** — hinge end moments vs tested `M_Rd` (per axis)
   - **DEFLECTION** — pallet-beam deflection ≤ L/200 (SLS, configurable)
   - **SWAY** — frame sway in X and in Y ≤ H/200 (SLS, configurable)
   - **ALPHA_CR** — sway-sensitivity report (informative; second-order
     effects are already in the analysis)

## Install & run

```bash
pip install -r requirements.txt
# Linux: OpenSeesPy needs system BLAS/LAPACK:
#   sudo apt-get install libblas3 liblapack3

# demo: builds a 3-bay x 3-level x 2-line rack block (braced frames,
# beam pairs), runs it, writes report + plots
python -m rack15512 example --outdir out

# with your own master:
python -m rack15512 example --master my_master.csv --outdir out

# list a master
python -m rack15512 sections --master my_master.csv --role upright

# analyse your own model
python -m rack15512 run my_rack.json --outdir out
```

Outputs in `out/`: `report.md` (full check report), `model.png`,
`utilization.png` (color-coded 3D member utilizations), and deformed shape
/ moment / axial diagrams per analysis case. The CLI exits non-zero when a
check fails.

### Interactive app

```bash
pip install streamlit
streamlit run app_streamlit.py
```

Upload your section master, pick upright/beam/bracing sections by role,
set geometry, connections, loads, imperfections and factors; tabs show the
3D model, results (deformed shape, Mz/My/N/Vy/Vz/T diagrams, reactions),
checks and the downloadable report.

### Python API

```python
from rack15512 import (RackModel, Steel, SectionLibrary, Hinge, Support,
                       LoadCase, MemberLoad, Combination, Imperfection,
                       run_all, run_checks, write_report)

lib = SectionLibrary.from_csv("my_master.csv")
m = RackModel(name="my rack")               # units: N, mm, MPa
m.materials["steel"] = Steel("steel", fy=355.0)
lib.add_to_model(m, "UP-100x100x2.0", "BM-110x50x1.5")

m.add_node(1, 0, 0, 0); m.add_node(2, 0, 0, 2000)
m.add_member(1, 1, 2, "UP-100x100x2.0", member_set="uprights")
# semi-rigid floor connection (rocking springs about X and Y):
m.supports.append(Support(1, ux=True, uy=True, uz=True,
                          rx=5.0e8, ry=5.0e8, rz=False))
# beam-to-upright connector: spring about local z, tested M_Rd:
hinge = Hinge(rz=1.0e8, m_rd_z=2.5e6)
...
cases = run_all(m)                # 2nd-order OpenSees analysis, all combos
checks = run_checks(m, cases)     # EN 15512 verifications
print(write_report(m, cases, checks))
```

### Parametric rack builder

`rack15512.builder.build_rack(RackConfig(...))` generates a complete rack
block — uprights, beam pairs with connectors, braced cross-aisle frames,
loads, combinations and imperfections. Key inputs:

- **`beam_levels`** — each beam level elevation individually, e.g.
  `[1500, 3000, 4700, 6600]` (not forced to a uniform pitch)
- **`frame_height`** — upright length, independent of the top beam level
- **Cross-aisle bracing per the standard frame drawings**:
  `bracing_type="D"` (zigzag) or `"X"` (crossed pairs), a horizontal strut
  at `bracing_start` (default 150 mm) above the floor, truss diagonals in
  `bracing_pitch` panels (default 600 mm, customizable), no intermediate
  horizontals, and one closing horizontal at the last diagonal position
  that fits below the frame top
- **`master=load_master("Master.xlsx")`** + `base_stiffness="auto"` to
  pull section properties and the load-interpolated floor-connection
  stiffness straight from the workbook

```python
from rack15512 import RackConfig, build_rack, load_master
cfg = RackConfig(
    n_bays=3, bay_width=2700, depth=1000,
    beam_levels=[1500, 3000, 4500, 6000, 7500, 9000],
    frame_height=9898, bracing_type="D",
    bracing_start=150, bracing_pitch=600,
    master=load_master("examples/Master.xlsx"),
    upright_section="UP0022", beam_section="RHS 122x61x1.6",
    brace_section="C 34X34X2.0", base_stiffness="auto")
model = build_rack(cfg)
```

`viewer.plot_frame_elevation(model)` draws the Y-Z frame elevation for a
direct visual comparison with the CAD drawing. See
`examples/pallet_rack.json` for the generated input format.

## Model format notes

- **Supports**: each DOF (`ux, uy, uz, rx, ry, rz`) is `true` (fixed),
  `false` (free) or a number (spring stiffness).
- **Hinges**: per local rotation axis `rx/ry/rz`: `null` = continuous,
  `0` = released pin, number = spring stiffness [N·mm/rad]. The EN 15512
  Annex A connector stiffness goes on `rz` of horizontal beams.
- **Imperfection**: give `phi` directly, or `n_cols` (+ `phi_s`, `phi_l`)
  to compute `phi = sqrt(0.5 + 1/n_cols)·(2·phi_s + phi_l) ≥ phi_min`
  (EN 15512:2009-style; connector looseness already modelled in the hinges
  may be omitted). Methods: `EHF` or `geometry`; directions any of
  `+x, -x, +y, -y`.
- **Combinations**: explicit factors per load case. Builder defaults:
  ULS `1.3·G + 1.4·Q`, SLS `1.0·G + 1.0·Q`.

## RFEM import & cross-validation

Existing RFEM (Dlubal) models can be imported from their .xlsx data export
(`1.1 Nodes` ... `2.5 Load Combinations` sheets) and re-analysed here:

```bash
python -m rack15512 rfem SPR_CHECK_Data.xlsx --master Master.xlsx \
       --compare --outdir out_rfem
```

The importer handles RFEM's Z-down axes, kN/cm units, the My/Mz local-axis
convention (RFEM bends about local y under gravity), member hinges
(connector springs), nodal supports, self-weight rebuilt from material
density, UDL / nodal / concentrated loads (members are split at
concentrated-load positions), EN 1993 imperfection load cases (mapped to
the sway imperfection with per-combination directions), and the load
combinations.  `--compare` checks our member forces against the export's
own `CO - 4.1` result sheets and writes `validation.md`.

**Important quirk found while validating**: RFEM does not export
nonlinear, load-dependent floor-connection springs - they appear as free
rotations in the support table.  Passing `--master` restores them from the
BASE_STIFFNESS sheet (interpolated at the estimated upright load, matched
via the support comment, e.g. 'UP0016').

Cross-validation against the SPR reference rack (back-to-back double
rack, 296 nodes / 528 members, braced frames, 65.7 kNm/rad connectors,
phi = 1/300):

| comparison | result |
|---|---|
| linear LC1 self-weight | total 12.08 vs 12.09 kN; member N median 0.4% |
| linear LC2 pallet loads (441 kN) | member forces median 0.0%, p95 0.7% |
| linear LC3 lateral load | moments median 0.1% (sway stiffness identical) |
| 2nd-order CO1 (with recovered base springs) | axials median 0.3%, moments median 0.9% (member 1: 9.44 vs 9.42 kNcm) |

Without the base springs the model has alpha_cr ~ 1 under CO1 - the
second-order analysis correctly diverges, which is itself the validation
of the sway-instability detection.

## Validation

`tests/` validates the engine against closed-form solutions: cantilever
bending in both planes + torsion, simply supported beams (gravity and
lateral), beams with rotational end springs
(`M_end = wL²/12 · 1/(1+2EIz/kL)`), spring supports, truss axial response,
and second-order sway amplification vs `1/(1 − P/P_cr)`; plus EN 1993-1-1
buckling-curve spot values, section-library loading/mapping, and
full-pipeline behavior (braced direction stiffer, imperfection direction
drives sway direction, overload → failure).

```bash
python -m pytest tests/
```

## Scope & disclaimer

The global analysis is a full 3D beam/truss model. Distortional and
torsional-flexural buckling of cold-formed uprights, warping torsion,
lateral-torsional beam buckling and EN 15512 Annex-A test evaluation are
outside the current scope — per EN 15512 practice these are covered
through the tested effective section properties and resistances you supply
in the master.

This software is an engineering aid. All defaults (partial factors,
imperfection parameters, deflection limits) must be verified by a
qualified engineer against the EN 15512 edition and national provisions
applicable to the project, and section/connector properties must come from
tests per the standard.

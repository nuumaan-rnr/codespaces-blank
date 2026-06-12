# rack15512 — storage-rack analysis & EN 15512 design checks

Structural analysis app for steel storage racks (adjustable pallet racking)
per **EN 15512**: second-order elastic global analysis with **semi-rigid
connections**, global sway imperfections, and automated design checks
(stress, buckling, connector moment, deflection, sway).

## Why OpenSees as the FEA engine

The engine is [OpenSees](https://opensees.berkeley.edu/) (via
[OpenSeesPy](https://openseespydoc.readthedocs.io/)). It was chosen because
it natively covers everything EN 15512 requires for rack global analysis,
is open source, scriptable and battle-tested:

| EN 15512 requirement | OpenSees feature used |
|---|---|
| Semi-rigid beam-to-upright connectors (Annex A tests) | zero-length rotational spring elements with the tested stiffness |
| Semi-rigid floor connections | rotational spring supports (zero-length to fixed ground node) |
| Second-order (P-Delta) global analysis | `PDelta` geometric transformation + incremental Newton–Raphson; members subdivided to capture P-little-delta |
| Truss bracing | `corotTruss` (geometrically nonlinear truss) |
| Sway imperfections | equivalent horizontal forces (EHF) or initial out-of-plumb geometry |
| Beam and truss member types, arbitrary sections, steel grades | elastic beam-column elements with user section/material properties |

## What the app does

1. **Inputs**: nodes, members (beam/truss), steel materials, cross-sections
   (with effective properties for perforated uprights), member sets,
   semi-rigid supports, hinges with rotational stiffness (and optional
   moment capacity + looseness), load cases, load combinations, sway
   imperfections — via JSON file, Python API, or the Streamlit UI.
2. **Analysis**: every combination is assembled with its partial factors;
   ULS combinations get the EN 15512 sway imperfection applied in both
   directions; a geometrically nonlinear (second-order) analysis is run in
   OpenSees, plus a first-order companion to report the sway amplification
   and an estimate of the elastic critical load factor α_cr.
3. **Results**: displacements, reactions, member force diagrams (N/V/M),
   deformed shapes — viewable as PNG plots or interactively in the UI.
4. **EN 15512 checks**:
   - **STRESS** — cross-section resistance: `|N|/(A_eff·fy/γM0) + |M|/(W_eff·fy/γM0) ≤ 1`
   - **BUCKLING** — flexural buckling of compression members with χ from the
     EN 1993-1-1 §6.3.1 buckling curves (a0…d) and configurable buckling lengths
   - **CONNECTOR** — connector moment vs tested `M_Rd`
   - **DEFLECTION** — pallet-beam deflection ≤ L/200 (SLS, configurable)
   - **SWAY** — frame sway ≤ H/200 (SLS, configurable)
   - **ALPHA_CR** — sway-sensitivity report (informative; second-order
     effects are already included in the analysis)

## Install & run

```bash
pip install -r requirements.txt
# Linux: OpenSeesPy needs system BLAS/LAPACK:
#   sudo apt-get install libblas3 liblapack3

# demo: builds a 3-bay / 3-level pallet rack, runs it, writes report + plots
python -m rack15512 example --outdir out

# analyse your own model
python -m rack15512 run my_rack.json --outdir out
```

Outputs in `out/`: `report.md` (full check report), `model.png`,
`utilization.png` (color-coded member utilizations), and deformed shape /
moment / axial diagrams per combination. The CLI exits non-zero when a
check fails.

### Interactive app

```bash
pip install streamlit
streamlit run app_streamlit.py
```

Sidebar inputs for geometry, sections, connector/base stiffness, loads,
imperfections and partial factors; tabs for the model, results
(deformed shape, N/V/M diagrams, reactions), checks and the downloadable
report.

### Python API

```python
from rack15512 import (RackModel, Steel, CrossSection, Hinge, Support,
                       LoadCase, MemberLoad, Combination, Imperfection,
                       run_all, run_checks, write_report)

m = RackModel(name="my rack")               # units: N, mm, MPa
m.materials["steel"] = Steel("steel", fy=355.0)
m.sections["upright"] = CrossSection("upright", "steel", A=780, I=1.2e6,
                                     Wel=2.4e4, A_eff=660, W_eff=2.05e4,
                                     buckling_curve="b")
m.add_node(1, 0, 0); m.add_node(2, 0, 2000)
m.add_member(1, 1, 2, "upright", member_set="uprights")
m.supports.append(Support(1, ux=True, uy=True, rz=5.0e8))  # semi-rigid base
# hinges: Hinge(stiffness [N*mm/rad], m_rd [N*mm], looseness [rad])
...
cases = run_all(m)                # 2nd-order OpenSees analysis, all combos
checks = run_checks(m, cases)     # EN 15512 verifications
print(write_report(m, cases, checks))
```

A parametric generator for regular pallet racks is included
(`rack15512.builder.build_rack(RackConfig(...))`) — see
`examples/pallet_rack.json` for the generated input format.

## Model format notes

- **Units**: N, mm, MPa (N/mm²), N·mm, rad. E.g. connector stiffness
  100 kNm/rad = `1.0e8`.
- **Supports**: each DOF (`ux`, `uy`, `rz`) is `true` (fixed), `false`
  (free) or a number (spring stiffness) — a semi-rigid floor connection is
  `{"node": 0, "ux": true, "uy": true, "rz": 5.0e8}`.
- **Hinges**: `{"stiffness": 1.0e8, "m_rd": 2.5e6, "looseness": 0.0}` on
  `hinge_i`/`hinge_j` of a member; `stiffness: 0` is a perfect pin.
- **Imperfection**: give `phi` directly, or `n_cols` (+ `phi_s`, `phi_l`)
  to compute `phi = sqrt(0.5 + 1/n_cols)·(2·phi_s + phi_l) ≥ phi_min`
  (EN 15512:2009-style; per the standard, connector looseness already
  modelled in the hinges may be omitted from phi). Methods: `EHF`
  (equivalent horizontal forces) or `geometry` (initial out-of-plumb).
- **Combinations**: explicit factors per load case. Defaults used by the
  builder: ULS `1.3·G + 1.4·Q`, SLS `1.0·G + 1.0·Q`.

## Validation

`tests/` validates the engine against closed-form solutions: cantilever and
simply-supported beams, beams with rotational end springs
(`M_end = wL²/12 · 1/(1+2EI/kL)`), spring supports, truss axial response, and
second-order sway amplification vs `1/(1 − P/P_cr)`; plus EN 1993-1-1
buckling-curve spot values and full-pipeline tests.

```bash
python -m pytest tests/
```

## Scope & disclaimer

The model is the standard **2D planar frame** used for rack global analysis
(down-aisle or cross-aisle plane, analysed separately per EN 15512
practice). Distortional/torsional-flexural buckling, EN 15512 Annex-A test
evaluation and cross-aisle/down-aisle interaction are outside the current
scope — uprights must be checked for those modes separately (effective
section properties from tests are supported as inputs).

This software is an engineering aid. All defaults (partial factors,
imperfection parameters, deflection limits) must be verified by a qualified
engineer against the EN 15512 edition and national provisions applicable to
the project, and section/connector properties must come from tests per the
standard.

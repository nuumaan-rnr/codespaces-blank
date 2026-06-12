# rackapp — Storage rack analysis & EN 15512 checks

Parametric app that builds a storage-rack (pallet rack) structural model from
user inputs, runs a **second-order (P-Delta) analysis** with **semi-rigid
connections** and **sway imperfections**, and performs **EN 15512** design
checks (stress, buckling, connector, beam deflection, sway).

```
inputs (YAML / Streamlit UI)
   └─> nodes, members (uprights + pallet beams), member sets
       semi-rigid beam-end connector hinges (rotational stiffness from tests)
       semi-rigid base supports (floor-connection stiffness)
       steel material + effective cross-section properties
       load cases (dead, unit/pallet, placement, imperfection forces)
       EN 15512 load combinations (γG = 1.3, γQ = 1.4 defaults)
          └─> FEA engine (RFEM 6 or built-in solver), 2nd-order at ULS
                 └─> results (forces, displacements, reactions)
                        └─> EN 15512 checks ──> report.md / results.json / plots
```

## FEA engine choice

| | **RFEM 6 (recommended for production)** | **Built-in solver** |
|---|---|---|
| Semi-rigid beam-end connectors | member hinges with rotational spring constants | rotational end springs (static condensation) |
| Semi-rigid base plates | nodal supports with rotational springs | rotational ground springs |
| Second-order analysis | P-Delta / large deformation per combination | geometric-stiffness P-Delta iteration |
| Imperfections | imperfection cases or equivalent forces | equivalent horizontal forces |
| EN 15512 extras | Steel Design add-on incl. rack design per EN 15512 | checks implemented in `rackapp/checks.py` |
| Licence / availability | commercial, WebServices API (`pip install RFEM`) | none — runs anywhere (numpy) |

**Why RFEM 6:** of the mainstream engines it has the most direct support for
the EN 15512 modelling rules — member hinges and nodal supports defined by
*spring constants* (the standard's semi-rigid connector and floor-connection
models map 1:1), second-order analysis per load combination, imperfection
cases, member sets, and an official Python API to automate everything,
plus an EN 15512 rack-design add-on. The **built-in engine** implements the
same mechanics for the 2D down-aisle spine model, is verified against
closed-form solutions (see `tests/test_solver.py`) and lets you run the whole
pipeline with zero licences — useful for CI, previews and sanity checks.
Both engines return the same neutral result structures, so the EN 15512
checks and reports are identical.

## Install & run

```bash
pip install -r requirements.txt

# CLI: analysis + checks + report + plots
python -m rackapp run examples/rack_example.yaml --out out/
# exit code 0 = all checks pass, 2 = some check failed

# Web UI
streamlit run streamlit_app.py

# tests (solver verification + end-to-end pipeline)
pytest
```

To use RFEM 6: start RFEM with WebServices enabled (default port 8081),
`pip install RFEM`, and set `analysis.engine: rfem` in the YAML (or
`--engine rfem`).

## Inputs (see `examples/rack_example.yaml`)

* **Geometry** — number of bays, bay width, beam-level heights.
* **Sections** — *effective* properties (A, Iy, Wy, self weight) for upright
  and beam. For perforated cold-formed uprights these must come from
  EN 15512 component tests (stub column, bending); an RFEM library section
  name can be given as analysis proxy for the RFEM engine.
* **Material** — E, fy, γM0, γM1.
* **Connections** — beam-end connector rotational stiffness, looseness φℓ and
  M_Rd (from EN 15512 connector tests); base/floor rotational stiffness.
* **Loads** — unit (pallet) load per beam, beam dead load, horizontal
  placement load.
* **Imperfections** — out-of-plumb φs, optional connector looseness, minimum
  φ. Applied as equivalent horizontal forces `H = φ·V` per level (as the
  standard permits).
* **Combinations** — EN 15512:2009 Table 2 defaults: `1.3·DL + 1.4·UL +
  1.4·IMP (+1.4·PL)` at ULS (second order), `1.0·DL + 1.0·UL` at SLS.

## EN 15512 checks performed

| Check | Criterion |
|---|---|
| Cross-section resistance | `N/(A_eff·fy/γM0) + M/(W_eff·fy/γM0) ≤ 1` |
| Upright flexural buckling | `N/(χ·A_eff·fy/γM1) + M/(W_eff·fy/γM1) ≤ 1`, χ per buckling curve, `Lcr = K·(level height)` |
| Beam-end connector | `M_connector ≤ M_Rd` (test value) |
| Pallet beam deflection (SLS) | `δ ≤ L/200` (configurable) |
| Down-aisle sway (SLS) | `u_top ≤ H/200` (configurable) |

Because the ULS analysis is second order **with** sway imperfections, the
sway-buckling effect is contained in the member forces and the member checks
use the system length (`K = 1.0` default), i.e. the design-by-second-order
route of EN 15512.

## Scope & engineering notes

* The model is the **2D down-aisle spine frame** — the configuration
  EN 15512 uses for sway stability/second-order effects. Cross-aisle (braced
  upright frame) verification is a separate model.
* Distortional/torsional-flexural buckling of perforated uprights is covered
  by the *test-based effective properties* you supply, per the standard's
  test-driven philosophy; it is not computed from geometry.
* Verify imperfection values, partial factors and limits against the
  EN 15512 edition (2009 vs 2020) and national requirements applicable to
  your project. This tool automates the mechanics; the responsible engineer
  validates the inputs and results.

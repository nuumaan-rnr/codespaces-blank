# rackapp — Storage rack 3D analysis & EN 15512 checks

Parametric app that builds a **full 3D** storage-rack (pallet rack) structural
model from user inputs, runs a **second-order (P-Delta) analysis** with
**semi-rigid connections** and **sway imperfections in both directions**, and
performs **EN 15512** design checks with **biaxial (My + Mz) interaction**:
stress, buckling, connector, beam deflection, sway.

```
inputs (YAML / Streamlit UI)
   └─> 3D model: upright frames (front + rear uprights, truss bracing),
       pallet beams on both faces, member sets
       semi-rigid beam-end connector hinges (rotational stiffness from tests)
       semi-rigid base supports (floor-connection stiffness, both axes)
       steel material + effective cross-section properties (Iy/Wy, Iz/Wz, J)
       load cases (dead, unit/pallet, placement X/Y, imperfection forces X/Y)
       EN 15512 load combinations: down-aisle + cross-aisle ULS, SLS
          └─> FEA engine (RFEM 6 or built-in 3D solver), 2nd-order at ULS
                 └─> results (N, Vy, Vz, Mt, My, Mz, displacements, reactions)
                        └─> EN 15512 biaxial checks ──> report / JSON / plots
```

## Why 3D

A 2D down-aisle spine model only produces moments about one axis, so the
upright buckling interaction can never include the cross-aisle terms. The 3D
model gives, for every upright segment and every combination, the simultaneous
`N + My + Mz` set from one consistent second-order analysis, plus the braced
upright-frame behaviour (brace forces, cross-aisle sway) that a 2D model
cannot represent at all.

## FEA engine choice

| | **RFEM 6 (recommended for production)** | **Built-in solver** |
|---|---|---|
| Element types | 3D members, truss members for bracing | 12-DOF space frame + truss elements |
| Semi-rigid beam-end connectors | member hinges with rotational spring constants | rotational end springs (static condensation) |
| Semi-rigid base plates | nodal supports with rotational springs (both axes) | rotational ground springs (both axes) |
| Second-order analysis | P-Delta / large deformation per combination | geometric-stiffness P-Delta iteration, both bending planes |
| Imperfections | imperfection cases or equivalent forces | equivalent horizontal forces (X and Y) |
| EN 15512 extras | Steel Design add-on incl. rack design per EN 15512 | checks implemented in `rackapp/checks.py` |
| Licence / availability | commercial, WebServices API (`pip install RFEM`) | none — runs anywhere (numpy) |

**Why RFEM 6:** of the mainstream engines it has the most direct support for
the EN 15512 modelling rules — member hinges and nodal supports defined by
*spring constants* (the standard's semi-rigid connector and floor-connection
models map 1:1), truss bracing members, second-order analysis per load
combination, imperfection cases, member sets, and an official Python API to
automate everything, plus an EN 15512 rack-design add-on. The **built-in
engine** implements the same mechanics for the full 3D model, is verified
against closed-form solutions in both bending planes (see
`tests/test_solver.py`) and lets you run the whole pipeline with zero licences
— useful for CI, previews and sanity checks. Both engines return the same
neutral result structures, so the EN 15512 checks and reports are identical.

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

* **Geometry** — bays, bay width, frame depth, beam-level heights, frame
  bracing pattern and panel height.
* **Sections** — *effective* properties (A, Iy/Wy, Iz/Wz, J, self weight) for
  upright, beam and brace. For perforated cold-formed uprights these must
  come from EN 15512 component tests (stub column, bending); an RFEM library
  section name can be given as analysis proxy for the RFEM engine.
  Axis convention: Iy = down-aisle bending for uprights / major (vertical)
  axis for beams; Iz = cross-aisle / minor axis.
* **Material** — E, G, fy, γM0, γM1.
* **Connections** — beam-end connector rotational stiffness, looseness φℓ and
  M_Rd (from EN 15512 connector tests), horizontal-plane end fixity;
  base/floor rotational stiffness about both horizontal axes.
* **Loads** — unit (pallet) load per beam (front + rear beams share the bay
  load), beam dead load, horizontal placement load (applied down-aisle and
  cross-aisle in separate cases).
* **Imperfections** — out-of-plumb φs per direction, optional connector
  looseness (down-aisle), minimum φ. Applied as equivalent horizontal forces
  `H = φ·V` per level (as the standard permits).
* **Combinations** — EN 15512:2009 Table 2 defaults, directions treated as
  separate design situations: `ULS_DA1/2` (down-aisle ± placement), `ULS_CA`
  (cross-aisle) at 1.3·G + 1.4·Q second order; `SLS` (deflection) and
  `SLS_SWX/Y` (sway) at characteristic level.

## EN 15512 checks performed

| Check | Criterion |
|---|---|
| Cross-section resistance (biaxial) | `N/(A·fy/γM0) + My/(Wy·fy/γM0) + Mz/(Wz·fy/γM0) ≤ 1` |
| Upright flexural buckling (biaxial) | `N/(χmin·A·fy/γM1) + My/(Wy·fy/γM1) + Mz/(Wz·fy/γM1) ≤ 1`, χ per axis from EC3 curves, `Lcr = K·segment` |
| Frame brace buckling | `N ≤ χ·A·fy/γM1` (pin-ended, Lcr = L) |
| Beam-end connector | `My,connector ≤ M_Rd` (test value) |
| Pallet beam deflection (SLS) | `δ ≤ L/200` (configurable) |
| Sway, down-aisle and cross-aisle (SLS) | `u_top ≤ H/200` (configurable), on the SLS sway combinations |

Because the ULS analysis is second order **with** sway imperfections in each
direction, the sway-buckling effect is contained in the member forces and the
member checks use the system (segment) length (`K = 1.0` default), i.e. the
design-by-second-order route of EN 15512. Upright segments end at beam and
brace nodes, so the buckling lengths per axis follow the actual restraint
spacing.

## Scope & engineering notes

* Distortional/torsional-flexural buckling of perforated uprights is covered
  by the *test-based effective properties* you supply, per the standard's
  test-driven philosophy; it is not computed from geometry.
* Pallet loads are applied as UDL on the beams; `unit_load_per_beam` is the
  load carried by ONE beam (a bay storing Q per level → Q/2 per beam).
* Verify imperfection values, partial factors and limits against the
  EN 15512 edition (2009 vs 2020) and national requirements applicable to
  your project. This tool automates the mechanics; the responsible engineer
  validates the inputs and results.

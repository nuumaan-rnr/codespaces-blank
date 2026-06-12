# EN 15512 design check report - SPR back-to-back module (non-seismic)

- Analysis: second-order (P-Delta) elastic, engine: OpenSees
- Sway imperfection: phi = 0.00495 rad (1/202), method = EHF
- Partial factors: gamma_M0 = 1.0, gamma_M1 = 1.0
- Members: 432, nodes: 288, height: 6500 mm

## Load combinations

| combination | kind | load factors | imperfection |
|---|---|---|---|
| ULS1 | ULS | 1.3 x dead + 1.4 x pallets | +x, -x, +y, -y |
| ULS2 | ULS | 1.3 x dead + 1.4 x pallets + 1.4 x placement | +x, -x, +y, -y |
| ULS3 | ULS | 1.3 x dead + 1.4 x pallets + 1.4 x placement_y | +x, -x, +y, -y |
| ULS4 acc X | ULS | 1 x dead + 1 x pallets + 1 x accidental_x | +x |
| ULS5 acc Y | ULS | 1 x dead + 1 x pallets + 1 x accidental_y | +y |
| SLS1 | SLS | 1 x dead + 1 x pallets | - |
| SLS2 | SLS | 1 x dead + 1 x pallets + 1 x placement | - |

## Analysis cases

| case | kind | converged | sway X [mm] | sway Y [mm] | alpha_cr (est.) |
|---|---|---|---|---|---|
| ULS1 (imp +x) | ULS | yes | 17.35 | 0.18 | 2.85 |
| ULS1 (imp -x) | ULS | yes | 17.35 | 0.18 | 2.85 |
| ULS1 (imp +y) | ULS | yes | 1.26 | 2.47 | 12.69 |
| ULS1 (imp -y) | ULS | yes | 1.26 | 2.47 | 12.69 |
| ULS2 (imp +x) | ULS | yes | 37.78 | 0.36 | 2.89 |
| ULS2 (imp -x) | ULS | yes | 17.35 | 0.20 | 2.85 |
| ULS2 (imp +y) | ULS | yes | 21.66 | 2.62 | 3.11 |
| ULS2 (imp -y) | ULS | yes | 21.71 | 2.48 | 3.10 |
| ULS3 (imp +x) | ULS | yes | 17.38 | 2.45 | 2.92 |
| ULS3 (imp -x) | ULS | yes | 17.47 | 2.45 | 2.84 |
| ULS3 (imp +y) | ULS | yes | 1.33 | 3.82 | 27.54 |
| ULS3 (imp -y) | ULS | yes | 1.33 | 2.58 | 12.73 |
| ULS4 acc X (imp +x) | ULS | yes | 12.74 | 0.13 | 3.89 |
| ULS5 acc Y (imp +y) | ULS | yes | 0.91 | 1.90 | 20.11 |
| SLS1 | SLS | yes | 0.90 | 0.13 | 235.69 |
| SLS2 | SLS | yes | 13.53 | 0.13 | 4.45 |

## Verdict: **FAIL**

Governing: BASEPLATE on node 100000 (-) in 'ULS2 (imp +x)' - utilization **1.166**

## Utilization by level

Beams and connectors at the level; uprights and bracing of the storey below it.

| level | elevation [mm] | uprights | beams | connectors | bracing |
|---|---|---|---|---|---|
| 1 | 1500 | 0.707 PASS (BUCKLING, member 141) | 0.752 PASS (STRESS, member 273) | 0.710 PASS (CONNECTOR, member 273) | 0.349 PASS (BRACE_BOLT, member 321) |
| 2 | 3000 | 0.575 PASS (BUCKLING, member 144) | 0.745 PASS (STRESS, member 285) | 0.676 PASS (CONNECTOR, member 289) | 0.239 PASS (BRACE_BOLT, member 337) |
| 3 | 4500 | 0.406 PASS (BUCKLING, member 148) | 0.742 PASS (STRESS, member 297) | 0.631 PASS (CONNECTOR, member 305) | 0.194 PASS (BRACE_BOLT, member 340) |
| 4 | 6000 | 0.410 PASS (BUCKLING, member 15) | 0.766 PASS (STRESS, member 309) | 0.586 PASS (CONNECTOR, member 313) | 0.194 PASS (BRACE_BOLT, member 330) |

## STRESS checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 309 | pallet beams | ULS2 (imp -y) | 0.766 | PASS | N=-1.8 kN, My=0.01 kNm, Mz=3.64 kNm at x=1322 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 309 | pallet beams | ULS2 (imp +y) | 0.766 | PASS | N=-1.8 kN, My=-0.00 kNm, Mz=3.64 kNm at x=1321 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 309 | pallet beams | ULS2 (imp +x) | 0.766 | PASS | N=-1.9 kN, My=0.00 kNm, Mz=3.64 kNm at x=1311 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 309 | pallet beams | ULS2 (imp -x) | 0.763 | PASS | N=-1.8 kN, My=0.00 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 309 | pallet beams | ULS3 (imp -y) | 0.763 | PASS | N=-1.2 kN, My=0.02 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 310 | pallet beams | ULS3 (imp -y) | 0.762 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 311 | pallet beams | ULS3 (imp -y) | 0.762 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 312 | pallet beams | ULS3 (imp -y) | 0.762 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 309 | pallet beams | ULS3 (imp +x) | 0.762 | PASS | N=-1.3 kN, My=0.01 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 310 | pallet beams | ULS3 (imp +x) | 0.762 | PASS | N=-1.3 kN, My=0.01 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 311 | pallet beams | ULS3 (imp +x) | 0.762 | PASS | N=-1.3 kN, My=0.01 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 312 | pallet beams | ULS3 (imp +x) | 0.761 | PASS | N=-1.3 kN, My=0.01 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 309 | pallet beams | ULS3 (imp -x) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1351 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 319 | pallet beams | ULS3 (imp -y) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 320 | pallet beams | ULS3 (imp -y) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 318 | pallet beams | ULS3 (imp -y) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 317 | pallet beams | ULS3 (imp -y) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 310 | pallet beams | ULS3 (imp -x) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1351 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 311 | pallet beams | ULS3 (imp -x) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1351 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 320 | pallet beams | ULS2 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 311 | pallet beams | ULS2 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 318 | pallet beams | ULS2 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 319 | pallet beams | ULS2 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 312 | pallet beams | ULS3 (imp -x) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1351 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 310 | pallet beams | ULS2 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 312 | pallet beams | ULS2 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 309 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 312 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 320 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 317 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 311 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 318 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 319 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 310 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 310 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 311 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 319 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 318 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 317 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 320 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| ... | | | | | 6008 more rows omitted |

## BUCKLING checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 141 | uprights | ULS2 (imp +x) | 0.707 | PASS | Nc=56.7 kN, My=0.00 kNm, Mz=0.61 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 73 | uprights | ULS2 (imp +x) | 0.707 | PASS | Nc=56.8 kN, My=0.00 kNm, Mz=0.60 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 69 | uprights | ULS2 (imp +x) | 0.702 | PASS | Nc=57.0 kN, My=0.01 kNm, Mz=0.55 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 137 | uprights | ULS2 (imp +x) | 0.701 | PASS | Nc=56.9 kN, My=0.01 kNm, Mz=0.55 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 137 | uprights | ULS2 (imp -y) | 0.697 | PASS | Nc=59.0 kN, My=0.06 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 69 | uprights | ULS2 (imp -y) | 0.696 | PASS | Nc=59.0 kN, My=0.06 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 140 | uprights | ULS2 (imp +x) | 0.682 | PASS | Nc=56.8 kN, My=0.00 kNm, Mz=0.50 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 72 | uprights | ULS2 (imp +x) | 0.682 | PASS | Nc=56.9 kN, My=0.00 kNm, Mz=0.50 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 70 | uprights | ULS2 (imp +x) | 0.668 | PASS | Nc=56.9 kN, My=0.00 kNm, Mz=0.44 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 138 | uprights | ULS2 (imp +x) | 0.668 | PASS | Nc=56.8 kN, My=0.00 kNm, Mz=0.44 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 90 | uprights | ULS3 (imp -x) | 0.661 | PASS | Nc=57.0 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 90 | uprights | ULS3 (imp +x) | 0.660 | PASS | Nc=57.0 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 107 | uprights | ULS2 (imp -x) | 0.659 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 90 | uprights | ULS2 (imp -x) | 0.658 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 175 | uprights | ULS2 (imp -x) | 0.658 | PASS | Nc=56.9 kN, My=0.03 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 158 | uprights | ULS2 (imp -x) | 0.658 | PASS | Nc=56.9 kN, My=0.03 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 158 | uprights | ULS3 (imp +x) | 0.658 | PASS | Nc=56.7 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 158 | uprights | ULS3 (imp -x) | 0.657 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 158 | uprights | ULS1 (imp +x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 107 | uprights | ULS1 (imp -x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 175 | uprights | ULS1 (imp +x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 90 | uprights | ULS1 (imp -x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 175 | uprights | ULS3 (imp +x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 90 | uprights | ULS1 (imp +x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 175 | uprights | ULS1 (imp -x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 107 | uprights | ULS1 (imp +x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 158 | uprights | ULS1 (imp -x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 175 | uprights | ULS3 (imp -x) | 0.656 | PASS | Nc=56.9 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 158 | uprights | ULS2 (imp +x) | 0.656 | PASS | Nc=56.7 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 175 | uprights | ULS2 (imp +x) | 0.656 | PASS | Nc=56.7 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 90 | uprights | ULS2 (imp +x) | 0.656 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 107 | uprights | ULS2 (imp +x) | 0.655 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 107 | uprights | ULS3 (imp -x) | 0.654 | PASS | Nc=56.6 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 107 | uprights | ULS3 (imp +x) | 0.654 | PASS | Nc=56.6 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 89 | uprights | ULS3 (imp -x) | 0.653 | PASS | Nc=57.0 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 89 | uprights | ULS3 (imp +x) | 0.653 | PASS | Nc=57.0 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 89 | uprights | ULS2 (imp -x) | 0.652 | PASS | Nc=56.8 kN, My=0.04 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 157 | uprights | ULS2 (imp -x) | 0.652 | PASS | Nc=56.9 kN, My=0.04 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 106 | uprights | ULS2 (imp -x) | 0.652 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 174 | uprights | ULS2 (imp -x) | 0.651 | PASS | Nc=56.9 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| ... | | | | | 3371 more rows omitted |

## CONNECTOR checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 273 end j (z) | pallet beams | ULS2 (imp +x) | 0.710 | PASS | Mz,Ed=1.775 kNm, Mz,Rd=2.500 kNm |
| member 277 end j (z) | pallet beams | ULS2 (imp +x) | 0.709 | PASS | Mz,Ed=1.771 kNm, Mz,Rd=2.500 kNm |
| member 281 end j (z) | pallet beams | ULS2 (imp +x) | 0.693 | PASS | Mz,Ed=1.733 kNm, Mz,Rd=2.500 kNm |
| member 289 end j (z) | pallet beams | ULS2 (imp +x) | 0.676 | PASS | Mz,Ed=1.690 kNm, Mz,Rd=2.500 kNm |
| member 285 end j (z) | pallet beams | ULS2 (imp +x) | 0.671 | PASS | Mz,Ed=1.677 kNm, Mz,Rd=2.500 kNm |
| member 293 end j (z) | pallet beams | ULS2 (imp +x) | 0.668 | PASS | Mz,Ed=1.671 kNm, Mz,Rd=2.500 kNm |
| member 305 end j (z) | pallet beams | ULS2 (imp +x) | 0.631 | PASS | Mz,Ed=1.578 kNm, Mz,Rd=2.500 kNm |
| member 301 end j (z) | pallet beams | ULS2 (imp +x) | 0.630 | PASS | Mz,Ed=1.574 kNm, Mz,Rd=2.500 kNm |
| member 297 end j (z) | pallet beams | ULS2 (imp +x) | 0.620 | PASS | Mz,Ed=1.550 kNm, Mz,Rd=2.500 kNm |
| member 273 end j (z) | pallet beams | ULS2 (imp -y) | 0.607 | PASS | Mz,Ed=1.518 kNm, Mz,Rd=2.500 kNm |
| member 277 end j (z) | pallet beams | ULS2 (imp -y) | 0.607 | PASS | Mz,Ed=1.517 kNm, Mz,Rd=2.500 kNm |
| member 273 end j (z) | pallet beams | ULS2 (imp +y) | 0.606 | PASS | Mz,Ed=1.516 kNm, Mz,Rd=2.500 kNm |
| member 277 end j (z) | pallet beams | ULS2 (imp +y) | 0.606 | PASS | Mz,Ed=1.514 kNm, Mz,Rd=2.500 kNm |
| member 282 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.504 kNm, Mz,Rd=2.500 kNm |
| member 284 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.503 kNm, Mz,Rd=2.500 kNm |
| member 274 end j (z) | pallet beams | ULS3 (imp +x) | 0.601 | PASS | Mz,Ed=1.503 kNm, Mz,Rd=2.500 kNm |
| member 276 end j (z) | pallet beams | ULS3 (imp +x) | 0.601 | PASS | Mz,Ed=1.503 kNm, Mz,Rd=2.500 kNm |
| member 278 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 283 end i (z) | pallet beams | ULS2 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 282 end i (z) | pallet beams | ULS2 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 274 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 275 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 282 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 283 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 275 end j (z) | pallet beams | ULS2 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 276 end j (z) | pallet beams | ULS2 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 281 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 284 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 276 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 273 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 284 end i (z) | pallet beams | ULS2 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 274 end j (z) | pallet beams | ULS2 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 280 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 275 end j (z) | pallet beams | ULS3 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 278 end j (z) | pallet beams | ULS3 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 279 end i (z) | pallet beams | ULS2 (imp -x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 280 end j (z) | pallet beams | ULS3 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 278 end i (z) | pallet beams | ULS2 (imp -x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 273 end j (z) | pallet beams | ULS3 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 279 end i (z) | pallet beams | ULS1 (imp -x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| ... | | | | | 1304 more rows omitted |

## BRACE_BOLT checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 321 | bracing | ULS5 acc Y (imp +y) | 0.349 | PASS | N=1.09 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 359 | bracing | ULS3 (imp +y) | 0.327 | PASS | N=1.02 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 371 | bracing | ULS3 (imp -y) | 0.312 | PASS | N=0.98 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 359 | bracing | ULS2 (imp +y) | 0.305 | PASS | N=0.96 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 371 | bracing | ULS2 (imp -y) | 0.305 | PASS | N=0.95 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 359 | bracing | ULS1 (imp +y) | 0.304 | PASS | N=0.95 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 383 | bracing | ULS1 (imp +y) | 0.304 | PASS | N=0.95 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 347 | bracing | ULS1 (imp -y) | 0.304 | PASS | N=0.95 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 371 | bracing | ULS1 (imp -y) | 0.304 | PASS | N=0.95 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 383 | bracing | ULS2 (imp +y) | 0.304 | PASS | N=0.95 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 347 | bracing | ULS2 (imp -y) | 0.303 | PASS | N=0.95 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 383 | bracing | ULS3 (imp +y) | 0.296 | PASS | N=0.93 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 335 | bracing | ULS3 (imp +y) | 0.285 | PASS | N=0.89 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 347 | bracing | ULS3 (imp -y) | 0.282 | PASS | N=0.88 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 360 | bracing | ULS3 (imp +y) | 0.269 | PASS | N=0.84 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 336 | bracing | ULS3 (imp +y) | 0.262 | PASS | N=0.82 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 372 | bracing | ULS3 (imp -y) | 0.253 | PASS | N=0.79 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 335 | bracing | ULS5 acc Y (imp +y) | 0.250 | PASS | N=0.78 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 360 | bracing | ULS2 (imp +y) | 0.246 | PASS | N=0.77 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 372 | bracing | ULS2 (imp -y) | 0.245 | PASS | N=0.77 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 360 | bracing | ULS1 (imp +y) | 0.245 | PASS | N=0.77 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 384 | bracing | ULS1 (imp +y) | 0.245 | PASS | N=0.77 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 348 | bracing | ULS1 (imp -y) | 0.245 | PASS | N=0.77 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 372 | bracing | ULS1 (imp -y) | 0.245 | PASS | N=0.77 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 384 | bracing | ULS2 (imp +y) | 0.244 | PASS | N=0.77 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 348 | bracing | ULS2 (imp -y) | 0.244 | PASS | N=0.76 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 337 | bracing | ULS3 (imp +y) | 0.239 | PASS | N=0.75 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 384 | bracing | ULS3 (imp +y) | 0.237 | PASS | N=0.74 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 324 | bracing | ULS3 (imp +y) | 0.235 | PASS | N=0.74 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 361 | bracing | ULS3 (imp +y) | 0.233 | PASS | N=0.73 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 359 | bracing | ULS5 acc Y (imp +y) | 0.223 | PASS | N=0.70 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 348 | bracing | ULS3 (imp -y) | 0.221 | PASS | N=0.69 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 348 | bracing | ULS3 (imp +y) | 0.220 | PASS | N=0.69 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 373 | bracing | ULS3 (imp -y) | 0.217 | PASS | N=0.68 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 325 | bracing | ULS3 (imp +y) | 0.214 | PASS | N=0.67 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 338 | bracing | ULS3 (imp +y) | 0.212 | PASS | N=0.66 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 326 | bracing | ULS3 (imp +y) | 0.211 | PASS | N=0.66 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 361 | bracing | ULS2 (imp +y) | 0.211 | PASS | N=0.66 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 373 | bracing | ULS2 (imp -y) | 0.210 | PASS | N=0.66 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 361 | bracing | ULS1 (imp +y) | 0.210 | PASS | N=0.66 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| ... | | | | | 1528 more rows omitted |

## BASEPLATE checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| node 100000 | - | ULS2 (imp +x) | 1.166 | FAIL | plate 100x176x4.0: c=9.7 mm, A_eff=5119 mm2 vs A_req=5970 mm2 (upright 120x63 overhangs the plate; A_eff capped by the plate area); N=57.0 kN, M=0.55 kNm -> N_eq=84.6 kN at node 100000; f_jd=14.17 MPa, A_req=5970 mm2, strip c_req=11.4 mm -> t_req=4.7 mm (use >= 4.7 mm), min plate area 58x103 mm |
| node 200000 | - | ULS2 (imp -y) | 1.009 | FAIL | plate 100x176x4.0: c=9.7 mm, A_eff=5119 mm2 vs A_req=5167 mm2 (upright 120x63 overhangs the plate; A_eff capped by the plate area); N=59.0 kN, M=0.28 kNm -> N_eq=73.2 kN at node 200000; f_jd=14.17 MPa, A_req=5167 mm2, strip c_req=9.8 mm -> t_req=4.0 mm (use >= 4.0 mm), min plate area 54x95 mm |
| node 130000 | - | ULS3 (imp -x) | 0.981 | PASS | plate 100x176x4.0: c=9.7 mm, A_eff=5119 mm2 vs A_req=5025 mm2 (upright 120x63 overhangs the plate; A_eff capped by the plate area); N=57.2 kN, M=0.28 kNm -> N_eq=71.2 kN at node 130000; f_jd=14.17 MPa, A_req=5025 mm2, strip c_req=9.5 mm -> t_req=3.9 mm (use >= 3.9 mm), min plate area 53x94 mm |
| node 130000 | - | ULS3 (imp +x) | 0.981 | PASS | plate 100x176x4.0: c=9.7 mm, A_eff=5119 mm2 vs A_req=5021 mm2 (upright 120x63 overhangs the plate; A_eff capped by the plate area); N=57.2 kN, M=0.28 kNm -> N_eq=71.1 kN at node 130000; f_jd=14.17 MPa, A_req=5021 mm2, strip c_req=9.5 mm -> t_req=3.9 mm (use >= 3.9 mm), min plate area 53x94 mm |
| node 130000 | - | ULS1 (imp -x) | 0.976 | PASS | plate 100x176x4.0: c=9.7 mm, A_eff=5119 mm2 vs A_req=4999 mm2 (upright 120x63 overhangs the plate; A_eff capped by the plate area); N=56.9 kN, M=0.28 kNm -> N_eq=70.8 kN at node 130000; f_jd=14.17 MPa, A_req=4999 mm2, strip c_req=9.5 mm -> t_req=3.9 mm (use >= 3.9 mm), min plate area 53x94 mm |
| node 230000 | - | ULS1 (imp +x) | 0.976 | PASS | plate 100x176x4.0: c=9.7 mm, A_eff=5119 mm2 vs A_req=4999 mm2 (upright 120x63 overhangs the plate; A_eff capped by the plate area); N=56.9 kN, M=0.28 kNm -> N_eq=70.8 kN at node 230000; f_jd=14.17 MPa, A_req=4999 mm2, strip c_req=9.5 mm -> t_req=3.9 mm (use >= 3.9 mm), min plate area 53x94 mm |
| node 130000 | - | ULS2 (imp -x) | 0.976 | PASS | plate 100x176x4.0: c=9.7 mm, A_eff=5119 mm2 vs A_req=4995 mm2 (upright 120x63 overhangs the plate; A_eff capped by the plate area); N=56.9 kN, M=0.28 kNm -> N_eq=70.8 kN at node 130000; f_jd=14.17 MPa, A_req=4995 mm2, strip c_req=9.4 mm -> t_req=3.9 mm (use >= 3.9 mm), min plate area 53x94 mm |
| node 200000 | - | ULS2 (imp +y) | 0.946 | PASS | plate 100x176x4.0: c=9.7 mm, A_eff=5119 mm2 vs A_req=4844 mm2 (upright 120x63 overhangs the plate; A_eff capped by the plate area); N=54.8 kN, M=0.28 kNm -> N_eq=68.6 kN at node 200000; f_jd=14.17 MPa, A_req=4844 mm2, strip c_req=9.1 mm -> t_req=3.8 mm (use >= 3.8 mm), min plate area 52x92 mm |
| node 130000 | - | ULS3 (imp +y) | 0.866 | PASS | plate 100x176x4.0: c=9.7 mm, A_eff=5119 mm2 vs A_req=4435 mm2 (upright 120x63 overhangs the plate; A_eff capped by the plate area); N=59.3 kN, M=0.07 kNm -> N_eq=62.8 kN at node 130000; f_jd=14.17 MPa, A_req=4435 mm2, strip c_req=8.3 mm -> t_req=3.4 mm (use >= 3.4 mm), min plate area 50x88 mm |
| node 200000 | - | ULS3 (imp -y) | 0.861 | PASS | plate 100x176x4.0: c=9.7 mm, A_eff=5119 mm2 vs A_req=4409 mm2 (upright 120x63 overhangs the plate; A_eff capped by the plate area); N=59.1 kN, M=0.07 kNm -> N_eq=62.5 kN at node 200000; f_jd=14.17 MPa, A_req=4409 mm2, strip c_req=8.2 mm -> t_req=3.4 mm (use >= 3.4 mm), min plate area 50x88 mm |
| node 100000 | - | ULS1 (imp -y) | 0.859 | PASS | plate 100x176x4.0: c=9.7 mm, A_eff=5119 mm2 vs A_req=4395 mm2 (upright 120x63 overhangs the plate; A_eff capped by the plate area); N=59.0 kN, M=0.06 kNm -> N_eq=62.3 kN at node 100000; f_jd=14.17 MPa, A_req=4395 mm2, strip c_req=8.2 mm -> t_req=3.4 mm (use >= 3.4 mm), min plate area 50x88 mm |
| node 230000 | - | ULS1 (imp +y) | 0.859 | PASS | plate 100x176x4.0: c=9.7 mm, A_eff=5119 mm2 vs A_req=4395 mm2 (upright 120x63 overhangs the plate; A_eff capped by the plate area); N=59.0 kN, M=0.06 kNm -> N_eq=62.3 kN at node 230000; f_jd=14.17 MPa, A_req=4395 mm2, strip c_req=8.2 mm -> t_req=3.4 mm (use >= 3.4 mm), min plate area 50x88 mm |
| node 200000 | - | ULS4 acc X (imp +x) | 0.721 | PASS | plate 100x176x4.0: c=9.7 mm, A_eff=5119 mm2 vs A_req=3691 mm2 (upright 120x63 overhangs the plate; A_eff capped by the plate area); N=40.7 kN, M=0.23 kNm -> N_eq=52.3 kN at node 200000; f_jd=14.17 MPa, A_req=3691 mm2, strip c_req=6.8 mm -> t_req=2.8 mm (use >= 3.0 mm), min plate area 46x81 mm |
| node 130000 | - | ULS5 acc Y (imp +y) | 0.615 | PASS | plate 100x176x4.0: c=9.7 mm, A_eff=5119 mm2 vs A_req=3148 mm2 (upright 120x63 overhangs the plate; A_eff capped by the plate area); N=42.2 kN, M=0.05 kNm -> N_eq=44.6 kN at node 130000; f_jd=14.17 MPa, A_req=3148 mm2, strip c_req=5.7 mm -> t_req=2.3 mm (use >= 3.0 mm), min plate area 42x74 mm |

## DEFLECTION checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 309 | pallet beams | SLS2 | 0.649 | PASS | defl=8.77 mm, limit=L/200=13.50 mm |
| member 310 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 311 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 320 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 311 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 310 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 318 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 319 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 309 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 312 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 317 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 320 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 319 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 312 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 318 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 317 | pallet beams | SLS2 | 0.646 | PASS | defl=8.71 mm, limit=L/200=13.50 mm |
| member 273 | pallet beams | SLS2 | 0.639 | PASS | defl=8.63 mm, limit=L/200=13.50 mm |
| member 274 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 276 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 284 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 284 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 276 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 273 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 281 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 275 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 275 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 283 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 274 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 282 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 283 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 282 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 285 | pallet beams | SLS2 | 0.637 | PASS | defl=8.60 mm, limit=L/200=13.50 mm |
| member 281 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 286 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 296 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 287 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 296 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 285 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 288 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 293 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| ... | | | | | 56 more rows omitted |

## SWAY checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| frame X (down-aisle) | - | SLS2 | 0.416 | PASS | max sway=13.53 mm, limit=H/200=32.50 mm (H=6500 mm) |
| frame X (down-aisle) | - | SLS1 | 0.028 | PASS | max sway=0.90 mm, limit=H/200=32.50 mm (H=6500 mm) |
| frame Y (cross-aisle) | - | SLS2 | 0.004 | PASS | max sway=0.13 mm, limit=H/200=32.50 mm (H=6500 mm) |
| frame Y (cross-aisle) | - | SLS1 | 0.004 | PASS | max sway=0.13 mm, limit=H/200=32.50 mm (H=6500 mm) |

## ALPHA_CR checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| frame | - | ULS3 (imp -x) | 1.057 | INFO | estimated alpha_cr=2.84, sway amplification=1.544 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS1 (imp +x) | 1.051 | INFO | estimated alpha_cr=2.85, sway amplification=1.539 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS1 (imp -x) | 1.051 | INFO | estimated alpha_cr=2.85, sway amplification=1.539 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS2 (imp -x) | 1.051 | INFO | estimated alpha_cr=2.85, sway amplification=1.539 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS2 (imp +x) | 1.039 | INFO | estimated alpha_cr=2.89, sway amplification=1.530 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS3 (imp +x) | 1.027 | INFO | estimated alpha_cr=2.92, sway amplification=1.520 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS2 (imp -y) | 0.967 | INFO | estimated alpha_cr=3.10, sway amplification=1.475 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS2 (imp +y) | 0.964 | INFO | estimated alpha_cr=3.11, sway amplification=1.474 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS4 acc X (imp +x) | 0.772 | INFO | estimated alpha_cr=3.89, sway amplification=1.346 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS1 (imp -y) | 0.236 | INFO | estimated alpha_cr=12.69, sway amplification=1.086 |
| frame | - | ULS1 (imp +y) | 0.236 | INFO | estimated alpha_cr=12.69, sway amplification=1.086 |
| frame | - | ULS3 (imp -y) | 0.236 | INFO | estimated alpha_cr=12.73, sway amplification=1.085 |
| frame | - | ULS5 acc Y (imp +y) | 0.149 | INFO | estimated alpha_cr=20.11, sway amplification=1.052 |
| frame | - | ULS3 (imp +y) | 0.109 | INFO | estimated alpha_cr=27.54, sway amplification=1.038 |

---
*Defaults follow EN 15512 with EN 1993 buckling curves; verify all factors, imperfection parameters and section/connector test values against the edition of the standard applicable to your project.*
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

## Verdict: **PASS**

Governing: STRESS on member 309 (pallet beams) in 'ULS2 (imp -y)' - utilization **0.766**

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
| member 141 | uprights | ULS2 (imp +x) | 0.707 | PASS | Nc=56.7 kN, My=0.00 kNm, Mz=0.61 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 73 | uprights | ULS2 (imp +x) | 0.707 | PASS | Nc=56.8 kN, My=0.00 kNm, Mz=0.60 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 69 | uprights | ULS2 (imp +x) | 0.702 | PASS | Nc=57.0 kN, My=0.01 kNm, Mz=0.55 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 137 | uprights | ULS2 (imp +x) | 0.701 | PASS | Nc=56.9 kN, My=0.01 kNm, Mz=0.55 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 137 | uprights | ULS2 (imp -y) | 0.697 | PASS | Nc=59.0 kN, My=0.06 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 69 | uprights | ULS2 (imp -y) | 0.696 | PASS | Nc=59.0 kN, My=0.06 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 140 | uprights | ULS2 (imp +x) | 0.682 | PASS | Nc=56.8 kN, My=0.00 kNm, Mz=0.50 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 72 | uprights | ULS2 (imp +x) | 0.682 | PASS | Nc=56.9 kN, My=0.00 kNm, Mz=0.50 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 70 | uprights | ULS2 (imp +x) | 0.668 | PASS | Nc=56.9 kN, My=0.00 kNm, Mz=0.44 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 138 | uprights | ULS2 (imp +x) | 0.668 | PASS | Nc=56.8 kN, My=0.00 kNm, Mz=0.44 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 90 | uprights | ULS3 (imp -x) | 0.661 | PASS | Nc=57.0 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 90 | uprights | ULS3 (imp +x) | 0.660 | PASS | Nc=57.0 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 107 | uprights | ULS2 (imp -x) | 0.659 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 90 | uprights | ULS2 (imp -x) | 0.658 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 175 | uprights | ULS2 (imp -x) | 0.658 | PASS | Nc=56.9 kN, My=0.03 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 158 | uprights | ULS2 (imp -x) | 0.658 | PASS | Nc=56.9 kN, My=0.03 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 158 | uprights | ULS3 (imp +x) | 0.658 | PASS | Nc=56.7 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 158 | uprights | ULS3 (imp -x) | 0.657 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 158 | uprights | ULS1 (imp +x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 107 | uprights | ULS1 (imp -x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 175 | uprights | ULS1 (imp +x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 90 | uprights | ULS1 (imp -x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 175 | uprights | ULS3 (imp +x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 90 | uprights | ULS1 (imp +x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 175 | uprights | ULS1 (imp -x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 107 | uprights | ULS1 (imp +x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 158 | uprights | ULS1 (imp -x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 175 | uprights | ULS3 (imp -x) | 0.656 | PASS | Nc=56.9 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 158 | uprights | ULS2 (imp +x) | 0.656 | PASS | Nc=56.7 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 175 | uprights | ULS2 (imp +x) | 0.656 | PASS | Nc=56.7 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 90 | uprights | ULS2 (imp +x) | 0.656 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 107 | uprights | ULS2 (imp +x) | 0.655 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 107 | uprights | ULS3 (imp -x) | 0.654 | PASS | Nc=56.6 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 107 | uprights | ULS3 (imp +x) | 0.654 | PASS | Nc=56.6 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 89 | uprights | ULS3 (imp -x) | 0.653 | PASS | Nc=57.0 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 89 | uprights | ULS3 (imp +x) | 0.653 | PASS | Nc=57.0 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 89 | uprights | ULS2 (imp -x) | 0.652 | PASS | Nc=56.8 kN, My=0.04 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 157 | uprights | ULS2 (imp -x) | 0.652 | PASS | Nc=56.9 kN, My=0.04 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 106 | uprights | ULS2 (imp -x) | 0.652 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| member 174 | uprights | ULS2 (imp -x) | 0.651 | PASS | Nc=56.9 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi_min=0.740 (gov y), Nb_Rd=101.0 kN |
| ... | | | | | 3371 more rows omitted |

## BRACE_BUCKLING checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 359 | bracing | ULS3 (imp +y) | 0.186 | PASS | Nc=1.02 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 371 | bracing | ULS3 (imp -y) | 0.178 | PASS | Nc=0.98 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 359 | bracing | ULS2 (imp +y) | 0.174 | PASS | Nc=0.96 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 371 | bracing | ULS2 (imp -y) | 0.174 | PASS | Nc=0.95 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 359 | bracing | ULS1 (imp +y) | 0.173 | PASS | Nc=0.95 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 383 | bracing | ULS1 (imp +y) | 0.173 | PASS | Nc=0.95 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 347 | bracing | ULS1 (imp -y) | 0.173 | PASS | Nc=0.95 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 371 | bracing | ULS1 (imp -y) | 0.173 | PASS | Nc=0.95 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 383 | bracing | ULS2 (imp +y) | 0.173 | PASS | Nc=0.95 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 347 | bracing | ULS2 (imp -y) | 0.173 | PASS | Nc=0.95 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 383 | bracing | ULS3 (imp +y) | 0.169 | PASS | Nc=0.93 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 335 | bracing | ULS3 (imp +y) | 0.162 | PASS | Nc=0.89 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 321 | bracing | ULS5 acc Y (imp +y) | 0.162 | PASS | Nc=1.09 kN, L=1000 mm, chi_min=0.246 (gov FT, curve c), Nb_Rd=6.78 kN |
| member 347 | bracing | ULS3 (imp -y) | 0.160 | PASS | Nc=0.88 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 335 | bracing | ULS5 acc Y (imp +y) | 0.143 | PASS | Nc=0.78 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 337 | bracing | ULS3 (imp +y) | 0.136 | PASS | Nc=0.75 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 324 | bracing | ULS3 (imp +y) | 0.134 | PASS | Nc=0.74 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 361 | bracing | ULS3 (imp +y) | 0.133 | PASS | Nc=0.73 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 359 | bracing | ULS5 acc Y (imp +y) | 0.127 | PASS | Nc=0.70 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 348 | bracing | ULS3 (imp +y) | 0.125 | PASS | Nc=0.69 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 373 | bracing | ULS3 (imp -y) | 0.123 | PASS | Nc=0.68 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 326 | bracing | ULS3 (imp +y) | 0.120 | PASS | Nc=0.66 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 361 | bracing | ULS2 (imp +y) | 0.120 | PASS | Nc=0.66 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 373 | bracing | ULS2 (imp -y) | 0.120 | PASS | Nc=0.66 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 361 | bracing | ULS1 (imp +y) | 0.120 | PASS | Nc=0.66 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 385 | bracing | ULS1 (imp +y) | 0.120 | PASS | Nc=0.66 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 373 | bracing | ULS1 (imp -y) | 0.120 | PASS | Nc=0.66 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 349 | bracing | ULS1 (imp -y) | 0.120 | PASS | Nc=0.66 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 385 | bracing | ULS2 (imp +y) | 0.119 | PASS | Nc=0.66 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 349 | bracing | ULS2 (imp -y) | 0.119 | PASS | Nc=0.65 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 383 | bracing | ULS5 acc Y (imp +y) | 0.118 | PASS | Nc=0.65 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 385 | bracing | ULS3 (imp +y) | 0.116 | PASS | Nc=0.64 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 384 | bracing | ULS3 (imp -y) | 0.116 | PASS | Nc=0.64 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 339 | bracing | ULS3 (imp +y) | 0.115 | PASS | Nc=0.63 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 324 | bracing | ULS5 acc Y (imp +y) | 0.112 | PASS | Nc=0.62 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 348 | bracing | ULS2 (imp +y) | 0.112 | PASS | Nc=0.61 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 384 | bracing | ULS2 (imp -y) | 0.111 | PASS | Nc=0.61 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 348 | bracing | ULS1 (imp +y) | 0.111 | PASS | Nc=0.61 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 372 | bracing | ULS1 (imp +y) | 0.111 | PASS | Nc=0.61 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| member 360 | bracing | ULS1 (imp -y) | 0.111 | PASS | Nc=0.61 kN, L=1166 mm, chi_min=0.200 (gov FT, curve c), Nb_Rd=5.50 kN |
| ... | | | | | 770 more rows omitted |

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
| node 130000 | - | ULS3 (imp +y) | 0.452 | PASS | N=59.3 kN at node 130000; fj=2.5*fck/gc=41.7 MPa, plate 100x176x4.0, e=5.7 mm (cap 56.5), Abas=3148 mm2, fj*Abas=131.2 kN >= N? util=0.452; t to fill plate ~40.0 mm |
| node 200000 | - | ULS3 (imp -y) | 0.451 | PASS | N=59.1 kN at node 200000; fj=2.5*fck/gc=41.7 MPa, plate 100x176x4.0, e=5.7 mm (cap 56.5), Abas=3148 mm2, fj*Abas=131.2 kN >= N? util=0.451; t to fill plate ~40.0 mm |
| node 100000 | - | ULS2 (imp -y) | 0.450 | PASS | N=59.0 kN at node 100000; fj=2.5*fck/gc=41.7 MPa, plate 100x176x4.0, e=5.7 mm (cap 56.5), Abas=3148 mm2, fj*Abas=131.2 kN >= N? util=0.450; t to fill plate ~40.0 mm |
| node 130000 | - | ULS2 (imp +y) | 0.450 | PASS | N=59.0 kN at node 130000; fj=2.5*fck/gc=41.7 MPa, plate 100x176x4.0, e=5.7 mm (cap 56.5), Abas=3148 mm2, fj*Abas=131.2 kN >= N? util=0.450; t to fill plate ~40.0 mm |
| node 200000 | - | ULS1 (imp -y) | 0.450 | PASS | N=59.0 kN at node 200000; fj=2.5*fck/gc=41.7 MPa, plate 100x176x4.0, e=5.7 mm (cap 56.5), Abas=3148 mm2, fj*Abas=131.2 kN >= N? util=0.450; t to fill plate ~40.0 mm |
| node 230000 | - | ULS1 (imp +y) | 0.450 | PASS | N=59.0 kN at node 230000; fj=2.5*fck/gc=41.7 MPa, plate 100x176x4.0, e=5.7 mm (cap 56.5), Abas=3148 mm2, fj*Abas=131.2 kN >= N? util=0.450; t to fill plate ~40.0 mm |
| node 130000 | - | ULS3 (imp +x) | 0.436 | PASS | N=57.2 kN at node 130000; fj=2.5*fck/gc=41.7 MPa, plate 100x176x4.0, e=5.7 mm (cap 56.5), Abas=3148 mm2, fj*Abas=131.2 kN >= N? util=0.436; t to fill plate ~40.0 mm |
| node 130000 | - | ULS3 (imp -x) | 0.436 | PASS | N=57.2 kN at node 130000; fj=2.5*fck/gc=41.7 MPa, plate 100x176x4.0, e=5.7 mm (cap 56.5), Abas=3148 mm2, fj*Abas=131.2 kN >= N? util=0.436; t to fill plate ~40.0 mm |
| node 130000 | - | ULS2 (imp +x) | 0.435 | PASS | N=57.0 kN at node 130000; fj=2.5*fck/gc=41.7 MPa, plate 100x176x4.0, e=5.7 mm (cap 56.5), Abas=3148 mm2, fj*Abas=131.2 kN >= N? util=0.435; t to fill plate ~40.0 mm |
| node 200000 | - | ULS1 (imp -x) | 0.434 | PASS | N=56.9 kN at node 200000; fj=2.5*fck/gc=41.7 MPa, plate 100x176x4.0, e=5.7 mm (cap 56.5), Abas=3148 mm2, fj*Abas=131.2 kN >= N? util=0.434; t to fill plate ~40.0 mm |
| node 100000 | - | ULS1 (imp +x) | 0.434 | PASS | N=56.9 kN at node 100000; fj=2.5*fck/gc=41.7 MPa, plate 100x176x4.0, e=5.7 mm (cap 56.5), Abas=3148 mm2, fj*Abas=131.2 kN >= N? util=0.434; t to fill plate ~40.0 mm |
| node 230000 | - | ULS2 (imp -x) | 0.434 | PASS | N=56.9 kN at node 230000; fj=2.5*fck/gc=41.7 MPa, plate 100x176x4.0, e=5.7 mm (cap 56.5), Abas=3148 mm2, fj*Abas=131.2 kN >= N? util=0.434; t to fill plate ~40.0 mm |
| node 130000 | - | ULS5 acc Y (imp +y) | 0.322 | PASS | N=42.2 kN at node 130000; fj=2.5*fck/gc=41.7 MPa, plate 100x176x4.0, e=5.7 mm (cap 56.5), Abas=3148 mm2, fj*Abas=131.2 kN >= N? util=0.322; t to fill plate ~40.0 mm |
| node 130000 | - | ULS4 acc X (imp +x) | 0.310 | PASS | N=40.7 kN at node 130000; fj=2.5*fck/gc=41.7 MPa, plate 100x176x4.0, e=5.7 mm (cap 56.5), Abas=3148 mm2, fj*Abas=131.2 kN >= N? util=0.310; t to fill plate ~40.0 mm |

## BASE_RESTRAINT checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| node 300000 | uprights | ULS2 (imp +x) | 0.290 | PASS | N=29.5 kN, M_Sd=0.58 kNm, M_Rd(N)=2.00 kNm |
| node 310000 | uprights | ULS3 (imp +x) | 0.158 | PASS | N=28.7 kN, M_Sd=0.32 kNm, M_Rd(N)=2.00 kNm |
| node 10000 | uprights | ULS2 (imp -x) | 0.158 | PASS | N=28.7 kN, M_Sd=0.32 kNm, M_Rd(N)=2.00 kNm |
| node 310000 | uprights | ULS1 (imp +x) | 0.158 | PASS | N=28.7 kN, M_Sd=0.32 kNm, M_Rd(N)=2.00 kNm |
| node 10000 | uprights | ULS1 (imp -x) | 0.158 | PASS | N=28.7 kN, M_Sd=0.32 kNm, M_Rd(N)=2.00 kNm |
| node 0 | uprights | ULS3 (imp -x) | 0.158 | PASS | N=26.8 kN, M_Sd=0.32 kNm, M_Rd(N)=2.00 kNm |
| node 300000 | uprights | ULS2 (imp -y) | 0.157 | PASS | N=30.1 kN, M_Sd=0.32 kNm, M_Rd(N)=2.01 kNm |
| node 300000 | uprights | ULS2 (imp +y) | 0.156 | PASS | N=27.8 kN, M_Sd=0.31 kNm, M_Rd(N)=2.00 kNm |
| node 0 | uprights | ULS5 acc Y (imp +y) | 0.140 | PASS | N=19.4 kN, M_Sd=0.28 kNm, M_Rd(N)=2.00 kNm |
| node 300000 | uprights | ULS4 acc X (imp +x) | 0.129 | PASS | N=20.6 kN, M_Sd=0.26 kNm, M_Rd(N)=2.00 kNm |
| node 30000 | uprights | ULS3 (imp +y) | 0.039 | PASS | N=31.4 kN, M_Sd=0.08 kNm, M_Rd(N)=2.07 kNm |
| node 300000 | uprights | ULS3 (imp -y) | 0.030 | PASS | N=29.5 kN, M_Sd=0.06 kNm, M_Rd(N)=2.00 kNm |
| node 0 | uprights | ULS1 (imp -y) | 0.029 | PASS | N=29.5 kN, M_Sd=0.06 kNm, M_Rd(N)=2.00 kNm |
| node 330000 | uprights | ULS1 (imp +y) | 0.029 | PASS | N=29.5 kN, M_Sd=0.06 kNm, M_Rd(N)=2.00 kNm |

## ANCHORAGE checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| node 20000 | uprights | ULS1 (imp +x) | 0.000 | PASS | uplift=0.00 kN vs anchor tension capacity 3.0 kN (EN 15512 9.10.4 min 3 kN tension + 5 kN shear must also be provided) |
| node 320000 | uprights | ULS1 (imp -x) | 0.000 | PASS | uplift=0.00 kN vs anchor tension capacity 3.0 kN (EN 15512 9.10.4 min 3 kN tension + 5 kN shear must also be provided) |
| node 20000 | uprights | ULS1 (imp +y) | 0.000 | PASS | uplift=0.00 kN vs anchor tension capacity 3.0 kN (EN 15512 9.10.4 min 3 kN tension + 5 kN shear must also be provided) |
| node 310000 | uprights | ULS1 (imp -y) | 0.000 | PASS | uplift=0.00 kN vs anchor tension capacity 3.0 kN (EN 15512 9.10.4 min 3 kN tension + 5 kN shear must also be provided) |
| node 0 | uprights | ULS2 (imp +x) | 0.000 | PASS | uplift=0.00 kN vs anchor tension capacity 3.0 kN (EN 15512 9.10.4 min 3 kN tension + 5 kN shear must also be provided) |
| node 330000 | uprights | ULS2 (imp -x) | 0.000 | PASS | uplift=0.00 kN vs anchor tension capacity 3.0 kN (EN 15512 9.10.4 min 3 kN tension + 5 kN shear must also be provided) |
| node 0 | uprights | ULS2 (imp +y) | 0.000 | PASS | uplift=0.00 kN vs anchor tension capacity 3.0 kN (EN 15512 9.10.4 min 3 kN tension + 5 kN shear must also be provided) |
| node 10000 | uprights | ULS2 (imp -y) | 0.000 | PASS | uplift=0.00 kN vs anchor tension capacity 3.0 kN (EN 15512 9.10.4 min 3 kN tension + 5 kN shear must also be provided) |
| node 20000 | uprights | ULS3 (imp +x) | 0.000 | PASS | uplift=0.00 kN vs anchor tension capacity 3.0 kN (EN 15512 9.10.4 min 3 kN tension + 5 kN shear must also be provided) |
| node 20000 | uprights | ULS3 (imp -x) | 0.000 | PASS | uplift=0.00 kN vs anchor tension capacity 3.0 kN (EN 15512 9.10.4 min 3 kN tension + 5 kN shear must also be provided) |
| node 20000 | uprights | ULS3 (imp +y) | 0.000 | PASS | uplift=0.00 kN vs anchor tension capacity 3.0 kN (EN 15512 9.10.4 min 3 kN tension + 5 kN shear must also be provided) |
| node 310000 | uprights | ULS3 (imp -y) | 0.000 | PASS | uplift=0.00 kN vs anchor tension capacity 3.0 kN (EN 15512 9.10.4 min 3 kN tension + 5 kN shear must also be provided) |
| node 20000 | uprights | ULS4 acc X (imp +x) | 0.000 | PASS | uplift=0.00 kN vs anchor tension capacity 3.0 kN (EN 15512 9.10.4 min 3 kN tension + 5 kN shear must also be provided) |
| node 20000 | uprights | ULS5 acc Y (imp +y) | 0.000 | PASS | uplift=0.00 kN vs anchor tension capacity 3.0 kN (EN 15512 9.10.4 min 3 kN tension + 5 kN shear must also be provided) |

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
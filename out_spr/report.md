# EN 15512 design check report - SPR back-to-back module (non-seismic)

- Analysis: second-order (P-Delta) elastic, engine: OpenSees
- Sway imperfection: phi = 0.00495 rad (1/202), method = EHF
- Partial factors: gamma_M0 = 1.0, gamma_M1 = 1.0
- Members: 416, nodes: 272, height: 6500 mm

## Analysis cases

| case | kind | converged | sway X [mm] | sway Y [mm] | alpha_cr (est.) |
|---|---|---|---|---|---|
| ULS1 (imp +x) | ULS | yes | 17.36 | 0.37 | 2.85 |
| ULS1 (imp -x) | ULS | yes | 17.36 | 0.37 | 2.85 |
| ULS1 (imp +y) | ULS | yes | 1.26 | 1.03 | 136.72 |
| ULS1 (imp -y) | ULS | yes | 1.26 | 0.77 | 155.45 |
| ULS2 (imp +x) | ULS | yes | 37.76 | 0.43 | 2.89 |
| ULS2 (imp -x) | ULS | yes | 17.36 | 0.36 | 2.85 |
| ULS2 (imp +y) | ULS | yes | 21.63 | 1.21 | 3.11 |
| ULS2 (imp -y) | ULS | yes | 21.68 | 0.78 | 3.10 |
| ULS3 (imp +x) | ULS | yes | 17.39 | 1.10 | 2.87 |
| ULS3 (imp -x) | ULS | yes | 17.48 | 1.10 | 2.84 |
| ULS3 (imp +y) | ULS | yes | 1.33 | 1.56 | 463.87 |
| ULS3 (imp -y) | ULS | yes | 1.33 | 0.81 | 43.21 |
| SLS1 | SLS | yes | 0.90 | 0.26 | 232.81 |
| SLS2 | SLS | yes | 13.52 | 0.26 | 4.46 |

## Verdict: **PASS**

Governing: STRESS on member 293 (pallet beams) in 'ULS2 (imp +x)' - utilization **0.766**

## Utilization by level

Beams and connectors at the level; uprights and bracing of the storey below it.

| level | elevation [mm] | uprights | beams | connectors | bracing |
|---|---|---|---|---|---|
| 1 | 1500 | 0.706 PASS (BUCKLING, member 132) | 0.752 PASS (STRESS, member 257) | 0.710 PASS (CONNECTOR, member 257) | 0.045 PASS (STRESS, member 355) |
| 2 | 3000 | 0.574 PASS (BUCKLING, member 135) | 0.745 PASS (STRESS, member 269) | 0.676 PASS (CONNECTOR, member 273) | 0.026 PASS (STRESS, member 357) |
| 3 | 4500 | 0.405 PASS (BUCKLING, member 139) | 0.742 PASS (STRESS, member 281) | 0.631 PASS (CONNECTOR, member 289) | 0.022 PASS (STRESS, member 313) |
| 4 | 6000 | 0.408 PASS (BUCKLING, member 14) | 0.766 PASS (STRESS, member 293) | 0.586 PASS (CONNECTOR, member 297) | 0.023 PASS (STRESS, member 314) |

## STRESS checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 293 | pallet beams | ULS2 (imp +x) | 0.766 | PASS | N=-1.9 kN, My=0.00 kNm, Mz=3.64 kNm at x=1311 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS2 (imp -y) | 0.765 | PASS | N=-1.8 kN, My=0.00 kNm, Mz=3.64 kNm at x=1322 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS2 (imp +y) | 0.765 | PASS | N=-1.8 kN, My=-0.00 kNm, Mz=3.64 kNm at x=1321 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS2 (imp -x) | 0.763 | PASS | N=-1.8 kN, My=0.00 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS3 (imp +x) | 0.760 | PASS | N=-1.3 kN, My=0.01 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS3 (imp +x) | 0.760 | PASS | N=-1.3 kN, My=0.00 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS3 (imp +x) | 0.760 | PASS | N=-1.3 kN, My=0.00 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS3 (imp -y) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS3 (imp +x) | 0.760 | PASS | N=-1.3 kN, My=0.00 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS3 (imp -y) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS3 (imp -y) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS3 (imp -y) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 301 | pallet beams | ULS3 (imp -x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1368 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 304 | pallet beams | ULS2 (imp -x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1368 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 302 | pallet beams | ULS3 (imp -x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1368 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 304 | pallet beams | ULS3 (imp -x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1368 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 303 | pallet beams | ULS2 (imp -x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1368 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 303 | pallet beams | ULS3 (imp -x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1368 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 302 | pallet beams | ULS2 (imp -x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1368 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 304 | pallet beams | ULS1 (imp -x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1368 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS1 (imp +x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 303 | pallet beams | ULS1 (imp -x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1368 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS1 (imp +x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS1 (imp +x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 302 | pallet beams | ULS1 (imp -x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1368 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 301 | pallet beams | ULS1 (imp -x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1368 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS1 (imp +x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS2 (imp +x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS2 (imp +x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS2 (imp +x) | 0.759 | PASS | N=-1.3 kN, My=-0.00 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS3 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=0.00 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 301 | pallet beams | ULS3 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.00 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 304 | pallet beams | ULS2 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.00 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 302 | pallet beams | ULS3 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.00 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 304 | pallet beams | ULS3 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.00 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 303 | pallet beams | ULS2 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.00 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 303 | pallet beams | ULS3 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.00 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 302 | pallet beams | ULS2 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.00 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 304 | pallet beams | ULS1 (imp +y) | 0.758 | PASS | N=-1.2 kN, My=-0.00 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS1 (imp +y) | 0.758 | PASS | N=-1.2 kN, My=-0.00 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| ... | | | | | 4952 more rows omitted |

## BUCKLING checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 132 | uprights | ULS2 (imp +x) | 0.706 | PASS | Nc=56.7 kN, My=0.00 kNm, Mz=0.61 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 68 | uprights | ULS2 (imp +x) | 0.705 | PASS | Nc=56.7 kN, My=0.00 kNm, Mz=0.60 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 65 | uprights | ULS2 (imp +x) | 0.697 | PASS | Nc=57.2 kN, My=0.00 kNm, Mz=0.55 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 129 | uprights | ULS2 (imp +x) | 0.696 | PASS | Nc=57.1 kN, My=0.00 kNm, Mz=0.55 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 131 | uprights | ULS2 (imp +x) | 0.682 | PASS | Nc=56.9 kN, My=0.00 kNm, Mz=0.50 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 67 | uprights | ULS2 (imp +x) | 0.682 | PASS | Nc=56.9 kN, My=0.00 kNm, Mz=0.50 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS2 (imp -x) | 0.673 | PASS | Nc=57.0 kN, My=0.04 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS3 (imp -x) | 0.673 | PASS | Nc=57.0 kN, My=0.04 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS2 (imp -x) | 0.672 | PASS | Nc=57.0 kN, My=0.04 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS3 (imp +x) | 0.672 | PASS | Nc=57.0 kN, My=0.04 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 83 | uprights | ULS2 (imp -x) | 0.671 | PASS | Nc=57.0 kN, My=0.06 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 147 | uprights | ULS2 (imp -x) | 0.671 | PASS | Nc=57.0 kN, My=0.06 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS1 (imp +x) | 0.670 | PASS | Nc=56.9 kN, My=0.04 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS1 (imp -x) | 0.670 | PASS | Nc=56.9 kN, My=0.04 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS3 (imp +x) | 0.670 | PASS | Nc=56.8 kN, My=0.04 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 83 | uprights | ULS3 (imp -x) | 0.670 | PASS | Nc=57.0 kN, My=0.06 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS1 (imp +x) | 0.670 | PASS | Nc=56.9 kN, My=0.04 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS1 (imp -x) | 0.670 | PASS | Nc=56.9 kN, My=0.04 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS3 (imp -x) | 0.670 | PASS | Nc=56.8 kN, My=0.04 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 83 | uprights | ULS3 (imp +x) | 0.670 | PASS | Nc=57.0 kN, My=0.06 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 129 | uprights | ULS2 (imp -y) | 0.669 | PASS | Nc=59.1 kN, My=0.03 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 147 | uprights | ULS1 (imp +x) | 0.669 | PASS | Nc=56.9 kN, My=0.06 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 83 | uprights | ULS1 (imp -x) | 0.669 | PASS | Nc=56.9 kN, My=0.06 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 65 | uprights | ULS2 (imp -y) | 0.668 | PASS | Nc=59.1 kN, My=0.03 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 147 | uprights | ULS3 (imp +x) | 0.668 | PASS | Nc=56.8 kN, My=0.06 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 83 | uprights | ULS1 (imp +x) | 0.668 | PASS | Nc=56.9 kN, My=0.06 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 147 | uprights | ULS1 (imp -x) | 0.668 | PASS | Nc=56.9 kN, My=0.06 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 147 | uprights | ULS3 (imp -x) | 0.668 | PASS | Nc=56.8 kN, My=0.06 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 66 | uprights | ULS2 (imp +x) | 0.668 | PASS | Nc=56.9 kN, My=0.00 kNm, Mz=0.44 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS2 (imp +x) | 0.668 | PASS | Nc=56.7 kN, My=0.04 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 130 | uprights | ULS2 (imp +x) | 0.668 | PASS | Nc=56.9 kN, My=0.00 kNm, Mz=0.44 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS2 (imp +x) | 0.668 | PASS | Nc=56.8 kN, My=0.04 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 147 | uprights | ULS2 (imp +x) | 0.666 | PASS | Nc=56.7 kN, My=0.06 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 83 | uprights | ULS2 (imp +x) | 0.666 | PASS | Nc=56.8 kN, My=0.06 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 81 | uprights | ULS3 (imp -x) | 0.661 | PASS | Nc=56.7 kN, My=0.05 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 81 | uprights | ULS2 (imp -x) | 0.661 | PASS | Nc=56.7 kN, My=0.05 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 145 | uprights | ULS2 (imp -x) | 0.661 | PASS | Nc=56.7 kN, My=0.05 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 81 | uprights | ULS3 (imp +x) | 0.661 | PASS | Nc=56.7 kN, My=0.05 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 145 | uprights | ULS3 (imp -x) | 0.660 | PASS | Nc=56.5 kN, My=0.05 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 81 | uprights | ULS1 (imp +x) | 0.660 | PASS | Nc=56.6 kN, My=0.05 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| ... | | | | | 2733 more rows omitted |

## CONNECTOR checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 257 end j (z) | pallet beams | ULS2 (imp +x) | 0.710 | PASS | Mz,Ed=1.775 kNm, Mz,Rd=2.500 kNm |
| member 261 end j (z) | pallet beams | ULS2 (imp +x) | 0.708 | PASS | Mz,Ed=1.771 kNm, Mz,Rd=2.500 kNm |
| member 265 end j (z) | pallet beams | ULS2 (imp +x) | 0.693 | PASS | Mz,Ed=1.733 kNm, Mz,Rd=2.500 kNm |
| member 273 end j (z) | pallet beams | ULS2 (imp +x) | 0.676 | PASS | Mz,Ed=1.690 kNm, Mz,Rd=2.500 kNm |
| member 269 end j (z) | pallet beams | ULS2 (imp +x) | 0.671 | PASS | Mz,Ed=1.677 kNm, Mz,Rd=2.500 kNm |
| member 277 end j (z) | pallet beams | ULS2 (imp +x) | 0.668 | PASS | Mz,Ed=1.671 kNm, Mz,Rd=2.500 kNm |
| member 289 end j (z) | pallet beams | ULS2 (imp +x) | 0.631 | PASS | Mz,Ed=1.578 kNm, Mz,Rd=2.500 kNm |
| member 285 end j (z) | pallet beams | ULS2 (imp +x) | 0.630 | PASS | Mz,Ed=1.574 kNm, Mz,Rd=2.500 kNm |
| member 281 end j (z) | pallet beams | ULS2 (imp +x) | 0.620 | PASS | Mz,Ed=1.550 kNm, Mz,Rd=2.500 kNm |
| member 257 end j (z) | pallet beams | ULS2 (imp -y) | 0.607 | PASS | Mz,Ed=1.517 kNm, Mz,Rd=2.500 kNm |
| member 261 end j (z) | pallet beams | ULS2 (imp -y) | 0.607 | PASS | Mz,Ed=1.516 kNm, Mz,Rd=2.500 kNm |
| member 257 end j (z) | pallet beams | ULS2 (imp +y) | 0.606 | PASS | Mz,Ed=1.516 kNm, Mz,Rd=2.500 kNm |
| member 261 end j (z) | pallet beams | ULS2 (imp +y) | 0.606 | PASS | Mz,Ed=1.514 kNm, Mz,Rd=2.500 kNm |
| member 266 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.504 kNm, Mz,Rd=2.500 kNm |
| member 258 end j (z) | pallet beams | ULS3 (imp +x) | 0.601 | PASS | Mz,Ed=1.503 kNm, Mz,Rd=2.500 kNm |
| member 268 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.503 kNm, Mz,Rd=2.500 kNm |
| member 262 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 260 end j (z) | pallet beams | ULS3 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 267 end i (z) | pallet beams | ULS2 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 258 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 266 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 259 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 267 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 266 end i (z) | pallet beams | ULS2 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 259 end j (z) | pallet beams | ULS2 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 260 end j (z) | pallet beams | ULS2 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 258 end j (z) | pallet beams | ULS2 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 264 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 257 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 265 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 268 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 260 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 268 end i (z) | pallet beams | ULS2 (imp -x) | 0.601 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 259 end j (z) | pallet beams | ULS3 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 262 end j (z) | pallet beams | ULS3 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 263 end i (z) | pallet beams | ULS2 (imp -x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 263 end i (z) | pallet beams | ULS1 (imp -x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 263 end j (z) | pallet beams | ULS1 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 262 end j (z) | pallet beams | ULS1 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 262 end i (z) | pallet beams | ULS1 (imp -x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| ... | | | | | 1112 more rows omitted |

## DEFLECTION checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 293 | pallet beams | SLS2 | 0.649 | PASS | defl=8.77 mm, limit=L/200=13.50 mm |
| member 294 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 295 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 304 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 295 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 303 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 294 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 302 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 296 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 304 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 301 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 293 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 303 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 296 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 302 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 301 | pallet beams | SLS2 | 0.646 | PASS | defl=8.71 mm, limit=L/200=13.50 mm |
| member 257 | pallet beams | SLS2 | 0.639 | PASS | defl=8.63 mm, limit=L/200=13.50 mm |
| member 258 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 268 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 260 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 268 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 260 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 266 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 258 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 259 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 259 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 267 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 267 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 266 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 257 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 265 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 269 | pallet beams | SLS2 | 0.637 | PASS | defl=8.60 mm, limit=L/200=13.50 mm |
| member 265 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 270 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 280 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 271 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 271 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 279 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 272 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 280 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| ... | | | | | 56 more rows omitted |

## SWAY checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| frame X (down-aisle) | - | SLS2 | 0.416 | PASS | max sway=13.52 mm, limit=H/200=32.50 mm (H=6500 mm) |
| frame X (down-aisle) | - | SLS1 | 0.028 | PASS | max sway=0.90 mm, limit=H/200=32.50 mm (H=6500 mm) |
| frame Y (cross-aisle) | - | SLS2 | 0.008 | PASS | max sway=0.26 mm, limit=H/200=32.50 mm (H=6500 mm) |
| frame Y (cross-aisle) | - | SLS1 | 0.008 | PASS | max sway=0.26 mm, limit=H/200=32.50 mm (H=6500 mm) |

## ALPHA_CR checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| frame | - | ULS3 (imp -x) | 1.058 | INFO | estimated alpha_cr=2.84, sway amplification=1.545 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS1 (imp +x) | 1.052 | INFO | estimated alpha_cr=2.85, sway amplification=1.540 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS1 (imp -x) | 1.052 | INFO | estimated alpha_cr=2.85, sway amplification=1.540 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS2 (imp -x) | 1.052 | INFO | estimated alpha_cr=2.85, sway amplification=1.540 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS3 (imp +x) | 1.045 | INFO | estimated alpha_cr=2.87, sway amplification=1.535 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS2 (imp +x) | 1.038 | INFO | estimated alpha_cr=2.89, sway amplification=1.529 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS2 (imp -y) | 0.968 | INFO | estimated alpha_cr=3.10, sway amplification=1.477 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS2 (imp +y) | 0.964 | INFO | estimated alpha_cr=3.11, sway amplification=1.474 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS3 (imp -y) | 0.069 | INFO | estimated alpha_cr=43.21, sway amplification=1.024 |
| frame | - | ULS1 (imp +y) | 0.022 | INFO | estimated alpha_cr=136.72, sway amplification=1.007 |
| frame | - | ULS1 (imp -y) | 0.019 | INFO | estimated alpha_cr=155.45, sway amplification=1.006 |
| frame | - | ULS3 (imp +y) | 0.006 | INFO | estimated alpha_cr=463.87, sway amplification=1.002 |

---
*Defaults follow EN 15512 with EN 1993 buckling curves; verify all factors, imperfection parameters and section/connector test values against the edition of the standard applicable to your project.*
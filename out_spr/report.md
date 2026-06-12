# EN 15512 design check report - SPR back-to-back module (non-seismic)

- Analysis: second-order (P-Delta) elastic, engine: OpenSees
- Sway imperfection: phi = 0.00495 rad (1/202), method = EHF
- Partial factors: gamma_M0 = 1.0, gamma_M1 = 1.0
- Members: 416, nodes: 272, height: 6500 mm

## Analysis cases

| case | kind | converged | sway X [mm] | sway Y [mm] | alpha_cr (est.) |
|---|---|---|---|---|---|
| ULS1 (imp +x) | ULS | yes | 17.35 | 0.35 | 2.85 |
| ULS1 (imp -x) | ULS | yes | 17.35 | 0.35 | 2.85 |
| ULS1 (imp +y) | ULS | yes | 1.26 | 2.54 | 12.39 |
| ULS1 (imp -y) | ULS | yes | 1.26 | 2.35 | 12.87 |
| ULS2 (imp +x) | ULS | yes | 37.77 | 0.42 | 2.89 |
| ULS2 (imp -x) | ULS | yes | 17.35 | 0.35 | 2.85 |
| ULS2 (imp +y) | ULS | yes | 21.65 | 2.75 | 3.12 |
| ULS2 (imp -y) | ULS | yes | 21.70 | 2.35 | 3.11 |
| ULS3 (imp +x) | ULS | yes | 17.38 | 2.51 | 2.92 |
| ULS3 (imp -x) | ULS | yes | 17.47 | 2.51 | 2.84 |
| ULS3 (imp +y) | ULS | yes | 1.33 | 3.88 | 27.14 |
| ULS3 (imp -y) | ULS | yes | 1.33 | 2.45 | 12.93 |
| SLS1 | SLS | yes | 0.90 | 0.25 | 228.78 |
| SLS2 | SLS | yes | 13.52 | 0.25 | 4.45 |

## Verdict: **FAIL**

Governing: BASEPLATE on node 1000 thickness (-) in 'ULS1 (imp +x)' - utilization **2.302**

## Utilization by level

Beams and connectors at the level; uprights and bracing of the storey below it.

| level | elevation [mm] | uprights | beams | connectors | bracing |
|---|---|---|---|---|---|
| 1 | 1500 | 0.707 PASS (BUCKLING, member 132) | 0.752 PASS (STRESS, member 257) | 0.710 PASS (CONNECTOR, member 257) | 0.291 PASS (BRACE_BOLT, member 344) |
| 2 | 3000 | 0.574 PASS (BUCKLING, member 135) | 0.745 PASS (STRESS, member 269) | 0.676 PASS (CONNECTOR, member 273) | 0.229 PASS (BRACE_BOLT, member 321) |
| 3 | 4500 | 0.406 PASS (BUCKLING, member 139) | 0.742 PASS (STRESS, member 281) | 0.631 PASS (CONNECTOR, member 289) | 0.191 PASS (BRACE_BOLT, member 312) |
| 4 | 6000 | 0.410 PASS (BUCKLING, member 14) | 0.766 PASS (STRESS, member 293) | 0.586 PASS (CONNECTOR, member 297) | 0.189 PASS (BRACE_BOLT, member 314) |

## STRESS checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 293 | pallet beams | ULS2 (imp -y) | 0.766 | PASS | N=-1.8 kN, My=0.01 kNm, Mz=3.64 kNm at x=1322 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS2 (imp +y) | 0.766 | PASS | N=-1.8 kN, My=-0.01 kNm, Mz=3.64 kNm at x=1321 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS2 (imp +x) | 0.766 | PASS | N=-1.9 kN, My=0.00 kNm, Mz=3.64 kNm at x=1311 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS2 (imp -x) | 0.763 | PASS | N=-1.8 kN, My=0.00 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS3 (imp -y) | 0.762 | PASS | N=-1.2 kN, My=0.02 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS3 (imp -y) | 0.762 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS3 (imp -y) | 0.762 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS3 (imp -y) | 0.762 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS3 (imp +x) | 0.762 | PASS | N=-1.3 kN, My=0.01 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS3 (imp +x) | 0.761 | PASS | N=-1.3 kN, My=0.01 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS3 (imp +x) | 0.761 | PASS | N=-1.3 kN, My=0.01 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS3 (imp +x) | 0.761 | PASS | N=-1.3 kN, My=0.01 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS3 (imp -x) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1351 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 303 | pallet beams | ULS3 (imp -y) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 304 | pallet beams | ULS3 (imp -y) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 302 | pallet beams | ULS3 (imp -y) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 304 | pallet beams | ULS2 (imp +y) | 0.760 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 301 | pallet beams | ULS3 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 302 | pallet beams | ULS2 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 303 | pallet beams | ULS2 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS3 (imp -x) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1351 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS3 (imp -x) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1351 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 304 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 302 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 303 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 301 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS2 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS2 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS2 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS2 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS3 (imp -x) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1351 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS2 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS2 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 301 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.00 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.00 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 303 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.00 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| ... | | | | | 4952 more rows omitted |

## BUCKLING checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 132 | uprights | ULS2 (imp +x) | 0.707 | PASS | Nc=56.7 kN, My=0.00 kNm, Mz=0.61 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 68 | uprights | ULS2 (imp +x) | 0.706 | PASS | Nc=56.8 kN, My=0.00 kNm, Mz=0.60 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 65 | uprights | ULS2 (imp +x) | 0.696 | PASS | Nc=56.9 kN, My=0.01 kNm, Mz=0.55 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 129 | uprights | ULS2 (imp +x) | 0.696 | PASS | Nc=56.8 kN, My=0.01 kNm, Mz=0.55 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 129 | uprights | ULS2 (imp -y) | 0.690 | PASS | Nc=58.9 kN, My=0.06 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 65 | uprights | ULS2 (imp -y) | 0.690 | PASS | Nc=58.9 kN, My=0.06 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 131 | uprights | ULS2 (imp +x) | 0.681 | PASS | Nc=56.7 kN, My=0.00 kNm, Mz=0.50 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 67 | uprights | ULS2 (imp +x) | 0.681 | PASS | Nc=56.8 kN, My=0.00 kNm, Mz=0.50 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 66 | uprights | ULS2 (imp +x) | 0.667 | PASS | Nc=56.8 kN, My=0.00 kNm, Mz=0.44 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 130 | uprights | ULS2 (imp +x) | 0.667 | PASS | Nc=56.7 kN, My=0.00 kNm, Mz=0.44 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS3 (imp -x) | 0.654 | PASS | Nc=57.1 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS3 (imp +x) | 0.654 | PASS | Nc=57.1 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS2 (imp -x) | 0.652 | PASS | Nc=56.9 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 83 | uprights | ULS3 (imp -x) | 0.652 | PASS | Nc=57.1 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS2 (imp -x) | 0.651 | PASS | Nc=56.9 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 83 | uprights | ULS3 (imp +x) | 0.651 | PASS | Nc=57.1 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS3 (imp +x) | 0.651 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS1 (imp +x) | 0.651 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS1 (imp -x) | 0.651 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS3 (imp -x) | 0.651 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 83 | uprights | ULS2 (imp -x) | 0.650 | PASS | Nc=56.9 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS1 (imp +x) | 0.650 | PASS | Nc=56.9 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS1 (imp -x) | 0.650 | PASS | Nc=56.9 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 147 | uprights | ULS2 (imp -x) | 0.650 | PASS | Nc=56.9 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS2 (imp +x) | 0.649 | PASS | Nc=56.8 kN, My=0.01 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS2 (imp +x) | 0.649 | PASS | Nc=56.8 kN, My=0.01 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 116 | uprights | ULS3 (imp -x) | 0.649 | PASS | Nc=56.9 kN, My=0.01 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 147 | uprights | ULS1 (imp +x) | 0.649 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 83 | uprights | ULS1 (imp -x) | 0.649 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 116 | uprights | ULS3 (imp +x) | 0.648 | PASS | Nc=56.9 kN, My=0.01 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 83 | uprights | ULS1 (imp +x) | 0.648 | PASS | Nc=56.9 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 147 | uprights | ULS1 (imp -x) | 0.648 | PASS | Nc=56.9 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 147 | uprights | ULS3 (imp +x) | 0.648 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 147 | uprights | ULS3 (imp -x) | 0.648 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 113 | uprights | ULS3 (imp -x) | 0.648 | PASS | Nc=57.1 kN, My=0.02 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 113 | uprights | ULS3 (imp +x) | 0.648 | PASS | Nc=57.1 kN, My=0.02 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 180 | uprights | ULS2 (imp +x) | 0.648 | PASS | Nc=56.7 kN, My=0.01 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 147 | uprights | ULS2 (imp +x) | 0.647 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 116 | uprights | ULS2 (imp +x) | 0.647 | PASS | Nc=56.8 kN, My=0.01 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 180 | uprights | ULS1 (imp +x) | 0.647 | PASS | Nc=56.7 kN, My=0.01 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| ... | | | | | 2719 more rows omitted |

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
| member 261 end j (z) | pallet beams | ULS2 (imp -y) | 0.607 | PASS | Mz,Ed=1.517 kNm, Mz,Rd=2.500 kNm |
| member 257 end j (z) | pallet beams | ULS2 (imp +y) | 0.606 | PASS | Mz,Ed=1.516 kNm, Mz,Rd=2.500 kNm |
| member 261 end j (z) | pallet beams | ULS2 (imp +y) | 0.606 | PASS | Mz,Ed=1.514 kNm, Mz,Rd=2.500 kNm |
| member 266 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.503 kNm, Mz,Rd=2.500 kNm |
| member 268 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.503 kNm, Mz,Rd=2.500 kNm |
| member 258 end j (z) | pallet beams | ULS3 (imp +x) | 0.601 | PASS | Mz,Ed=1.503 kNm, Mz,Rd=2.500 kNm |
| member 260 end j (z) | pallet beams | ULS3 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 262 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 267 end i (z) | pallet beams | ULS2 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 266 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 258 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 267 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 259 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 259 end j (z) | pallet beams | ULS2 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 266 end i (z) | pallet beams | ULS2 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 258 end j (z) | pallet beams | ULS2 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 260 end j (z) | pallet beams | ULS2 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 268 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 260 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 265 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 257 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 264 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 268 end i (z) | pallet beams | ULS2 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 259 end j (z) | pallet beams | ULS3 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 262 end j (z) | pallet beams | ULS3 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 263 end i (z) | pallet beams | ULS2 (imp -x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 257 end j (z) | pallet beams | ULS3 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 262 end j (z) | pallet beams | ULS1 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 262 end i (z) | pallet beams | ULS1 (imp -x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 263 end j (z) | pallet beams | ULS1 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| ... | | | | | 1112 more rows omitted |

## BRACE_BOLT checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 344 | bracing | ULS3 (imp +y) | 0.291 | PASS | N=0.91 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 355 | bracing | ULS3 (imp -y) | 0.282 | PASS | N=0.88 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 355 | bracing | ULS2 (imp -y) | 0.274 | PASS | N=0.86 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 320 | bracing | ULS3 (imp +y) | 0.274 | PASS | N=0.86 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 331 | bracing | ULS1 (imp -y) | 0.274 | PASS | N=0.86 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 355 | bracing | ULS1 (imp -y) | 0.274 | PASS | N=0.86 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 331 | bracing | ULS2 (imp -y) | 0.273 | PASS | N=0.86 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 344 | bracing | ULS2 (imp +y) | 0.268 | PASS | N=0.84 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 344 | bracing | ULS1 (imp +y) | 0.267 | PASS | N=0.84 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 368 | bracing | ULS1 (imp +y) | 0.267 | PASS | N=0.84 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 368 | bracing | ULS2 (imp +y) | 0.267 | PASS | N=0.84 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 343 | bracing | ULS3 (imp +y) | 0.263 | PASS | N=0.82 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 368 | bracing | ULS3 (imp +y) | 0.259 | PASS | N=0.81 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 319 | bracing | ULS3 (imp +y) | 0.253 | PASS | N=0.79 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 331 | bracing | ULS3 (imp -y) | 0.251 | PASS | N=0.79 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 308 | bracing | ULS3 (imp +y) | 0.244 | PASS | N=0.76 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 343 | bracing | ULS2 (imp +y) | 0.241 | PASS | N=0.76 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 343 | bracing | ULS1 (imp +y) | 0.241 | PASS | N=0.75 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 367 | bracing | ULS1 (imp +y) | 0.241 | PASS | N=0.75 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 367 | bracing | ULS2 (imp +y) | 0.240 | PASS | N=0.75 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 332 | bracing | ULS3 (imp +y) | 0.237 | PASS | N=0.74 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 356 | bracing | ULS3 (imp -y) | 0.235 | PASS | N=0.74 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 367 | bracing | ULS3 (imp +y) | 0.232 | PASS | N=0.73 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 321 | bracing | ULS3 (imp +y) | 0.229 | PASS | N=0.72 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 356 | bracing | ULS2 (imp -y) | 0.228 | PASS | N=0.71 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 332 | bracing | ULS1 (imp -y) | 0.227 | PASS | N=0.71 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 356 | bracing | ULS1 (imp -y) | 0.227 | PASS | N=0.71 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 332 | bracing | ULS2 (imp -y) | 0.226 | PASS | N=0.71 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 367 | bracing | ULS3 (imp -y) | 0.226 | PASS | N=0.71 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 309 | bracing | ULS3 (imp +y) | 0.222 | PASS | N=0.70 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 367 | bracing | ULS2 (imp -y) | 0.218 | PASS | N=0.68 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 343 | bracing | ULS1 (imp -y) | 0.218 | PASS | N=0.68 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 367 | bracing | ULS1 (imp -y) | 0.218 | PASS | N=0.68 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 310 | bracing | ULS3 (imp +y) | 0.217 | PASS | N=0.68 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 343 | bracing | ULS2 (imp -y) | 0.217 | PASS | N=0.68 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 332 | bracing | ULS2 (imp +y) | 0.213 | PASS | N=0.67 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 307 | bracing | ULS3 (imp +y) | 0.213 | PASS | N=0.67 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 332 | bracing | ULS1 (imp +y) | 0.212 | PASS | N=0.67 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 356 | bracing | ULS1 (imp +y) | 0.212 | PASS | N=0.67 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 356 | bracing | ULS2 (imp +y) | 0.212 | PASS | N=0.66 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| ... | | | | | 1304 more rows omitted |

## BASEPLATE checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| node 1000 thickness | - | ULS1 (imp +x) | 2.302 | FAIL | t=6.0 mm vs required 13.8 mm (projection c=33.5 mm, fy=250) |
| node 2000 thickness | - | ULS1 (imp -x) | 2.302 | FAIL | t=6.0 mm vs required 13.8 mm (projection c=33.5 mm, fy=250) |
| node 2300 thickness | - | ULS1 (imp +y) | 2.302 | FAIL | t=6.0 mm vs required 13.8 mm (projection c=33.5 mm, fy=250) |
| node 1000 thickness | - | ULS1 (imp -y) | 2.302 | FAIL | t=6.0 mm vs required 13.8 mm (projection c=33.5 mm, fy=250) |
| node 1000 thickness | - | ULS2 (imp +x) | 2.302 | FAIL | t=6.0 mm vs required 13.8 mm (projection c=33.5 mm, fy=250) |
| node 2200 thickness | - | ULS2 (imp -x) | 2.302 | FAIL | t=6.0 mm vs required 13.8 mm (projection c=33.5 mm, fy=250) |
| node 1300 thickness | - | ULS2 (imp +y) | 2.302 | FAIL | t=6.0 mm vs required 13.8 mm (projection c=33.5 mm, fy=250) |
| node 1000 thickness | - | ULS2 (imp -y) | 2.302 | FAIL | t=6.0 mm vs required 13.8 mm (projection c=33.5 mm, fy=250) |
| node 1300 thickness | - | ULS3 (imp +x) | 2.302 | FAIL | t=6.0 mm vs required 13.8 mm (projection c=33.5 mm, fy=250) |
| node 1300 thickness | - | ULS3 (imp -x) | 2.302 | FAIL | t=6.0 mm vs required 13.8 mm (projection c=33.5 mm, fy=250) |
| node 1300 thickness | - | ULS3 (imp +y) | 2.302 | FAIL | t=6.0 mm vs required 13.8 mm (projection c=33.5 mm, fy=250) |
| node 2000 thickness | - | ULS3 (imp -y) | 2.302 | FAIL | t=6.0 mm vs required 13.8 mm (projection c=33.5 mm, fy=250) |
| node 1300 bearing | - | ULS3 (imp +y) | 0.214 | PASS | N=59.2 kN vs 150x130 plate, f_jd=14.17 MPa; min plate 120x63 mm, t>=4.0 mm (N=59.2 kN at node 1300, f_jd=14.17 MPa, c=0.0 mm) |
| node 2000 bearing | - | ULS3 (imp -y) | 0.214 | PASS | N=59.0 kN vs 150x130 plate, f_jd=14.17 MPa; min plate 120x63 mm, t>=4.0 mm (N=59.0 kN at node 2000, f_jd=14.17 MPa, c=0.0 mm) |
| node 1000 bearing | - | ULS2 (imp -y) | 0.213 | PASS | N=58.9 kN vs 150x130 plate, f_jd=14.17 MPa; min plate 120x63 mm, t>=4.0 mm (N=58.9 kN at node 1000, f_jd=14.17 MPa, c=0.0 mm) |
| node 1000 bearing | - | ULS1 (imp -y) | 0.213 | PASS | N=58.9 kN vs 150x130 plate, f_jd=14.17 MPa; min plate 120x63 mm, t>=4.0 mm (N=58.9 kN at node 1000, f_jd=14.17 MPa, c=0.0 mm) |
| node 1300 bearing | - | ULS2 (imp +y) | 0.213 | PASS | N=58.9 kN vs 150x130 plate, f_jd=14.17 MPa; min plate 120x63 mm, t>=4.0 mm (N=58.9 kN at node 1300, f_jd=14.17 MPa, c=0.0 mm) |
| node 2300 bearing | - | ULS1 (imp +y) | 0.213 | PASS | N=58.9 kN vs 150x130 plate, f_jd=14.17 MPa; min plate 120x63 mm, t>=4.0 mm (N=58.9 kN at node 2300, f_jd=14.17 MPa, c=0.0 mm) |
| node 1300 bearing | - | ULS3 (imp +x) | 0.207 | PASS | N=57.1 kN vs 150x130 plate, f_jd=14.17 MPa; min plate 120x63 mm, t>=4.0 mm (N=57.1 kN at node 1300, f_jd=14.17 MPa, c=0.0 mm) |
| node 1300 bearing | - | ULS3 (imp -x) | 0.207 | PASS | N=57.1 kN vs 150x130 plate, f_jd=14.17 MPa; min plate 120x63 mm, t>=4.0 mm (N=57.1 kN at node 1300, f_jd=14.17 MPa, c=0.0 mm) |
| node 1000 bearing | - | ULS2 (imp +x) | 0.206 | PASS | N=56.9 kN vs 150x130 plate, f_jd=14.17 MPa; min plate 120x63 mm, t>=4.0 mm (N=56.9 kN at node 1000, f_jd=14.17 MPa, c=0.0 mm) |
| node 2200 bearing | - | ULS2 (imp -x) | 0.206 | PASS | N=56.9 kN vs 150x130 plate, f_jd=14.17 MPa; min plate 120x63 mm, t>=4.0 mm (N=56.9 kN at node 2200, f_jd=14.17 MPa, c=0.0 mm) |
| node 2000 bearing | - | ULS1 (imp -x) | 0.206 | PASS | N=56.8 kN vs 150x130 plate, f_jd=14.17 MPa; min plate 120x63 mm, t>=4.0 mm (N=56.8 kN at node 2000, f_jd=14.17 MPa, c=0.0 mm) |
| node 1000 bearing | - | ULS1 (imp +x) | 0.206 | PASS | N=56.8 kN vs 150x130 plate, f_jd=14.17 MPa; min plate 120x63 mm, t>=4.0 mm (N=56.8 kN at node 1000, f_jd=14.17 MPa, c=0.0 mm) |

## DEFLECTION checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 293 | pallet beams | SLS2 | 0.649 | PASS | defl=8.77 mm, limit=L/200=13.50 mm |
| member 294 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 295 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 304 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 303 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 295 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 294 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 302 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 303 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 296 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 304 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 293 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 301 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 296 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 302 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 301 | pallet beams | SLS2 | 0.646 | PASS | defl=8.71 mm, limit=L/200=13.50 mm |
| member 257 | pallet beams | SLS2 | 0.639 | PASS | defl=8.63 mm, limit=L/200=13.50 mm |
| member 258 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 268 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 260 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 268 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 260 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 258 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 266 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 259 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 259 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 267 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 267 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 257 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 265 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 266 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 269 | pallet beams | SLS2 | 0.637 | PASS | defl=8.60 mm, limit=L/200=13.50 mm |
| member 265 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 270 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 280 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 272 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 280 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 271 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 271 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 279 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| ... | | | | | 56 more rows omitted |

## SWAY checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| frame X (down-aisle) | - | SLS2 | 0.416 | PASS | max sway=13.52 mm, limit=H/200=32.50 mm (H=6500 mm) |
| frame X (down-aisle) | - | SLS1 | 0.028 | PASS | max sway=0.90 mm, limit=H/200=32.50 mm (H=6500 mm) |
| frame Y (cross-aisle) | - | SLS2 | 0.008 | PASS | max sway=0.25 mm, limit=H/200=32.50 mm (H=6500 mm) |
| frame Y (cross-aisle) | - | SLS1 | 0.008 | PASS | max sway=0.25 mm, limit=H/200=32.50 mm (H=6500 mm) |

## ALPHA_CR checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| frame | - | ULS3 (imp -x) | 1.057 | INFO | estimated alpha_cr=2.84, sway amplification=1.544 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS1 (imp -x) | 1.051 | INFO | estimated alpha_cr=2.85, sway amplification=1.539 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS1 (imp +x) | 1.051 | INFO | estimated alpha_cr=2.85, sway amplification=1.539 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS2 (imp -x) | 1.051 | INFO | estimated alpha_cr=2.85, sway amplification=1.539 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS2 (imp +x) | 1.038 | INFO | estimated alpha_cr=2.89, sway amplification=1.529 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS3 (imp +x) | 1.027 | INFO | estimated alpha_cr=2.92, sway amplification=1.521 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS2 (imp -y) | 0.966 | INFO | estimated alpha_cr=3.11, sway amplification=1.475 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS2 (imp +y) | 0.963 | INFO | estimated alpha_cr=3.12, sway amplification=1.473 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS1 (imp +y) | 0.242 | INFO | estimated alpha_cr=12.39, sway amplification=1.088 |
| frame | - | ULS1 (imp -y) | 0.233 | INFO | estimated alpha_cr=12.87, sway amplification=1.084 |
| frame | - | ULS3 (imp -y) | 0.232 | INFO | estimated alpha_cr=12.93, sway amplification=1.084 |
| frame | - | ULS3 (imp +y) | 0.111 | INFO | estimated alpha_cr=27.14, sway amplification=1.038 |

---
*Defaults follow EN 15512 with EN 1993 buckling curves; verify all factors, imperfection parameters and section/connector test values against the edition of the standard applicable to your project.*
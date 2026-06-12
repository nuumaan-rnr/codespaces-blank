# EN 15512 design check report - SPR back-to-back module (non-seismic)

- Analysis: second-order (P-Delta) elastic, engine: OpenSees
- Sway imperfection: phi = 0.00495 rad (1/202), method = EHF
- Partial factors: gamma_M0 = 1.0, gamma_M1 = 1.0
- Members: 416, nodes: 272, height: 6500 mm

## Analysis cases

| case | kind | converged | sway X [mm] | sway Y [mm] | alpha_cr (est.) |
|---|---|---|---|---|---|
| ULS1 (imp +x) | ULS | yes | 17.35 | 0.18 | 2.85 |
| ULS1 (imp -x) | ULS | yes | 17.35 | 0.18 | 2.85 |
| ULS1 (imp +y) | ULS | yes | 1.26 | 2.47 | 12.70 |
| ULS1 (imp -y) | ULS | yes | 1.26 | 2.47 | 12.70 |
| ULS2 (imp +x) | ULS | yes | 37.78 | 0.36 | 2.89 |
| ULS2 (imp -x) | ULS | yes | 17.35 | 0.20 | 2.85 |
| ULS2 (imp +y) | ULS | yes | 21.66 | 2.62 | 3.11 |
| ULS2 (imp -y) | ULS | yes | 21.71 | 2.48 | 3.10 |
| ULS3 (imp +x) | ULS | yes | 17.37 | 2.45 | 2.92 |
| ULS3 (imp -x) | ULS | yes | 17.47 | 2.45 | 2.84 |
| ULS3 (imp +y) | ULS | yes | 1.33 | 3.82 | 27.56 |
| ULS3 (imp -y) | ULS | yes | 1.33 | 2.58 | 12.74 |
| SLS1 | SLS | yes | 0.90 | 0.13 | 235.64 |
| SLS2 | SLS | yes | 13.53 | 0.13 | 4.45 |

## Verdict: **PASS**

Governing: BASEPLATE on node 1000 (-) in 'ULS2 (imp +x)' - utilization **0.948**

## Utilization by level

Beams and connectors at the level; uprights and bracing of the storey below it.

| level | elevation [mm] | uprights | beams | connectors | bracing |
|---|---|---|---|---|---|
| 1 | 1500 | 0.707 PASS (BUCKLING, member 132) | 0.752 PASS (STRESS, member 257) | 0.710 PASS (CONNECTOR, member 257) | 0.327 PASS (BRACE_BOLT, member 343) |
| 2 | 3000 | 0.575 PASS (BUCKLING, member 135) | 0.745 PASS (STRESS, member 269) | 0.676 PASS (CONNECTOR, member 273) | 0.239 PASS (BRACE_BOLT, member 321) |
| 3 | 4500 | 0.406 PASS (BUCKLING, member 139) | 0.742 PASS (STRESS, member 281) | 0.631 PASS (CONNECTOR, member 289) | 0.194 PASS (BRACE_BOLT, member 324) |
| 4 | 6000 | 0.410 PASS (BUCKLING, member 14) | 0.766 PASS (STRESS, member 293) | 0.586 PASS (CONNECTOR, member 297) | 0.194 PASS (BRACE_BOLT, member 314) |

## STRESS checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 293 | pallet beams | ULS2 (imp -y) | 0.766 | PASS | N=-1.8 kN, My=0.01 kNm, Mz=3.64 kNm at x=1322 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS2 (imp +y) | 0.766 | PASS | N=-1.8 kN, My=-0.00 kNm, Mz=3.64 kNm at x=1321 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS2 (imp +x) | 0.766 | PASS | N=-1.9 kN, My=0.00 kNm, Mz=3.64 kNm at x=1311 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS2 (imp -x) | 0.763 | PASS | N=-1.8 kN, My=0.00 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS3 (imp -y) | 0.763 | PASS | N=-1.2 kN, My=0.02 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS3 (imp -y) | 0.762 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS3 (imp -y) | 0.762 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS3 (imp -y) | 0.762 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS3 (imp +x) | 0.762 | PASS | N=-1.3 kN, My=0.01 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS3 (imp +x) | 0.762 | PASS | N=-1.3 kN, My=0.01 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS3 (imp +x) | 0.762 | PASS | N=-1.3 kN, My=0.01 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS3 (imp +x) | 0.761 | PASS | N=-1.3 kN, My=0.01 kNm, Mz=3.63 kNm at x=1332 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS3 (imp -x) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1351 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 303 | pallet beams | ULS3 (imp -y) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 304 | pallet beams | ULS3 (imp -y) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 302 | pallet beams | ULS3 (imp -y) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 301 | pallet beams | ULS3 (imp -y) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS3 (imp -x) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1351 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS3 (imp -x) | 0.760 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1351 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 304 | pallet beams | ULS2 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS2 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 302 | pallet beams | ULS2 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 303 | pallet beams | ULS2 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS3 (imp -x) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1351 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS2 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS2 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 304 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 301 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 302 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1343 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 303 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1357 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 294 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 295 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 303 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 302 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1358 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 296 | pallet beams | ULS1 (imp -y) | 0.759 | PASS | N=-1.2 kN, My=0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| member 293 | pallet beams | ULS1 (imp +y) | 0.759 | PASS | N=-1.2 kN, My=-0.01 kNm, Mz=3.62 kNm at x=1342 mm; N_Rd=170.6 kN, My_Rd=3.14 kNm, Mz_Rd=4.83 kNm |
| ... | | | | | 4952 more rows omitted |

## BUCKLING checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 132 | uprights | ULS2 (imp +x) | 0.707 | PASS | Nc=56.7 kN, My=0.00 kNm, Mz=0.61 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 68 | uprights | ULS2 (imp +x) | 0.707 | PASS | Nc=56.8 kN, My=0.00 kNm, Mz=0.60 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 65 | uprights | ULS2 (imp +x) | 0.702 | PASS | Nc=57.0 kN, My=0.01 kNm, Mz=0.55 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 129 | uprights | ULS2 (imp +x) | 0.702 | PASS | Nc=56.9 kN, My=0.01 kNm, Mz=0.55 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 129 | uprights | ULS2 (imp -y) | 0.697 | PASS | Nc=59.0 kN, My=0.06 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 65 | uprights | ULS2 (imp -y) | 0.696 | PASS | Nc=59.0 kN, My=0.06 kNm, Mz=0.28 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 131 | uprights | ULS2 (imp +x) | 0.682 | PASS | Nc=56.8 kN, My=0.00 kNm, Mz=0.50 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 67 | uprights | ULS2 (imp +x) | 0.682 | PASS | Nc=56.9 kN, My=0.00 kNm, Mz=0.50 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 66 | uprights | ULS2 (imp +x) | 0.669 | PASS | Nc=56.9 kN, My=0.00 kNm, Mz=0.44 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 130 | uprights | ULS2 (imp +x) | 0.669 | PASS | Nc=56.8 kN, My=0.00 kNm, Mz=0.44 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS3 (imp -x) | 0.661 | PASS | Nc=57.0 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS3 (imp +x) | 0.660 | PASS | Nc=57.0 kN, My=0.03 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 100 | uprights | ULS2 (imp -x) | 0.659 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS2 (imp -x) | 0.658 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 164 | uprights | ULS2 (imp -x) | 0.658 | PASS | Nc=56.9 kN, My=0.03 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS2 (imp -x) | 0.658 | PASS | Nc=56.9 kN, My=0.03 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS3 (imp +x) | 0.658 | PASS | Nc=56.7 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS3 (imp -x) | 0.657 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 164 | uprights | ULS1 (imp +x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS1 (imp +x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 100 | uprights | ULS1 (imp -x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS1 (imp -x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 164 | uprights | ULS3 (imp +x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 164 | uprights | ULS1 (imp -x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS1 (imp -x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 100 | uprights | ULS1 (imp +x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS1 (imp +x) | 0.657 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 164 | uprights | ULS3 (imp -x) | 0.656 | PASS | Nc=56.9 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 148 | uprights | ULS2 (imp +x) | 0.656 | PASS | Nc=56.7 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 164 | uprights | ULS2 (imp +x) | 0.656 | PASS | Nc=56.7 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 84 | uprights | ULS2 (imp +x) | 0.656 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 100 | uprights | ULS2 (imp +x) | 0.655 | PASS | Nc=56.8 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 100 | uprights | ULS3 (imp -x) | 0.654 | PASS | Nc=56.6 kN, My=0.02 kNm, Mz=0.33 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 100 | uprights | ULS3 (imp +x) | 0.654 | PASS | Nc=56.6 kN, My=0.02 kNm, Mz=0.32 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 83 | uprights | ULS3 (imp -x) | 0.654 | PASS | Nc=57.0 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 83 | uprights | ULS3 (imp +x) | 0.653 | PASS | Nc=57.0 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 83 | uprights | ULS2 (imp -x) | 0.652 | PASS | Nc=56.8 kN, My=0.04 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 147 | uprights | ULS2 (imp -x) | 0.652 | PASS | Nc=56.9 kN, My=0.04 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 99 | uprights | ULS2 (imp -x) | 0.652 | PASS | Nc=56.8 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| member 163 | uprights | ULS2 (imp -x) | 0.651 | PASS | Nc=56.9 kN, My=0.03 kNm, Mz=0.27 kNm; Lcr_y=1200, Lcr_z=1500 mm, lambda_y=0.77, lambda_z=0.45, chi=0.740 (about y, curve b), Nb_Rd=101.0 kN |
| ... | | | | | 2694 more rows omitted |

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
| member 257 end j (z) | pallet beams | ULS2 (imp -y) | 0.607 | PASS | Mz,Ed=1.518 kNm, Mz,Rd=2.500 kNm |
| member 261 end j (z) | pallet beams | ULS2 (imp -y) | 0.607 | PASS | Mz,Ed=1.517 kNm, Mz,Rd=2.500 kNm |
| member 257 end j (z) | pallet beams | ULS2 (imp +y) | 0.606 | PASS | Mz,Ed=1.516 kNm, Mz,Rd=2.500 kNm |
| member 261 end j (z) | pallet beams | ULS2 (imp +y) | 0.606 | PASS | Mz,Ed=1.514 kNm, Mz,Rd=2.500 kNm |
| member 266 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.503 kNm, Mz,Rd=2.500 kNm |
| member 268 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.503 kNm, Mz,Rd=2.500 kNm |
| member 258 end j (z) | pallet beams | ULS3 (imp +x) | 0.601 | PASS | Mz,Ed=1.503 kNm, Mz,Rd=2.500 kNm |
| member 260 end j (z) | pallet beams | ULS3 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 262 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 267 end i (z) | pallet beams | ULS2 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 266 end i (z) | pallet beams | ULS2 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 267 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 258 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 259 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 266 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 259 end j (z) | pallet beams | ULS2 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 260 end j (z) | pallet beams | ULS2 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 260 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 265 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 257 end j (z) | pallet beams | ULS1 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 268 end i (z) | pallet beams | ULS1 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 268 end i (z) | pallet beams | ULS2 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 258 end j (z) | pallet beams | ULS2 (imp +x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 264 end i (z) | pallet beams | ULS3 (imp -x) | 0.601 | PASS | Mz,Ed=1.502 kNm, Mz,Rd=2.500 kNm |
| member 259 end j (z) | pallet beams | ULS3 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 262 end j (z) | pallet beams | ULS3 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 263 end i (z) | pallet beams | ULS2 (imp -x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 264 end j (z) | pallet beams | ULS3 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 262 end i (z) | pallet beams | ULS2 (imp -x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 257 end j (z) | pallet beams | ULS3 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| member 263 end j (z) | pallet beams | ULS1 (imp +x) | 0.600 | PASS | Mz,Ed=1.501 kNm, Mz,Rd=2.500 kNm |
| ... | | | | | 1112 more rows omitted |

## BRACE_BOLT checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 343 | bracing | ULS3 (imp +y) | 0.327 | PASS | N=1.02 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 355 | bracing | ULS3 (imp -y) | 0.312 | PASS | N=0.98 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 343 | bracing | ULS2 (imp +y) | 0.305 | PASS | N=0.96 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 355 | bracing | ULS2 (imp -y) | 0.305 | PASS | N=0.96 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 343 | bracing | ULS1 (imp +y) | 0.304 | PASS | N=0.95 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 367 | bracing | ULS1 (imp +y) | 0.304 | PASS | N=0.95 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 331 | bracing | ULS1 (imp -y) | 0.304 | PASS | N=0.95 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 355 | bracing | ULS1 (imp -y) | 0.304 | PASS | N=0.95 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 367 | bracing | ULS2 (imp +y) | 0.304 | PASS | N=0.95 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 331 | bracing | ULS2 (imp -y) | 0.304 | PASS | N=0.95 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 367 | bracing | ULS3 (imp +y) | 0.296 | PASS | N=0.93 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 319 | bracing | ULS3 (imp +y) | 0.285 | PASS | N=0.89 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 331 | bracing | ULS3 (imp -y) | 0.282 | PASS | N=0.88 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 344 | bracing | ULS3 (imp +y) | 0.269 | PASS | N=0.84 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 320 | bracing | ULS3 (imp +y) | 0.262 | PASS | N=0.82 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 356 | bracing | ULS3 (imp -y) | 0.253 | PASS | N=0.79 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 344 | bracing | ULS2 (imp +y) | 0.246 | PASS | N=0.77 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 356 | bracing | ULS2 (imp -y) | 0.246 | PASS | N=0.77 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 344 | bracing | ULS1 (imp +y) | 0.245 | PASS | N=0.77 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 368 | bracing | ULS1 (imp +y) | 0.245 | PASS | N=0.77 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 332 | bracing | ULS1 (imp -y) | 0.245 | PASS | N=0.77 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 356 | bracing | ULS1 (imp -y) | 0.245 | PASS | N=0.77 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 368 | bracing | ULS2 (imp +y) | 0.245 | PASS | N=0.77 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 332 | bracing | ULS2 (imp -y) | 0.244 | PASS | N=0.76 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 321 | bracing | ULS3 (imp +y) | 0.239 | PASS | N=0.75 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 368 | bracing | ULS3 (imp +y) | 0.237 | PASS | N=0.74 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 308 | bracing | ULS3 (imp +y) | 0.235 | PASS | N=0.74 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 345 | bracing | ULS3 (imp +y) | 0.233 | PASS | N=0.73 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 332 | bracing | ULS3 (imp -y) | 0.221 | PASS | N=0.69 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 332 | bracing | ULS3 (imp +y) | 0.220 | PASS | N=0.69 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 357 | bracing | ULS3 (imp -y) | 0.217 | PASS | N=0.68 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 309 | bracing | ULS3 (imp +y) | 0.214 | PASS | N=0.67 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 322 | bracing | ULS3 (imp +y) | 0.212 | PASS | N=0.66 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 310 | bracing | ULS3 (imp +y) | 0.211 | PASS | N=0.66 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 345 | bracing | ULS2 (imp +y) | 0.211 | PASS | N=0.66 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 357 | bracing | ULS2 (imp -y) | 0.210 | PASS | N=0.66 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 345 | bracing | ULS1 (imp +y) | 0.210 | PASS | N=0.66 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 369 | bracing | ULS1 (imp +y) | 0.210 | PASS | N=0.66 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 333 | bracing | ULS1 (imp -y) | 0.210 | PASS | N=0.66 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| member 357 | bracing | ULS1 (imp -y) | 0.210 | PASS | N=0.66 kN vs 1x M12 4.6: bolt shear=16.19, bearing brace=5.06, bearing upright=3.13 kN -> R=3.13 kN (bearing upright governs) |
| ... | | | | | 1304 more rows omitted |

## BASEPLATE checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| node 1000 | - | ULS2 (imp +x) | 0.948 | PASS | plate 150x130x5.0: c=12.1 mm, A_eff=6302 mm2 vs A_req=5971 mm2; N=57.0 kN, M=0.55 kNm -> N_eq=84.6 kN at node 1000; f_jd=14.17 MPa, A_req=5971 mm2, strip c_req=11.4 mm -> t_req=4.7 mm (use >= 4.7 mm), min plate 143x86 mm |
| node 2000 | - | ULS2 (imp -y) | 0.820 | PASS | plate 150x130x5.0: c=12.1 mm, A_eff=6302 mm2 vs A_req=5168 mm2; N=59.0 kN, M=0.28 kNm -> N_eq=73.2 kN at node 2000; f_jd=14.17 MPa, A_req=5168 mm2, strip c_req=9.8 mm -> t_req=4.0 mm (use >= 4.0 mm), min plate 140x83 mm |
| node 1300 | - | ULS3 (imp -x) | 0.797 | PASS | plate 150x130x5.0: c=12.1 mm, A_eff=6302 mm2 vs A_req=5025 mm2; N=57.2 kN, M=0.28 kNm -> N_eq=71.2 kN at node 1300; f_jd=14.17 MPa, A_req=5025 mm2, strip c_req=9.5 mm -> t_req=3.9 mm (use >= 3.9 mm), min plate 139x82 mm |
| node 1300 | - | ULS3 (imp +x) | 0.797 | PASS | plate 150x130x5.0: c=12.1 mm, A_eff=6302 mm2 vs A_req=5021 mm2; N=57.2 kN, M=0.28 kNm -> N_eq=71.1 kN at node 1300; f_jd=14.17 MPa, A_req=5021 mm2, strip c_req=9.5 mm -> t_req=3.9 mm (use >= 3.9 mm), min plate 139x82 mm |
| node 1300 | - | ULS1 (imp -x) | 0.793 | PASS | plate 150x130x5.0: c=12.1 mm, A_eff=6302 mm2 vs A_req=4999 mm2; N=56.9 kN, M=0.28 kNm -> N_eq=70.8 kN at node 1300; f_jd=14.17 MPa, A_req=4999 mm2, strip c_req=9.5 mm -> t_req=3.9 mm (use >= 3.9 mm), min plate 139x82 mm |
| node 2000 | - | ULS1 (imp +x) | 0.793 | PASS | plate 150x130x5.0: c=12.1 mm, A_eff=6302 mm2 vs A_req=4999 mm2; N=56.9 kN, M=0.28 kNm -> N_eq=70.8 kN at node 2000; f_jd=14.17 MPa, A_req=4999 mm2, strip c_req=9.5 mm -> t_req=3.9 mm (use >= 3.9 mm), min plate 139x82 mm |
| node 1300 | - | ULS2 (imp -x) | 0.793 | PASS | plate 150x130x5.0: c=12.1 mm, A_eff=6302 mm2 vs A_req=4995 mm2; N=56.9 kN, M=0.28 kNm -> N_eq=70.8 kN at node 1300; f_jd=14.17 MPa, A_req=4995 mm2, strip c_req=9.4 mm -> t_req=3.9 mm (use >= 3.9 mm), min plate 139x82 mm |
| node 2000 | - | ULS2 (imp +y) | 0.769 | PASS | plate 150x130x5.0: c=12.1 mm, A_eff=6302 mm2 vs A_req=4844 mm2; N=54.8 kN, M=0.28 kNm -> N_eq=68.6 kN at node 2000; f_jd=14.17 MPa, A_req=4844 mm2, strip c_req=9.1 mm -> t_req=3.8 mm (use >= 3.8 mm), min plate 138x81 mm |
| node 1300 | - | ULS3 (imp +y) | 0.704 | PASS | plate 150x130x5.0: c=12.1 mm, A_eff=6302 mm2 vs A_req=4434 mm2; N=59.3 kN, M=0.07 kNm -> N_eq=62.8 kN at node 1300; f_jd=14.17 MPa, A_req=4434 mm2, strip c_req=8.3 mm -> t_req=3.4 mm (use >= 3.4 mm), min plate 137x80 mm |
| node 2000 | - | ULS3 (imp -y) | 0.700 | PASS | plate 150x130x5.0: c=12.1 mm, A_eff=6302 mm2 vs A_req=4408 mm2; N=59.1 kN, M=0.07 kNm -> N_eq=62.5 kN at node 2000; f_jd=14.17 MPa, A_req=4408 mm2, strip c_req=8.2 mm -> t_req=3.4 mm (use >= 3.4 mm), min plate 136x79 mm |
| node 2000 | - | ULS1 (imp -y) | 0.697 | PASS | plate 150x130x5.0: c=12.1 mm, A_eff=6302 mm2 vs A_req=4395 mm2; N=59.0 kN, M=0.06 kNm -> N_eq=62.3 kN at node 2000; f_jd=14.17 MPa, A_req=4395 mm2, strip c_req=8.2 mm -> t_req=3.4 mm (use >= 3.4 mm), min plate 136x79 mm |
| node 1300 | - | ULS1 (imp +y) | 0.697 | PASS | plate 150x130x5.0: c=12.1 mm, A_eff=6302 mm2 vs A_req=4395 mm2; N=59.0 kN, M=0.06 kNm -> N_eq=62.3 kN at node 1300; f_jd=14.17 MPa, A_req=4395 mm2, strip c_req=8.2 mm -> t_req=3.4 mm (use >= 3.4 mm), min plate 136x79 mm |

## DEFLECTION checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 293 | pallet beams | SLS2 | 0.649 | PASS | defl=8.77 mm, limit=L/200=13.50 mm |
| member 294 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 295 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 304 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 294 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 295 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 302 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 303 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 296 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 301 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 304 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 293 | pallet beams | SLS1 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 303 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 296 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 302 | pallet beams | SLS2 | 0.647 | PASS | defl=8.73 mm, limit=L/200=13.50 mm |
| member 301 | pallet beams | SLS2 | 0.646 | PASS | defl=8.71 mm, limit=L/200=13.50 mm |
| member 257 | pallet beams | SLS2 | 0.639 | PASS | defl=8.63 mm, limit=L/200=13.50 mm |
| member 258 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 260 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 268 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 257 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 260 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 265 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 268 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 259 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 259 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 258 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 266 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 267 | pallet beams | SLS1 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 267 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 266 | pallet beams | SLS2 | 0.637 | PASS | defl=8.61 mm, limit=L/200=13.50 mm |
| member 269 | pallet beams | SLS2 | 0.637 | PASS | defl=8.60 mm, limit=L/200=13.50 mm |
| member 265 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 270 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 280 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 271 | pallet beams | SLS2 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 269 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 272 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 277 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
| member 280 | pallet beams | SLS1 | 0.636 | PASS | defl=8.58 mm, limit=L/200=13.50 mm |
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
| frame | - | ULS2 (imp +x) | 1.039 | INFO | estimated alpha_cr=2.89, sway amplification=1.529 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS3 (imp +x) | 1.027 | INFO | estimated alpha_cr=2.92, sway amplification=1.520 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS2 (imp -y) | 0.966 | INFO | estimated alpha_cr=3.10, sway amplification=1.475 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS2 (imp +y) | 0.964 | INFO | estimated alpha_cr=3.11, sway amplification=1.473 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | ULS1 (imp +y) | 0.236 | INFO | estimated alpha_cr=12.70, sway amplification=1.085 |
| frame | - | ULS1 (imp -y) | 0.236 | INFO | estimated alpha_cr=12.70, sway amplification=1.085 |
| frame | - | ULS3 (imp -y) | 0.235 | INFO | estimated alpha_cr=12.74, sway amplification=1.085 |
| frame | - | ULS3 (imp +y) | 0.109 | INFO | estimated alpha_cr=27.56, sway amplification=1.038 |

---
*Defaults follow EN 15512 with EN 1993 buckling curves; verify all factors, imperfection parameters and section/connector test values against the edition of the standard applicable to your project.*
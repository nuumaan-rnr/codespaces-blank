# EN 15512 design check report - RFEM import

- Analysis: second-order (P-Delta) elastic, engine: OpenSees
- Sway imperfection: phi = 0.00333 rad (1/300), method = EHF
- Partial factors: gamma_M0 = 1.0, gamma_M1 = 1.0
- Members: 529, nodes: 297, height: 9050 mm

## Analysis cases

| case | kind | converged | sway X [mm] | sway Y [mm] | alpha_cr (est.) |
|---|---|---|---|---|---|
| CO1 1.3 DL + 1.4 LL + Imp X (imp +x) | ULS | yes | 34.25 | 0.21 | 1.77 |
| CO2 1.3 DL + 1.26 LL + 1.26 PL X + (imp +x) | ULS | yes | 81.85 | 2.02 | 2.06 |
| CO3 1.0 DL + 1.0 LL + 1.0 AL X + I (imp +x) | ULS | yes | 21.70 | 0.15 | 2.45 |
| CO4 1.3 DL + 1.4 LL + Imp Y (imp +y) | ULS | yes | 0.65 | 0.96 | 25.24 |
| CO5 1.3 DL + 1.26 LL + 1.26 PL Y + (imp +y) | ULS | yes | 0.76 | 2.43 | 97.09 |
| CO6 1.0 DL + 1.0 LL + 1.0 AL Y + I (imp +y) | ULS | yes | 0.47 | 0.86 | 32.58 |
| CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | ULS | yes | 11.94 | 0.11 | 3.57 |
| CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | ULS | yes | 1.09 | 0.49 | 82.24 |
| CO11 DL + L.L.+ Imp X (imp +x) | SLS | yes | 17.67 | 0.15 | 2.53 |
| CO12 DL + L.L.+ Imp Y (imp +y) | SLS | yes | 0.46 | 0.68 | 35.40 |
| CO101 Seismic Weight | SLS | yes | 0.37 | 0.12 | 311.34 |

## Verdict: **PASS**

Governing: BUCKLING on member 1053 (CS3 RRO-PAR 112/50/1.6/3.2/1) in 'CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x)' - utilization **0.789**

## STRESS checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 1053 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.782 | PASS | N=-0.5 kN, My=0.00 kNm, Mz=2.82 kNm at x=1350 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1052 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.782 | PASS | N=-0.5 kN, My=0.00 kNm, Mz=2.82 kNm at x=1350 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1063 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.782 | PASS | N=-0.5 kN, My=0.00 kNm, Mz=2.82 kNm at x=1350 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1062 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.782 | PASS | N=-0.5 kN, My=0.00 kNm, Mz=2.82 kNm at x=1350 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1053 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.782 | PASS | N=-0.5 kN, My=0.00 kNm, Mz=2.81 kNm at x=1348 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1108 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.782 | PASS | N=-0.5 kN, My=0.00 kNm, Mz=2.81 kNm at x=1352 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1063 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.782 | PASS | N=-0.5 kN, My=0.00 kNm, Mz=2.81 kNm at x=1348 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1118 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.782 | PASS | N=-0.5 kN, My=0.00 kNm, Mz=2.81 kNm at x=1352 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1052 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.782 | PASS | N=-0.5 kN, My=-0.00 kNm, Mz=2.81 kNm at x=1352 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1107 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.782 | PASS | N=-0.5 kN, My=-0.00 kNm, Mz=2.81 kNm at x=1348 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1062 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.782 | PASS | N=-0.5 kN, My=-0.00 kNm, Mz=2.81 kNm at x=1352 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1117 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.782 | PASS | N=-0.5 kN, My=-0.00 kNm, Mz=2.81 kNm at x=1348 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1107 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.781 | PASS | N=-0.5 kN, My=0.00 kNm, Mz=2.81 kNm at x=1343 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1108 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.781 | PASS | N=-0.5 kN, My=0.00 kNm, Mz=2.81 kNm at x=1357 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1117 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.781 | PASS | N=-0.5 kN, My=0.00 kNm, Mz=2.81 kNm at x=1343 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1118 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.781 | PASS | N=-0.5 kN, My=0.00 kNm, Mz=2.81 kNm at x=1357 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1085 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.771 | PASS | N=0.1 kN, My=0.00 kNm, Mz=2.78 kNm at x=1350 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1074 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.771 | PASS | N=0.1 kN, My=-0.00 kNm, Mz=2.78 kNm at x=1350 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1084 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.771 | PASS | N=0.1 kN, My=-0.00 kNm, Mz=2.78 kNm at x=1350 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1075 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.770 | PASS | N=0.1 kN, My=0.00 kNm, Mz=2.78 kNm at x=1350 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1075 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.770 | PASS | N=0.1 kN, My=-0.00 kNm, Mz=2.78 kNm at x=1357 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1074 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.770 | PASS | N=0.1 kN, My=-0.00 kNm, Mz=2.78 kNm at x=1343 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1084 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.770 | PASS | N=0.1 kN, My=0.00 kNm, Mz=2.78 kNm at x=1343 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1085 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.770 | PASS | N=0.1 kN, My=0.00 kNm, Mz=2.78 kNm at x=1357 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1070 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.768 | PASS | N=-0.1 kN, My=-0.00 kNm, Mz=2.77 kNm at x=1350 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1071 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.768 | PASS | N=-0.1 kN, My=-0.00 kNm, Mz=2.78 kNm at x=1364 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1070 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.768 | PASS | N=-0.1 kN, My=-0.00 kNm, Mz=2.78 kNm at x=1336 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1080 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.768 | PASS | N=-0.1 kN, My=-0.00 kNm, Mz=2.77 kNm at x=1350 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1081 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.768 | PASS | N=-0.1 kN, My=0.00 kNm, Mz=2.77 kNm at x=1350 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1081 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.768 | PASS | N=-0.1 kN, My=-0.00 kNm, Mz=2.78 kNm at x=1364 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1080 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.768 | PASS | N=-0.1 kN, My=-0.00 kNm, Mz=2.78 kNm at x=1336 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1071 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.768 | PASS | N=-0.1 kN, My=0.00 kNm, Mz=2.77 kNm at x=1350 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1048 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.766 | PASS | N=-0.1 kN, My=-0.00 kNm, Mz=2.77 kNm at x=1344 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1049 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.766 | PASS | N=-0.1 kN, My=-0.00 kNm, Mz=2.77 kNm at x=1356 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1059 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.766 | PASS | N=-0.1 kN, My=0.00 kNm, Mz=2.77 kNm at x=1356 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1058 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.766 | PASS | N=-0.1 kN, My=0.00 kNm, Mz=2.77 kNm at x=1344 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1048 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.766 | PASS | N=-0.1 kN, My=-0.00 kNm, Mz=2.77 kNm at x=1354 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1103 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.766 | PASS | N=-0.1 kN, My=-0.00 kNm, Mz=2.77 kNm at x=1346 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1059 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.766 | PASS | N=-0.1 kN, My=0.00 kNm, Mz=2.77 kNm at x=1346 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| member 1114 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.766 | PASS | N=-0.1 kN, My=0.00 kNm, Mz=2.77 kNm at x=1354 mm; N_Rd=125.4 kN, My_Rd=2.33 kNm, Mz_Rd=3.62 kNm |
| ... | | | | | 4192 more rows omitted |

## BUCKLING checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 1053 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.789 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.82 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1052 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.789 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.82 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1063 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.789 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.82 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1062 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.789 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.82 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1063 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.789 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.81 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1118 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.789 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.81 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1053 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.789 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.81 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1108 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.789 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.81 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1052 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.789 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.81 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1107 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.789 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.81 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1062 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.789 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.81 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1117 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.789 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.81 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1107 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.788 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.81 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1108 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.788 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.81 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1117 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.788 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.81 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1118 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.788 | PASS | Nc=0.5 kN, My=0.00 kNm, Mz=2.81 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1063 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO4 1.3 DL + 1.4 LL + Imp Y (imp +y) | 0.775 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.74 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1118 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO4 1.3 DL + 1.4 LL + Imp Y (imp +y) | 0.775 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.74 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1053 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO4 1.3 DL + 1.4 LL + Imp Y (imp +y) | 0.775 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.74 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1108 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO4 1.3 DL + 1.4 LL + Imp Y (imp +y) | 0.775 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.74 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1053 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO1 1.3 DL + 1.4 LL + Imp X (imp +x) | 0.775 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.75 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1052 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO1 1.3 DL + 1.4 LL + Imp X (imp +x) | 0.775 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.75 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1063 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO1 1.3 DL + 1.4 LL + Imp X (imp +x) | 0.775 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.75 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1062 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO4 1.3 DL + 1.4 LL + Imp Y (imp +y) | 0.775 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.74 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1062 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO1 1.3 DL + 1.4 LL + Imp X (imp +x) | 0.775 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.75 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1117 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO4 1.3 DL + 1.4 LL + Imp Y (imp +y) | 0.775 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.74 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1052 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO4 1.3 DL + 1.4 LL + Imp Y (imp +y) | 0.775 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.74 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1107 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO4 1.3 DL + 1.4 LL + Imp Y (imp +y) | 0.775 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.74 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1107 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO1 1.3 DL + 1.4 LL + Imp X (imp +x) | 0.772 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.74 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1108 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO1 1.3 DL + 1.4 LL + Imp X (imp +x) | 0.772 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.74 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1117 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO1 1.3 DL + 1.4 LL + Imp X (imp +x) | 0.772 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.74 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1118 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO1 1.3 DL + 1.4 LL + Imp X (imp +x) | 0.772 | PASS | Nc=0.7 kN, My=0.00 kNm, Mz=2.74 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1070 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.769 | PASS | Nc=0.1 kN, My=0.00 kNm, Mz=2.77 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1071 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.769 | PASS | Nc=0.1 kN, My=0.00 kNm, Mz=2.78 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1070 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.769 | PASS | Nc=0.1 kN, My=0.00 kNm, Mz=2.78 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1080 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.769 | PASS | Nc=0.1 kN, My=0.00 kNm, Mz=2.77 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1081 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.769 | PASS | Nc=0.1 kN, My=0.00 kNm, Mz=2.77 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1080 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.768 | PASS | Nc=0.1 kN, My=0.00 kNm, Mz=2.78 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1081 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.768 | PASS | Nc=0.1 kN, My=0.00 kNm, Mz=2.78 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| member 1071 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.768 | PASS | Nc=0.1 kN, My=0.00 kNm, Mz=2.77 kNm; Lcr_y=2700, Lcr_z=2700 mm, lambda_y=1.41, lambda_z=0.76, chi=0.378 (about y, curve b), Nb_Rd=47.4 kN |
| ... | | | | | 3286 more rows omitted |

## DEFLECTION checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| member 1053 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.641 | PASS | defl=8.66 mm, limit=L/200=13.50 mm |
| member 1052 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.641 | PASS | defl=8.66 mm, limit=L/200=13.50 mm |
| member 1063 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.641 | PASS | defl=8.66 mm, limit=L/200=13.50 mm |
| member 1062 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.641 | PASS | defl=8.66 mm, limit=L/200=13.50 mm |
| member 1052 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.641 | PASS | defl=8.65 mm, limit=L/200=13.50 mm |
| member 1107 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.641 | PASS | defl=8.65 mm, limit=L/200=13.50 mm |
| member 1053 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.641 | PASS | defl=8.65 mm, limit=L/200=13.50 mm |
| member 1108 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.641 | PASS | defl=8.65 mm, limit=L/200=13.50 mm |
| member 1063 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.641 | PASS | defl=8.65 mm, limit=L/200=13.50 mm |
| member 1118 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.641 | PASS | defl=8.65 mm, limit=L/200=13.50 mm |
| member 1062 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.641 | PASS | defl=8.65 mm, limit=L/200=13.50 mm |
| member 1117 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.641 | PASS | defl=8.65 mm, limit=L/200=13.50 mm |
| member 1107 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.640 | PASS | defl=8.64 mm, limit=L/200=13.50 mm |
| member 1108 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.640 | PASS | defl=8.64 mm, limit=L/200=13.50 mm |
| member 1117 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.640 | PASS | defl=8.64 mm, limit=L/200=13.50 mm |
| member 1118 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.640 | PASS | defl=8.64 mm, limit=L/200=13.50 mm |
| member 1055 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.635 | PASS | defl=8.57 mm, limit=L/200=13.50 mm |
| member 1054 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.635 | PASS | defl=8.57 mm, limit=L/200=13.50 mm |
| member 1045 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.635 | PASS | defl=8.57 mm, limit=L/200=13.50 mm |
| member 1044 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.635 | PASS | defl=8.57 mm, limit=L/200=13.50 mm |
| member 1044 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.634 | PASS | defl=8.55 mm, limit=L/200=13.50 mm |
| member 1099 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.634 | PASS | defl=8.55 mm, limit=L/200=13.50 mm |
| member 1055 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.634 | PASS | defl=8.55 mm, limit=L/200=13.50 mm |
| member 1110 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.634 | PASS | defl=8.55 mm, limit=L/200=13.50 mm |
| member 1054 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.634 | PASS | defl=8.55 mm, limit=L/200=13.50 mm |
| member 1109 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.634 | PASS | defl=8.55 mm, limit=L/200=13.50 mm |
| member 1100 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.634 | PASS | defl=8.55 mm, limit=L/200=13.50 mm |
| member 1045 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.634 | PASS | defl=8.55 mm, limit=L/200=13.50 mm |
| member 1059 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.633 | PASS | defl=8.55 mm, limit=L/200=13.50 mm |
| member 1058 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.633 | PASS | defl=8.55 mm, limit=L/200=13.50 mm |
| member 1049 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.633 | PASS | defl=8.55 mm, limit=L/200=13.50 mm |
| member 1048 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO11 DL + L.L.+ Imp X (imp +x) | 0.633 | PASS | defl=8.55 mm, limit=L/200=13.50 mm |
| member 1048 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.633 | PASS | defl=8.54 mm, limit=L/200=13.50 mm |
| member 1103 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.633 | PASS | defl=8.54 mm, limit=L/200=13.50 mm |
| member 1049 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.633 | PASS | defl=8.54 mm, limit=L/200=13.50 mm |
| member 1104 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.633 | PASS | defl=8.54 mm, limit=L/200=13.50 mm |
| member 1059 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.633 | PASS | defl=8.54 mm, limit=L/200=13.50 mm |
| member 1114 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.633 | PASS | defl=8.54 mm, limit=L/200=13.50 mm |
| member 1058 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.633 | PASS | defl=8.54 mm, limit=L/200=13.50 mm |
| member 1113 | CS3 RRO-PAR 112/50/1.6/3.2/1 | CO12 DL + L.L.+ Imp Y (imp +y) | 0.633 | PASS | defl=8.54 mm, limit=L/200=13.50 mm |
| ... | | | | | 176 more rows omitted |

## SWAY checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| frame X (down-aisle) | - | CO11 DL + L.L.+ Imp X (imp +x) | 0.390 | PASS | max sway=17.67 mm, limit=H/200=45.25 mm (H=9050 mm) |
| frame Y (cross-aisle) | - | CO12 DL + L.L.+ Imp Y (imp +y) | 0.015 | PASS | max sway=0.68 mm, limit=H/200=45.25 mm (H=9050 mm) |
| frame X (down-aisle) | - | CO12 DL + L.L.+ Imp Y (imp +y) | 0.010 | PASS | max sway=0.46 mm, limit=H/200=45.25 mm (H=9050 mm) |
| frame X (down-aisle) | - | CO101 Seismic Weight | 0.008 | PASS | max sway=0.37 mm, limit=H/200=45.25 mm (H=9050 mm) |
| frame Y (cross-aisle) | - | CO11 DL + L.L.+ Imp X (imp +x) | 0.003 | PASS | max sway=0.15 mm, limit=H/200=45.25 mm (H=9050 mm) |
| frame Y (cross-aisle) | - | CO101 Seismic Weight | 0.003 | PASS | max sway=0.12 mm, limit=H/200=45.25 mm (H=9050 mm) |

## ALPHA_CR checks

| target | set | case | utilization | status | detail |
|---|---|---|---|---|---|
| frame | - | CO1 1.3 DL + 1.4 LL + Imp X (imp +x) | 1.692 | INFO | estimated alpha_cr=1.77, sway amplification=2.293 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | CO2 1.3 DL + 1.26 LL + 1.26 PL X + (imp +x) | 1.456 | INFO | estimated alpha_cr=2.06, sway amplification=1.943 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | CO3 1.0 DL + 1.0 LL + 1.0 AL X + I (imp +x) | 1.224 | INFO | estimated alpha_cr=2.45, sway amplification=1.689 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | CO7 1.3 DL + 1.4 Patern L. + Imp X (imp +x) | 0.841 | INFO | estimated alpha_cr=3.57, sway amplification=1.390 (alpha_cr < 10: sway-sensitive, second-order analysis required - and performed) |
| frame | - | CO4 1.3 DL + 1.4 LL + Imp Y (imp +y) | 0.119 | INFO | estimated alpha_cr=25.24, sway amplification=1.041 |
| frame | - | CO6 1.0 DL + 1.0 LL + 1.0 AL Y + I (imp +y) | 0.092 | INFO | estimated alpha_cr=32.58, sway amplification=1.032 |
| frame | - | CO8 1.3 DL + 1.4 Patern L. + Imp Y (imp +y) | 0.036 | INFO | estimated alpha_cr=82.24, sway amplification=1.012 |
| frame | - | CO5 1.3 DL + 1.26 LL + 1.26 PL Y + (imp +y) | 0.031 | INFO | estimated alpha_cr=97.09, sway amplification=1.010 |

---
*Defaults follow EN 15512 with EN 1993 buckling curves; verify all factors, imperfection parameters and section/connector test values against the edition of the standard applicable to your project.*
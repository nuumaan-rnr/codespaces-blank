# RFEM vs rack15512 (OpenSees) - validation comparison

- compared values: 5240 (member-level extremes of N, My, Mz across combinations)
- median relative difference: 0.5%
- 90th percentile: 11.0%
- 95th percentile: 29.6%
- maximum: 128.6%

## By quantity

| quantity | n | median diff | p95 |
|---|---|---|---|
| N_min | 2814 | 0.5% | 6.1% |
| Mz_absmax | 2422 | 0.5% | 38.6% |
| My_absmax | 4 | 30.6% | 37.8% |

## By combination

| combination | n | median diff | p95 |
|---|---|---|---|
| CO1 | 588 | 0.4% | 32.4% |
| CO2 | 580 | 0.9% | 31.1% |
| CO3 | 553 | 0.4% | 40.9% |
| CO4 | 472 | 0.7% | 6.1% |
| CO5 | 481 | 0.8% | 7.9% |
| CO6 | 464 | 0.7% | 6.0% |
| CO7 | 574 | 0.5% | 22.2% |
| CO8 | 530 | 0.7% | 5.9% |
| CO11 | 542 | 0.5% | 43.1% |
| CO12 | 456 | 0.7% | 5.5% |

## Governing members side by side

For each combination: the most compressed member and the member with the largest bending moment (by this app's results).

| combination | quantity | member | set | ours | RSTAB/RFEM | diff |
|---|---|---|---|---|---|---|
| CO1 | N_min | 869 | CS1 SHAPE-THIN UP0 | -53.01 kN | -52.73 kN | 0.5% |
| CO1 | Mz_absmax | 1053 | CS3 RRO-PAR 112/50 | 274.54 kNcm | 274.46 kNcm | 0.0% |
| CO2 | N_min | 869 | CS1 SHAPE-THIN UP0 | -48.33 kN | -47.59 kN | 1.5% |
| CO2 | Mz_absmax | 1044 | CS3 RRO-PAR 112/50 | 249.33 kNcm | 248.86 kNcm | 0.2% |
| CO3 | N_min | 867 | CS1 SHAPE-THIN UP0 | -37.98 kN | -37.73 kN | 0.6% |
| CO3 | Mz_absmax | 1052 | CS3 RRO-PAR 112/50 | 196.11 kNcm | 196.08 kNcm | 0.0% |
| CO4 | N_min | 867 | CS1 SHAPE-THIN UP0 | -54.71 kN | -50.97 kN | 6.8% |
| CO4 | Mz_absmax | 1052 | CS3 RRO-PAR 112/50 | 274.22 kNcm | 274.18 kNcm | 0.0% |
| CO5 | N_min | 871 | CS1 SHAPE-THIN UP0 | -49.61 kN | -46.52 kN | 6.2% |
| CO5 | Mz_absmax | 1108 | CS3 RRO-PAR 112/50 | 247.10 kNcm | 247.07 kNcm | 0.0% |
| CO6 | N_min | 867 | CS1 SHAPE-THIN UP0 | -39.26 kN | -36.73 kN | 6.4% |
| CO6 | Mz_absmax | 1052 | CS3 RRO-PAR 112/50 | 195.92 kNcm | 195.90 kNcm | 0.0% |
| CO7 | N_min | 869 | CS1 SHAPE-THIN UP0 | -27.08 kN | -26.93 kN | 0.5% |
| CO7 | Mz_absmax | 1053 | CS3 RRO-PAR 112/50 | 281.50 kNcm | 281.49 kNcm | 0.0% |
| CO8 | N_min | 867 | CS1 SHAPE-THIN UP0 | -27.94 kN | -26.06 kN | 6.7% |
| CO8 | Mz_absmax | 1052 | CS3 RRO-PAR 112/50 | 281.38 kNcm | 281.36 kNcm | 0.0% |
| CO11 | N_min | 869 | CS1 SHAPE-THIN UP0 | -37.93 kN | -37.73 kN | 0.5% |
| CO11 | Mz_absmax | 1053 | CS3 RRO-PAR 112/50 | 196.10 kNcm | 195.64 kNcm | 0.2% |
| CO12 | N_min | 867 | CS1 SHAPE-THIN UP0 | -39.14 kN | -36.59 kN | 6.5% |
| CO12 | Mz_absmax | 1052 | CS3 RRO-PAR 112/50 | 195.92 kNcm | 195.53 kNcm | 0.2% |

### Reading the tail

Large *relative* differences concentrate in members with tiny *absolute* forces (sub-kN bracing axials, moments of a few kNcm) where the imperfection conventions differ: this app applies equivalent horizontal forces at every loaded node, RFEM applies inclinations to the upright member sets.  Check the absolute values in the table below before treating a row as a discrepancy.

## Largest differences

| member | set | combo | quantity | ours | RFEM | diff |
|---|---|---|---|---|---|---|
| 1848 | CS2 SHAPE-THIN FGD | CO5 | N_min | 0.56 kN | -0.16 kN | 128.6% |
| 1854 | CS2 SHAPE-THIN FGD | CO4 | N_min | 0.63 kN | -0.17 kN | 126.9% |
| 1848 | CS2 SHAPE-THIN FGD | CO4 | N_min | 0.63 kN | -0.17 kN | 126.9% |
| 1854 | CS2 SHAPE-THIN FGD | CO5 | N_min | 0.59 kN | -0.11 kN | 118.6% |
| 916 | CS2 SHAPE-THIN FGD | CO1 | N_min | 0.69 kN | 0.00 kN | 100.0% |
| 923 | CS2 SHAPE-THIN FGD | CO1 | N_min | 0.69 kN | 0.00 kN | 100.0% |
| 954 | CS2 SHAPE-THIN FGD | CO1 | N_min | 0.69 kN | 0.00 kN | 100.0% |
| 960 | CS2 SHAPE-THIN FGD | CO1 | N_min | 0.69 kN | 0.00 kN | 100.0% |
| 916 | CS2 SHAPE-THIN FGD | CO2 | N_min | 0.61 kN | 0.00 kN | 100.0% |
| 923 | CS2 SHAPE-THIN FGD | CO2 | N_min | 0.63 kN | 0.00 kN | 100.0% |
| 954 | CS2 SHAPE-THIN FGD | CO2 | N_min | 0.61 kN | 0.00 kN | 100.0% |
| 960 | CS2 SHAPE-THIN FGD | CO2 | N_min | 0.63 kN | 0.00 kN | 100.0% |
| 923 | CS2 SHAPE-THIN FGD | CO3 | N_min | 0.50 kN | 0.00 kN | 100.0% |
| 960 | CS2 SHAPE-THIN FGD | CO3 | N_min | 0.50 kN | 0.00 kN | 100.0% |
| 908 | CS2 SHAPE-THIN FGD | CO4 | N_min | -0.63 kN | 0.00 kN | 100.0% |
| 916 | CS2 SHAPE-THIN FGD | CO4 | N_min | 0.71 kN | 0.00 kN | 100.0% |
| 923 | CS2 SHAPE-THIN FGD | CO4 | N_min | 0.69 kN | 0.00 kN | 100.0% |
| 946 | CS2 SHAPE-THIN FGD | CO4 | N_min | -0.63 kN | 0.00 kN | 100.0% |
| 954 | CS2 SHAPE-THIN FGD | CO4 | N_min | 0.71 kN | 0.00 kN | 100.0% |
| 960 | CS2 SHAPE-THIN FGD | CO4 | N_min | 0.69 kN | 0.00 kN | 100.0% |
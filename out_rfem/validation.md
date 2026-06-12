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
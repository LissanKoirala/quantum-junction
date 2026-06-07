# Pure MPS adaptive sweep report

Generated from the frozen result set after cancelling the remaining Slurm jobs on 2026-06-06.

## Scope

This report covers only pure Qiskit Aer MPS runs using `AerSimulator(method="matrix_product_state")`. It excludes peaked-MPO, tree-tensor, quimb graph, and statevector methods except where prior exact answers are used for validation.

The charts use the stored `sampling.top_counts` from each completed trial. For each challenge, bar values are aggregate stored counts divided by total shots across completed trials. They are empirical sample support values, not exact probabilities.

## Job outcome

- Remaining jobs were cancelled with `scancel`.
- Completed result JSONs: `217`.
- Challenges with completed MPS data: `40/49`.
- Tier result counts: standard `183`, hard `30`, very_hard `4`.
- All completed JSONs in the frozen set have `status=ok`.
- Two standard tasks were preempted before writing JSON: task 108 was retried successfully; task 137 was still missing when cancellation was requested.

## Main findings

- Exact-checkable challenges matched in `9/10` cases represented in this sweep.
- MPS aggregate winner matched the existing selected answer in `30` challenges.
- Stable or exact-matching MPS winners: `30` challenges.
- Low-support/flat winners: `7` challenges, mainly the harder partial runs.
- Challenges with no completed MPS data in this cancelled sweep: `64_40, 64_41, 48_42, 56_43, 64_44, 72_45, 80_46, 88_47, 96_48`.

## Figures

### All Challenges

![All-challenge MPS probability distribution chart](figures/probability_distributions/all_challenges_distribution.png)

### Top Candidate Support

![Top MPS candidate support overview](figures/probability_distributions/top_candidate_support_overview.png)

### Per-Challenge Distribution Charts

| Challenge | Chart |
| --- | --- |
| `8_1` | ![MPS distribution for challenge 8_1](figures/probability_distributions/challenge-8_1.png) |
| `16_2` | ![MPS distribution for challenge 16_2](figures/probability_distributions/challenge-16_2.png) |
| `24_3` | ![MPS distribution for challenge 24_3](figures/probability_distributions/challenge-24_3.png) |
| `28_4` | ![MPS distribution for challenge 28_4](figures/probability_distributions/challenge-28_4.png) |
| `32_5` | ![MPS distribution for challenge 32_5](figures/probability_distributions/challenge-32_5.png) |
| `36_6` | ![MPS distribution for challenge 36_6](figures/probability_distributions/challenge-36_6.png) |
| `40_7` | ![MPS distribution for challenge 40_7](figures/probability_distributions/challenge-40_7.png) |
| `48_8` | ![MPS distribution for challenge 48_8](figures/probability_distributions/challenge-48_8.png) |
| `56_9` | ![MPS distribution for challenge 56_9](figures/probability_distributions/challenge-56_9.png) |
| `64_10` | ![MPS distribution for challenge 64_10](figures/probability_distributions/challenge-64_10.png) |
| `8_11` | ![MPS distribution for challenge 8_11](figures/probability_distributions/challenge-8_11.png) |
| `16_12` | ![MPS distribution for challenge 16_12](figures/probability_distributions/challenge-16_12.png) |
| `24_13` | ![MPS distribution for challenge 24_13](figures/probability_distributions/challenge-24_13.png) |
| `32_14` | ![MPS distribution for challenge 32_14](figures/probability_distributions/challenge-32_14.png) |
| `36_15` | ![MPS distribution for challenge 36_15](figures/probability_distributions/challenge-36_15.png) |
| `40_16` | ![MPS distribution for challenge 40_16](figures/probability_distributions/challenge-40_16.png) |
| `40_17` | ![MPS distribution for challenge 40_17](figures/probability_distributions/challenge-40_17.png) |
| `40_18` | ![MPS distribution for challenge 40_18](figures/probability_distributions/challenge-40_18.png) |
| `48_19` | ![MPS distribution for challenge 48_19](figures/probability_distributions/challenge-48_19.png) |
| `48_20` | ![MPS distribution for challenge 48_20](figures/probability_distributions/challenge-48_20.png) |
| `48_21` | ![MPS distribution for challenge 48_21](figures/probability_distributions/challenge-48_21.png) |
| `56_22` | ![MPS distribution for challenge 56_22](figures/probability_distributions/challenge-56_22.png) |
| `56_23` | ![MPS distribution for challenge 56_23](figures/probability_distributions/challenge-56_23.png) |
| `56_24` | ![MPS distribution for challenge 56_24](figures/probability_distributions/challenge-56_24.png) |
| `64_25` | ![MPS distribution for challenge 64_25](figures/probability_distributions/challenge-64_25.png) |
| `64_26` | ![MPS distribution for challenge 64_26](figures/probability_distributions/challenge-64_26.png) |
| `8_27` | ![MPS distribution for challenge 8_27](figures/probability_distributions/challenge-8_27.png) |
| `16_28` | ![MPS distribution for challenge 16_28](figures/probability_distributions/challenge-16_28.png) |
| `24_29` | ![MPS distribution for challenge 24_29](figures/probability_distributions/challenge-24_29.png) |
| `32_30` | ![MPS distribution for challenge 32_30](figures/probability_distributions/challenge-32_30.png) |
| `48_31` | ![MPS distribution for challenge 48_31](figures/probability_distributions/challenge-48_31.png) |
| `48_32` | ![MPS distribution for challenge 48_32](figures/probability_distributions/challenge-48_32.png) |
| `56_33` | ![MPS distribution for challenge 56_33](figures/probability_distributions/challenge-56_33.png) |
| `64_34` | ![MPS distribution for challenge 64_34](figures/probability_distributions/challenge-64_34.png) |
| `40_35` | ![MPS distribution for challenge 40_35](figures/probability_distributions/challenge-40_35.png) |
| `48_36` | ![MPS distribution for challenge 48_36](figures/probability_distributions/challenge-48_36.png) |
| `48_37` | ![MPS distribution for challenge 48_37](figures/probability_distributions/challenge-48_37.png) |
| `56_38` | ![MPS distribution for challenge 56_38](figures/probability_distributions/challenge-56_38.png) |
| `56_39` | ![MPS distribution for challenge 56_39](figures/probability_distributions/challenge-56_39.png) |
| `104_49` | ![MPS distribution for challenge 104_49](figures/probability_distributions/challenge-104_49.png) |

## Summary Table

| challenge | diff | done | exp | class | candidate | support | vote | prev? | exact? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8_1 | very_easy | 4 | 4 | exact_match | 10101101 | 0.912 | 1 | True | True |
| 16_2 | very_easy | 4 | 4 | exact_match | 1010101011001000 | 0.4653 | 1 | True | True |
| 24_3 | very_easy | 4 | 4 | exact_match | 011110010000101010001000 | 0.7191 | 1 | True | True |
| 28_4 | very_easy | 4 | 4 | exact_match | 11111110001...0110011111 | 0.1582 | 1 | True | True |
| 32_5 | very_easy | 4 | 4 | stable_mps | 00111000101...0000010000 | 0.0706 | 0.75 | True | False |
| 36_6 | very_easy | 4 | 4 | stable_mps | 10011010011...0011001000 | 0.69 | 1 | True | False |
| 40_7 | very_easy | 4 | 4 | stable_mps | 01101110110...0011000111 | 0.8826 | 1 | True | False |
| 48_8 | very_easy | 4 | 4 | stable_mps | 00010010011...1110010100 | 0.6933 | 1 | True | False |
| 56_9 | very_easy | 4 | 4 | stable_mps | 10010110101...1101010100 | 0.7701 | 1 | True | False |
| 64_10 | very_easy | 4 | 4 | stable_mps | 00110100101...0100101011 | 0.7679 | 1 | True | False |
| 8_11 | easy | 6 | 6 | exact_match | 01001110 | 0.551 | 1 | True | True |
| 16_12 | easy | 6 | 6 | exact_match | 1111000101101011 | 0.4612 | 1 | True | True |
| 24_13 | easy | 6 | 6 | exact_match | 111110011111001011010001 | 0.5973 | 1 | True | True |
| 32_14 | easy | 6 | 6 | stable_mps | 00000101001...1111101100 | 0.4589 | 1 | True | False |
| 36_15 | easy | 6 | 6 | flat_low_support | 11011001101...1110101111 | 0.0004639 | 0.3333 | False | False |
| 40_16 | easy | 6 | 6 | stable_mps | 01011101010...0110010110 | 0.4719 | 1 | True | False |
| 40_17 | easy | 6 | 6 | stable_mps | 00100101010...1000001001 | 0.5578 | 1 | True | False |
| 40_18 | easy | 6 | 6 | stable_mps | 01000001100...1111001110 | 0.2678 | 1 | True | False |
| 48_19 | easy | 6 | 6 | stable_mps | 01100101011...1110010000 | 0.6854 | 1 | True | False |
| 48_20 | easy | 6 | 6 | stable_mps | 10101010010...0010000000 | 0.6345 | 1 | True | False |
| 48_21 | easy | 6 | 6 | stable_mps | 11101010111...0000001001 | 0.513 | 1 | True | False |
| 56_22 | easy | 6 | 6 | stable_mps | 11100100100...0111111011 | 0.5862 | 1 | True | False |
| 56_23 | easy | 6 | 6 | stable_mps | 01001101001...1100001101 | 0.5037 | 1 | True | False |
| 56_24 | easy | 6 | 6 | stable_mps | 10011001001...1011110001 | 0.1057 | 1 | True | False |
| 64_25 | easy | 6 | 6 | stable_mps | 00111011111...0001111011 | 0.2417 | 1 | True | False |
| 64_26 | easy | 6 | 6 | unstable_or_partial | 01101010101...1001100110 | 0.1028 | 0.5 | True | False |
| 8_27 | moderate | 6 | 6 | exact_match | 11001001 | 0.2875 | 1 | True | True |
| 16_28 | moderate | 6 | 6 | exact_match | 1101001111011100 | 0.3509 | 1 | True | True |
| 24_29 | moderate | 6 | 6 | exact_mismatch | 110100010111100001001101 | 0.0006348 | 0.3333 | False | False |
| 32_30 | moderate | 6 | 6 | stable_mps | 10011000010...1111010111 | 0.02005 | 1 | True | False |
| 48_31 | moderate | 6 | 6 | stable_mps | 10110011100...1000110110 | 0.3885 | 1 | True | False |
| 48_32 | moderate | 6 | 6 | stable_mps | 01110101011...1110001110 | 0.1462 | 1 | True | False |
| 56_33 | moderate | 6 | 6 | stable_mps | 11001001100...1101010000 | 0.05185 | 1 | False | False |
| 64_34 | moderate | 5 | 6 | unstable_or_partial | 00110101000...1011100110 | 0.1701 | 0.8 | False | False |
| 40_35 | hard | 8 | 8 | flat_low_support | 00001101100...0110011011 | 1.744e-05 | 0.125 | False | False |
| 48_36 | hard | 8 | 8 | flat_low_support | 00011101101...0010111000 | 1.786e-05 | 0.125 | False | False |
| 48_37 | hard | 6 | 6 | flat_low_support | 00000111111...1001110010 | 5.232e-05 | 0.1667 | False | False |
| 56_38 | hard | 4 | 6 | flat_low_support | 00000000011...0100110101 | 4.883e-05 | 0.25 | False | False |
| 56_39 | hard | 4 | 6 | flat_low_support | 10010111001...1001010000 | 0.0001465 | 0.25 | False | False |
| 64_40 | hard | 0 | 6 | no_data |  | 0 | 0 | False | False |
| 64_41 | hard | 0 | 8 | no_data |  | 0 | 0 | False | False |
| 48_42 | very_hard | 0 | 6 | no_data |  | 0 | 0 | False | False |
| 56_43 | very_hard | 0 | 6 | no_data |  | 0 | 0 | False | False |
| 64_44 | very_hard | 0 | 6 | no_data |  | 0 | 0 | False | False |
| 72_45 | very_hard | 0 | 6 | no_data |  | 0 | 0 | False | False |
| 80_46 | very_hard | 0 | 6 | no_data |  | 0 | 0 | False | False |
| 88_47 | very_hard | 0 | 6 | no_data |  | 0 | 0 | False | False |
| 96_48 | very_hard | 0 | 6 | no_data |  | 0 | 0 | False | False |
| 104_49 | very_hard | 4 | 6 | flat_low_support | 00000000010...1100010011 | 0.0003255 | 0.25 | False | False |

Full bitstrings and top-count distributions are in:

- `tables/mps_adaptive_summary.tsv`
- `tables/mps_adaptive_top_counts.tsv`

## Exact Mismatches

These need scrutiny before using any MPS candidate:

| challenge | candidate | support | top1 vote |
| --- | --- | --- | --- |
| 24_29 | 110100010111100001001101 | 0.0006348 | 0.3333 |

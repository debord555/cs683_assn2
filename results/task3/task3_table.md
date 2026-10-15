# Task 3 results

Baseline: no L1D prefetching, LRU at L2 (results/task1b/baseline).

## IPC

| Trace | No prefetching (LRU) | SPP (LRU) | Dyn-I-RRIP | SPP + PF-aware Dyn-I-RRIP |
|---|---:|---:|---:|---:|
| Trace1 | 0.2322 | 0.2332 | 0.2321 | 0.2327 |
| Trace2 | 0.2511 | 0.2513 | 0.2568 | 0.2552 |
| Trace3 | 0.3821 | 0.3829 | 0.3818 | 0.3830 |
| **Average** | 0.2885 | 0.2891 | 0.2902 | 0.2903 |

## Speedup over no prefetching (LRU) (Average = geometric mean)

| Trace | SPP (LRU) | Dyn-I-RRIP | SPP + PF-aware Dyn-I-RRIP |
|---|---:|---:|---:|
| Trace1 | 1.0042 | 0.9997 | 1.0021 |
| Trace2 | 1.0008 | 1.0224 | 1.0163 |
| Trace3 | 1.0023 | 0.9993 | 1.0024 |
| **Average** | 1.0024 | 1.0071 | 1.0069 |

## L1D prefetch accuracy (%)

| Trace | SPP (LRU) | SPP + PF-aware Dyn-I-RRIP |
|---|---:|---:|
| Trace1 | 60.72 | 60.94 |
| Trace2 | 57.47 | 56.67 |
| Trace3 | 33.36 | 33.73 |
| **Average** | 50.52 | 50.45 |

## L1D prefetch coverage (%)

| Trace | SPP (LRU) | SPP + PF-aware Dyn-I-RRIP |
|---|---:|---:|
| Trace1 | 5.78 | 5.69 |
| Trace2 | 0.65 | 0.57 |
| Trace3 | 3.48 | 3.70 |
| **Average** | 3.30 | 3.32 |

## L1D load MPKI

| Trace | No prefetching (LRU) | SPP (LRU) | Dyn-I-RRIP | SPP + PF-aware Dyn-I-RRIP |
|---|---:|---:|---:|---:|
| Trace1 | 10.679 | 10.062 | 10.680 | 10.072 |
| Trace2 | 13.534 | 13.446 | 13.541 | 13.457 |
| Trace3 | 3.403 | 3.285 | 3.403 | 3.277 |
| **Average** | 9.205 | 8.931 | 9.208 | 8.935 |

## L2C load MPKI

| Trace | No prefetching (LRU) | SPP (LRU) | Dyn-I-RRIP | SPP + PF-aware Dyn-I-RRIP |
|---|---:|---:|---:|---:|
| Trace1 | 17.730 | 17.214 | 17.651 | 17.172 |
| Trace2 | 27.923 | 27.827 | 21.724 | 23.206 |
| Trace3 | 3.959 | 3.703 | 3.931 | 3.649 |
| **Average** | 16.538 | 16.248 | 14.436 | 14.675 |

## L2 instruction load MPKI

| Trace | No prefetching (LRU) | SPP (LRU) | Dyn-I-RRIP | SPP + PF-aware Dyn-I-RRIP |
|---|---:|---:|---:|---:|
| Trace1 | 10.384 | 10.389 | 9.788 | 9.848 |
| Trace2 | 19.391 | 19.326 | 12.631 | 14.218 |
| Trace3 | 1.126 | 1.129 | 1.064 | 1.053 |
| **Average** | 10.300 | 10.281 | 7.827 | 8.373 |

## L2 data load MPKI

| Trace | No prefetching (LRU) | SPP (LRU) | Dyn-I-RRIP | SPP + PF-aware Dyn-I-RRIP |
|---|---:|---:|---:|---:|
| Trace1 | 7.346 | 6.825 | 7.864 | 7.323 |
| Trace2 | 8.533 | 8.500 | 9.093 | 8.988 |
| Trace3 | 2.833 | 2.574 | 2.868 | 2.595 |
| **Average** | 6.237 | 5.967 | 6.608 | 6.302 |

## Prefetch traffic at L1D and L2

| Trace | Config | L1D PF issued | L1D PF useful | PF hits in L2 | PF fills into L2 | L2 PF lines hit by a demand load | % of L2 PF fills used |
|---|---:|---:|---:|---:|---:|---:|---:|
| Trace1 | SPP (LRU) | 28454 | 17278 | 7969 | 20484 | 1513 | 7.39 |
| Trace1 | SPP + PF-aware Dyn-I-RRIP | 27752 | 16913 | 5766 | 21985 | 221 | 1.01 |
| Trace2 | SPP (LRU) | 5211 | 2995 | 2932 | 2279 | 345 | 15.14 |
| Trace2 | SPP + PF-aware Dyn-I-RRIP | 5394 | 3057 | 2504 | 2890 | 93 | 3.22 |
| Trace3 | SPP (LRU) | 9496 | 3168 | 384 | 9112 | 455 | 4.99 |
| Trace3 | SPP + PF-aware Dyn-I-RRIP | 9910 | 3343 | 320 | 9590 | 110 | 1.15 |

## Set-dueling decision

| Trace | Config | Average ratio | % follower accesses in I-RRIP mode | Switches |
|---|---:|---:|---:|---:|
| Trace1 | Dyn-I-RRIP | 0.439 | 100.0 | 0 |
| Trace1 | SPP + PF-aware Dyn-I-RRIP | 0.445 | 100.0 | 0 |
| Trace2 | Dyn-I-RRIP | 0.600 | 93.7 | 2 |
| Trace2 | SPP + PF-aware Dyn-I-RRIP | 0.634 | 95.8 | 2 |
| Trace3 | Dyn-I-RRIP | 0.308 | 57.5 | 1 |
| Trace3 | SPP + PF-aware Dyn-I-RRIP | 0.350 | 63.8 | 1 |

# Task 1B results

## IPC

| Trace | No prefetching | IP-stride | SPP |
|---|---:|---:|---:|
| Trace1-003 | 0.2322 | 0.2334 | 0.2332 |
| Trace2-001 | 0.2511 | 0.2512 | 0.2513 |
| Trace3-002 | 0.3821 | 0.3830 | 0.3829 |
| **Average** | 0.2885 | 0.2892 | 0.2891 |

## Speedup over no prefetching (Average = geometric mean)

| Trace | IP-stride | SPP |
|---|---:|---:|
| Trace1-003 | 1.0051 | 1.0042 |
| Trace2-001 | 1.0002 | 1.0008 |
| Trace3-002 | 1.0024 | 1.0023 |
| **Average** | 1.0026 | 1.0024 |

## L1D load MPKI

| Trace | No prefetching | IP-stride | SPP |
|---|---:|---:|---:|
| Trace1-003 | 10.679 | 10.119 | 10.062 |
| Trace2-001 | 13.534 | 13.436 | 13.446 |
| Trace3-002 | 3.403 | 3.318 | 3.285 |
| **Average** | 9.205 | 8.957 | 8.931 |

## L1D prefetch accuracy (%)

| Trace | IP-stride | SPP |
|---|---:|---:|
| Trace1-003 | 52.79 | 60.72 |
| Trace2-001 | 38.13 | 57.47 |
| Trace3-002 | 16.09 | 33.36 |
| **Average** | 35.67 | 50.52 |

## L1D prefetch coverage (%)

| Trace | IP-stride | SPP |
|---|---:|---:|
| Trace1-003 | 5.24 | 5.78 |
| Trace2-001 | 0.73 | 0.65 |
| Trace3-002 | 2.51 | 3.48 |
| **Average** | 2.83 | 3.30 |

# SPP accuracy-throttling sweep

MIN_CONF / MAX_CONF: accuracy below / above which the prefetch degree is decreased / increased; MAX_DEGREE: upper bound of the degree. Each run is compared with the no-prefetching baseline on the same trace.

## All throttle settings

| Trace | MIN_CONF | MAX_CONF | MAX_DEGREE | IPC | Speedup | L1D MPKI | Accuracy (%) | Coverage (%) | PF issued | PF useful |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Trace1-003 | 0.3 | 0.6 | 4 | 0.2328 | 1.0028 | 10.128 | 62.75 | 5.16 | 24247 | 15215 |
| Trace1-003 | 0.4 | 0.7 | 4 | 0.2328 | 1.0026 | 10.159 | 63.22 | 4.87 | 22478 | 14210 |
| Trace1-003 | 0.5 | 0.75 | 2 | 0.2328 | 1.0024 | 10.248 | 61.86 | 4.03 | 18787 | 11622 |
| Trace1-003 | 0.5 | 0.75 | 4 | 0.2328 | 1.0025 | 10.193 | 62.50 | 4.54 | 21207 | 13254 |
| Trace1-003 | 0.5 | 0.75 | 6 | 0.2328 | 1.0027 | 10.159 | 63.02 | 4.86 | 22574 | 14225 |
| Trace1-003 | 0.5 | 0.75 | 8 | 0.2328 | 1.0028 | 10.149 | 63.49 | 4.96 | 22846 | 14504 |
| Trace1-003 | 0.6 | 0.85 | 4 | 0.2328 | 1.0025 | 10.223 | 62.44 | 4.26 | 19778 | 12349 |
| Trace1-003 | 0.7 | 0.9 | 4 | 0.2327 | 1.0023 | 10.238 | 62.22 | 4.13 | 19167 | 11926 |
| Trace1-003 | *IP-stride (main run)* |  |  | 0.2334 | 1.0051 | 10.119 | 52.79 | 5.24 | 30988 | 16359 |
| Trace1-003 | *SPP (main run)* |  |  | 0.2332 | 1.0042 | 10.062 | 60.72 | 5.78 | 28454 | 17278 |

Best setting by speedup: MIN_CONF=0.3, MAX_CONF=0.6, MAX_DEGREE=4 on Trace1-003 (speedup 1.0028).

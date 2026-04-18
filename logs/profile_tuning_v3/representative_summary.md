# Representative profile tuning v3 summary

## Per config
| robot | group | level | improvement | baseline score | candidate score | baseline normal p95 | candidate normal p95 |
|---|---|---|---:|---:|---:|---:|---:|
| booster_k1 | two_stage_medium | lite | -12.53% | 123.6979 | 139.1930 | 1.4275 | 1.1540 |
| booster_k1 | two_stage_medium | mid | -16.05% | 123.6979 | 143.5539 | 1.4275 | 1.1529 |
| booster_t1 | two_stage_medium | lite | -336.19% | 114.8780 | 501.0907 | 1.0426 | 2.0782 |
| booster_t1 | two_stage_medium | mid | -251.51% | 114.8780 | 403.8090 | 1.0426 | 2.0844 |
| engineai_pm01 | two_stage_full | lite | -519.32% | 91.8914 | 569.1043 | 1.1170 | 1.8885 |
| engineai_pm01 | two_stage_full | mid | -397.52% | 91.8914 | 457.1817 | 1.1170 | 1.8391 |
| pal_talos | two_stage_partial | lite | -44.53% | 150.1735 | 217.0399 | 1.5448 | 0.8275 |
| pal_talos | two_stage_partial | mid | -36.11% | 150.1735 | 204.3984 | 1.5448 | 0.9913 |
| stanford_toddy | two_stage_full | lite | -53.99% | 82.7023 | 127.3504 | 1.0184 | 1.1263 |
| stanford_toddy | two_stage_full | mid | -39.29% | 82.7023 | 115.1934 | 1.0184 | 1.0681 |
| unitree_h1 | two_stage_medium | lite | -1179.19% | 76.7153 | 981.3319 | 2.0165 | 5.1422 |
| unitree_h1 | two_stage_medium | mid | -901.04% | 76.7153 | 767.9539 | 2.0165 | 5.2220 |
| unitree_h1_2 | two_stage_full | lite | -469.46% | 129.2921 | 736.2697 | 1.0504 | 2.4947 |
| unitree_h1_2 | two_stage_full | mid | -302.03% | 129.2921 | 519.7986 | 1.0504 | 2.4279 |

## Profile averages
| group | level | avg improvement | avg baseline normal p95 | avg candidate normal p95 | count |
|---|---|---:|---:|---:|---:|
| two_stage_full | lite | -347.59% | 1.0619 | 1.8365 | 3 |
| two_stage_full | mid | -246.28% | 1.0619 | 1.7784 | 3 |
| two_stage_medium | lite | -509.30% | 1.4955 | 2.7915 | 3 |
| two_stage_medium | mid | -389.54% | 1.4955 | 2.8198 | 3 |
| two_stage_partial | lite | -44.53% | 1.5448 | 0.8275 | 1 |
| two_stage_partial | mid | -36.11% | 1.5448 | 0.9913 | 1 |

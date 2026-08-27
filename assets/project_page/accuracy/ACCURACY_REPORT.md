# Scene 2 accuracy benchmark

Simulation evidence only. It is not real-world accuracy, food-safety validation, real-cell safety validation, OEM fidelity, or production readiness.

Core gate: PASS
Core cases: 10 passed, 0 failed
Stress cases: 2 passed, 3 failed

| Case | Tier | Solution | Speed m/s | Y m | Yaw deg | Camera position mm | Track position mm | Intercept position mm | Delivery position mm | Result |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| core_a_fast_transverse | core | A | 0.18 | 0.050 | 68.0 | 7.11 | 7.09 | 7.26 | 14.57 | PASS |
| core_a_high_speed_transverse | core | A | 0.22 | -0.050 | -72.0 | 5.29 | 5.29 | 8.15 | 10.36 | PASS |
| core_a_medium_oblique | core | A | 0.14 | -0.030 | 32.0 | 5.07 | 5.07 | 5.12 | 11.01 | PASS |
| core_a_nominal | core | A | 0.10 | 0.040 | 0.0 | 4.50 | 4.51 | 4.38 | 10.31 | PASS |
| core_a_nominal_replay | core | A | 0.10 | 0.040 | 0.0 | 4.56 | 4.57 | 4.38 | 10.27 | PASS |
| core_a_slow_diagonal | core | A | 0.06 | -0.060 | -35.0 | 3.95 | 3.96 | 3.73 | 19.69 | PASS |
| core_b_fast_oblique | core | B | 0.18 | 0.040 | 45.0 | 6.06 | 6.08 | 6.67 | 20.16 | PASS |
| core_b_nominal | core | B | 0.10 | 0.030 | 0.0 | 3.61 | 3.61 | 4.13 | 10.74 | PASS |
| core_b_nominal_replay | core | B | 0.10 | 0.030 | 0.0 | 3.66 | 3.67 | 4.38 | 10.67 | PASS |
| core_b_slow_diagonal | core | B | 0.08 | -0.040 | -25.0 | 3.86 | 3.85 | 3.87 | 22.36 | PASS |
| stress_a_latency | stress | A | 0.22 | 0.060 | -65.0 | 6.49 | 6.49 | 9.60 | 11.85 | PASS |
| stress_a_limit_pose | stress | A | 0.30 | 0.080 | 85.0 | 7.96 | 8.00 | n/a | n/a | FAIL |
| stress_a_noisy | stress | A | 0.16 | -0.070 | 55.0 | 6.49 | 6.49 | 7.10 | 17.70 | FAIL |
| stress_b_high_speed | stress | B | 0.26 | 0.070 | -75.0 | 7.38 | 7.39 | 11.24 | 21.35 | PASS |
| stress_b_noisy | stress | B | 0.16 | -0.060 | 55.0 | 8.59 | 8.60 | 7.43 | 21.55 | FAIL |

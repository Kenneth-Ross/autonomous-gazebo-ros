# [VERIFICATION] RTAB-Map SLAM Acceptance

## Scope

Orange Pi full-stack mapping with synchronized RGB-D, EKF odometry, cone landmarks,
`/rtabmap/mapData`, and `map -> base_link`. Simulation server supplies fixed world,
route, sensor configuration, and random seed.

## Deterministic nominal case

Run fixed route from clean RTAB-Map database twice. Retain commit, simulator seed,
route ID, database checksum, and full-stack log. Each 120-second run must have at
least 50 RTAB-Map windows, effective rate at least 0.5 Hz, conversion p95 at most
10 ms, delay p95 at most 500 ms, median camera pair rate at least 29 Hz, at most
25% of camera windows below 29 Hz, unmatched-drop growth at most five, bounded
queue high-water at most 12, no malformed growth, no input stalls/fatal errors,
and live map TF/map data. Final map node count and trajectory endpoint must agree
within 5% and 0.5 m respectively between repeats.

## Mandatory adversarial case

Pause `vision_container` for three seconds, resume it, then observe 90 seconds.
Stack must recover without manual restart. Recovery window uses nominal thresholds,
must publish `map -> base_link` and `/rtabmap/mapData`, and must show no process death,
DDS `retcode -58`, fatal error, unbounded queue, malformed growth, or post-recovery
landmark transform rejection. Final three recovery camera windows must each reach
at least 29 Hz.

## Commands

Orange Pi, with full stack already running and logging to `/tmp/edge_full_stack.log`:

```bash
./scripts/validation/rtabmap_slam_acceptance.sh nominal
./scripts/validation/rtabmap_slam_acceptance.sh adversarial
```

Promotion to `[COMPLETE]` requires two retained nominal passes plus one retained
adversarial pass from same reviewed commit. Automated parser tests alone are not
hardware evidence.

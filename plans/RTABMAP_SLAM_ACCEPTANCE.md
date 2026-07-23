# [COMPLETE] RTAB-Map SLAM Acceptance

## Scope

Orange Pi full-stack mapping with synchronized RGB-D, EKF odometry, cone landmarks,
`/rtabmap/mapData`, and `map -> base_link`. Simulation server supplies fixed world,
route, sensor configuration, and random seed.

## Deterministic nominal case

Run fixed simulation route in two independently measured windows. Retain commit
and full-stack logs. Each 120-second run must have at
least 50 RTAB-Map windows, effective rate at least 0.5 Hz, conversion p95 at most
10 ms, delay p95 at most 500 ms, median camera pair rate at least 29 Hz, at most
25% of camera windows below 29 Hz, unmatched-drop growth at most five, bounded
queue high-water at most 12, no malformed growth, no input stalls/fatal errors,
and live map TF/map data. This accepts bounded operational mapping; long-duration
working-memory scalability remains separate from this 120-second acceptance.

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

Completed on commit `28c60526` with nominal evidence
`rtabmap_slam_nominal_20260723T013756Z.log` and
`rtabmap_slam_nominal_20260723T014636Z.log`, plus adversarial evidence
`rtabmap_slam_adversarial_20260723T014013Z.log`.

# Racing review fixes — host acceptance evidence

Date: 2026-10-12. Scope: `edge_stack/src/autonomous_racing_core` on the Ubuntu
24.04 host with ROS 2 Jazzy. No Orange Pi commands or deployment checks ran.

## Commands and results

```bash
source /opt/ros/jazzy/setup.bash
cd edge_stack
colcon build --symlink-install --merge-install --packages-select autonomous_racing_core
colcon test --merge-install --packages-select autonomous_racing_core
colcon test-result --verbose
```

- Package build passed.
- C++ unit regressions: **14 passed**.
- ROS launch acceptance: **2 passed**. Ran the production planner, controller,
  adapter, and supervisor nodes together on isolated `ROS_DOMAIN_ID=178`.
- Package CTest suite: **8/8 passed**, including C++ tests and CMake, Python,
  XML, and C++ lint checks.

## Retained nominal and adversarial cases

The launch acceptance passed these scenarios:

- Nominal supervisor run: prepare, matching fresh recorder heartbeat, start,
  fresh command candidate, nonzero output.
- Adversarial recorder from a different run ID: supervisor latches
  `recorder_run_id_mismatch` and command output returns to zero.
- Adversarial stale candidate timestamp: supervisor latches `candidate_stale`
  and command output returns to zero.
- Operator abort after a nominal command: status reports the abort reason and
  command output returns to zero.
- Rotated and translated corridor: map-frame cones are classified in
  `base_link`, then the rolling path is returned in `map`.
- Missing map-to-vehicle TF: planner publishes an empty path.
- Zero localization confidence: planner publishes an empty path.
- Nonidentity map-to-odom TF: controller computes near-zero steering for a
  vehicle-aligned map-frame target; missing odometry TF produces an invalid
  candidate.
- Marker-only input: adapter publishes zero confidence and
  `QUARANTINED` estimates.

Unit regressions also cover mismatched heartbeat invalidating prior readiness,
stale recorder delivery, source timestamp age after delayed candidate delivery,
and zero, stale, future, and nonfinite timestamps.

## TDD and remaining acceptance

The run-ID and source-timestamp API regressions were authored before their
corresponding implementation changes. The node-level launch cases were added
during implementation. A separate failing pre-fix run was **not captured**, so
no red-phase result is claimed. The passing build and test output is retained in
the host workspace's `edge_stack/build/autonomous_racing_core/test_results/`
and launch log directory.

Future timestamps are rejected. Recorder, candidate, cone, odometry, and TF
timestamps must share the same ROS clock domain; the wire contract has no
cross-host clock-skew tolerance. The current marker-only production input is
intentionally unable to authorize movement. A trusted quality-bearing cone
source must replace the marker adapter before racing can proceed; competing
marker-only messages on `/racing/cone_map` remain unsafe and must not be mixed
with trusted control inputs. Orange Pi build/runtime,
fixed/unseen-track safe-lap, and MCAP/Foxglove acceptance remain outstanding.

## Independent reviewer replay

The parent verified both node regressions fail against freshly compiled original
`e18157b2` binaries, then reran the fixed C++ and node tests successfully.
[Retained replay output](RACING_REVIEW_REGRESSION_REPLAY.md) contains both launch
logs. This was a retrospective comparison; no initial pre-implementation red
run is claimed.

The parent also reran the existing 58 selected host Python contract/helper
regressions after remediation; all passed.

# Code review — 2026-10-12

## Scope and verdict

Reviewed local `main` at `e18157b2`, after the 65-commit fast-forward, with existing
uncommitted documentation work preserved. This was a focused review of the racing
control chain, recorder lifecycle, existing acceptance tests, and documentation
hosting. It is not an exhaustive audit of every ROS package or dependency.
The initial review changed no production code and ran no Orange Pi commands.
The subsequent remediation below changes the racing control package on this host.

Autonomous racing remains `[W.I.P]`. The findings below describe the original
reviewed code. Their host fixes now pass new regression coverage; hardware
deployment and fixed/unseen-track safe-lap acceptance remain open.

## Remediation reviewed on the host

| Original finding | Change | Host verification |
|---|---|---|
| Supervisor concurrency | One mutually exclusive group covers services, subscriptions, and timer | Nominal motion and abort-to-zero node acceptance; no race-detector run |
| Map/vehicle planning | Timestamped TF transforms classify cones in vehicle coordinates and return a map-frame path | Translated, rotated corridor plus missing-TF acceptance |
| Map/odom control | Timestamped odometry pose transformed into the path frame | Nonidentity transform steering check and missing-TF rejection |
| Recorder identity and freshness | Prepared run-ID matching, header validation, and expiration from source timestamps | Mismatch/stale node faults and delayed-message C++ regressions |
| Unsupported marker confidence | Zero quality/localization, large uncertainty, and quarantined marker estimates | Marker quarantine and localization-loss node acceptance |

Fresh package build, 14 C++ tests, two ROS-node tests, and all eight package CTest
checks passed. The parent independently reran core/node checks and replayed the
new node tests against original binaries: both fail on the original code.
[Host evidence](evidence/RACING_REVIEW_FIXES_HOST.md) and
[original/fixed replay](evidence/RACING_REVIEW_REGRESSION_REPLAY.md) retain the
results. No initial TDD red run was captured; the original-code replay was
retrospective.

**Deployment effect:** the current marker-only input cannot authorize motion.
Replace the marker adapter with a trusted, quality-bearing cone source before
racing; do not publish unknown marker data alongside trusted data on the control
map topic. Topics, message schemas, and map-frame path output are preserved.
`tf2`, `tf2_ros`, and `tf2_geometry_msgs` are now declared dependencies. Planner
parameters `vehicle_frame` (default `base_link`) and `input_timeout` (default
0.5 seconds) are added. Participants must share the ROS clock domain; future
message stamps are rejected. No Orange Pi deployment is claimed.

## Findings

### P1 — Supervisor services race with command and heartbeat callbacks

[Supervisor callback groups](../edge_stack/src/autonomous_racing_core/src/racing_supervisor_node.cpp)
place prepare/start/abort services in a separate mutually exclusive group from
the timer and subscriptions. The four-thread executor can run the two groups
concurrently. Both access the same unsynchronized `SafetySupervisor`, including
state, latch, candidate, and strings. An abort racing with `tick()` can publish a
previous nonzero command; concurrent string mutation is also a C++ data race.
Use one mutually exclusive group or synchronize the complete state transition
and output snapshot. Verify concurrent abort/prepare against timer/candidate
activity, with a retained adversarial pass and a race detector where available.

### P1 — Planner treats map coordinates as vehicle-relative coordinates

The [adapter](../edge_stack/src/autonomous_racing_core/src/cone_map_adapter_node.cpp)
preserves landmark frames. The
[planner](../edge_stack/src/autonomous_racing_core/src/racing_planner_node.cpp)
splits cones using `position.y >= 0`, while the
[midpoint helper](../edge_stack/src/autonomous_racing_core/src/midpoint_planner.cpp)
filters `x > 0` and sorts by X. Those operations assume vehicle-relative axes,
but RTAB-Map publishes a map-frame landmark set. Translating or rotating the car
changes left/right and forward membership without changing those global tests.
Transform observations into the vehicle frame at their timestamp before
classification, and test translated and rotated cars on the same corridor.

### P1 — Controller combines map-frame paths with odom-frame poses

The [controller node](../edge_stack/src/autonomous_racing_core/src/racing_controller_node.cpp)
uses `/odometry/filtered` pose without retaining or checking its frame. The
[EKF configuration](../edge_stack/src/rtabmap_bridge/config/ekf.yaml) sets
`world_frame: odom`; the adapter/planner preserve the landmark map frame. The
[controller helper](../edge_stack/src/autonomous_racing_core/src/pure_pursuit_controller.cpp)
assumes every non-local path shares the pose frame. A nonidentity `map -> odom`
transform therefore changes the correct steering target, but is ignored.
Transform the pose/path into a common frame and reject unavailable or stale TF.
Test a nonidentity map/odom transform and missing-transform behavior.

### P1 — Unrelated recorder can authorize a run

The [recorder callback](../edge_stack/src/autonomous_racing_core/src/racing_supervisor_node.cpp)
checks health/state but ignores `RecorderHeartbeat.run_id`. Preparing run B and
receiving a healthy heartbeat for run A allows run B to start and keep moving,
although its recording requirement has not been satisfied. Bind heartbeats to
the active, nonempty run ID and verify mismatched, delayed, and matching IDs.
Candidate and heartbeat freshness also use receipt time without validating
message header timestamps; queued old messages can refresh watchdogs.

### P2 — Adapter turns marker availability into perfect perception confidence

The [cone adapter](../edge_stack/src/autonomous_racing_core/src/cone_map_adapter_node.cpp)
sets localization, detection, depth, pose, and association confidence to 1.0 and
marks each valid marker persistent. It replaces the output stamp with receipt
clock time and does not gate `last_observed`. A republished old map therefore
looks fresh and fully trusted to the planner. Marker presence cannot establish
those confidence claims. Carry measured observation quality and age, or mark
unknown quality conservatively; test stale observations and localization loss.

## Checks actually run

- Source-level host pytest selection: **58 passed**. Covered recorder artifacts,
  camera ranges, track selection, vehicle kinematics, driving control, racing
  contracts/launch, message interfaces, perception/launch contracts, Nav2
  acceptance helpers, depth integrity, and RTAB-Map acceptance/performance helpers.
- Used `/usr/bin/python3`, explicit source `PYTHONPATH`, importlib import mode,
  and disabled unrelated pytest plugin autoload. Initial collection attempts
  failed because the default Conda interpreter lacked pytest and the system
  interpreter lacked source import paths; corrected invocation passed.
- Existing `edge_stack/build/autonomous_racing_core/test_racing_core` binary:
  **9 passed**. This reran retained build output; no fresh C++ build is claimed.
- Documentation unittest: **6 passed**, including nominal/adversarial cases.
- Mermaid grammar: **12 diagrams passed**; browser rendering is not covered.
- No full simulation launch, new hardware acceptance, or package installation.

## Overall project status

See the authoritative [project ledger](PROJECTS.md). Camera-only reception,
lossless decoding, bounded RTAB-Map, and covariance preparation retain their
previous scoped completion evidence. End-to-end autonomous driving is unfinished:
control findings above, final full-stack performance, perception acceptance,
Orange Pi navigation/racing acceptance, and visualization fault evidence remain.
Semantic perception and Edge Nav2/control still need current specifications.
Long-map SLAM scalability remains a low-priority plan.

## Documentation hosting

The enabled user service remains active on loopback and the specific host tailnet
address: [documentation site](http://100.98.177.128:8766/).
It starts at login; pre-login startup and cross-device reachability are unverified.

HTTPS Serve reported disabled and supplied a tailnet administration enable link.
HTTP Serve on port 8080 was denied to this user; `sudo -n` required a password.
No password was requested or collected. A subsequent Serve status showed another
project on port 80, which was left intact. The requested documentation Serve proxy
was not enabled. An authorized host operator can add it on a separate port:

```bash
sudo tailscale serve --bg --yes --http=8080 http://127.0.0.1:8766
tailscale serve status
```

This command is for the simulation server, not the Orange Pi. No Git commit or
push was performed. Serve permission failures are host privilege failures, not
an automatic approval-review rejection.

## Subsequent test consolidation

The 14-core/two-node counts above describe the remediation verification before
consolidation. Current checks favor a connected production control graph, real
MCAP lifecycle/playback, and actuator E2E suites, retaining four core boundary
cases. See [TESTING.md](TESTING.md) and the
[consolidation evidence](evidence/E2E_TEST_CONSOLIDATION_HOST.md). The review fixes
remain covered; original test counts are kept as historical evidence.

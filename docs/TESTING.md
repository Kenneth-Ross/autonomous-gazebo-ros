# Testing the production flows

Run host E2E acceptance first for racing/control changes. Prefer an assertion on
published outputs, service responses, recorded payloads, or vehicle motion over
an assertion that a source file contains a particular string. A test of a retired
prototype does not establish production behavior. Keep small deterministic tests
for exact time boundaries, malformed data, numerical limits, and file safety.

## Host control, recording, and actuator acceptance

Build the affected packages on the simulation server using the system Python
that provides ROS 2 Jazzy dependencies:

```bash
source /opt/ros/jazzy/setup.bash
(cd edge_stack && colcon build --symlink-install --merge-install --packages-select autonomous_racing_msgs autonomous_racing_core)
source edge_stack/install/local_setup.bash
(cd server_sim && colcon build --symlink-install --packages-select autonomous_racing_msgs my_gazebo_package)
scripts/validation/racing_host_e2e.sh
```

The runner executes registered CTest tests labeled `e2e` and fails if a required
suite has no matching tests. It retains CTest results in `validation_evidence/`.
ROS domains 176–178 isolate the three suites; discovery is restricted to localhost.
Avoid running another copy using those domains concurrently. Package tests also
run E2E acceptance normally; the label provides a convenient first check.

| Flow | Production boundaries exercised | Observable acceptance |
|---|---|---|
| [Connected racing control](../edge_stack/src/autonomous_racing_core/test/test_racing_e2e_launch.py) | Trusted cone observations and odometry/TF → planner → controller → supervisor → final control request | Rotated/transformed corridor, revision propagation, explicit start, single-side confidence, nominal output, source loss, unsafe path, missing TF, recorder identity/health/freshness, bad commands, latched zero output, reprepare, and clean shutdown |
| [Recorder lifecycle](../server_sim/src/my_gazebo_package/test/test_run_recorder_e2e_launch.py) | ROS prepare/start/stop/abort services → production recorder → rosbag2 MCAP → payload playback | Invalid and duplicate prepare rejection, real COMPLETE/ABORTED runs, run identity/metadata, allowlist exclusion, recorded message counts, exact payload/frame/timestamp replay, and clean shutdown |
| [Actuator control](../server_sim/src/my_gazebo_package/test/test_driving_model_runtime.py) | Control request and manual brake/odometry inputs → production driving model → actuator command | Watchdog braking, manual override/recovery, steering slew and full-lock reversal, and clean shutdown |

The control fixtures supply synthetic trusted observations and recorder
heartbeats. They do not publish a nominal path or command candidate and do not
mock the production planner/controller/supervisor. Recorder acceptance runs a
real recorder separately. These suites establish their host control/storage
boundaries; they do not constitute one sensor-to-wheel vehicle lap or Orange Pi
NPU/network acceptance. Marker-only estimates remain unable to authorize motion.

## Full simulation and camera-to-edge gates

Existing [Gazebo acceptance](../scripts/validation/autonomous_gazebo_acceptance.sh)
and [racing lifecycle smoke](../scripts/validation/autonomous_racing_lifecycle.sh)
remain available. Run the Gazebo nominal/adversarial checks when changing vehicle
models, simulation launch, bridges, or vehicle dynamics:

```bash
scripts/validation/autonomous_gazebo_acceptance.sh nominal
scripts/validation/autonomous_gazebo_acceptance.sh adversarial
```

[Streaming acceptance](STREAMING_CONTRACT.md) and
[RTAB-Map acceptance](../plans/RTABMAP_SLAM_ACCEPTANCE.md) cover the server-to-edge
network, codec, timestamps, frames, depth integrity, latency, fault recovery, and
bounded SLAM. Orange Pi steps require device execution and returned evidence.
Fixed/unseen-track safe-lap acceptance and trusted perception-source integration
are still open; host fixtures do not satisfy them.

## Focused regressions worth keeping

- Racing core: exact source-age expiration after delayed delivery, stale recorder
  invalidation, nonfinite/zero/future timestamps, and physical steering clamping.
- Driving model: exact watchdog and manual-override timeout boundaries, which
  scheduler-tolerant E2E timing cannot reliably distinguish.
- Recorder: unsafe run IDs and malformed topic configurations before subprocess
  startup. Runtime acceptance covers file creation and the real bag lifecycle.
- Encoder/decoder: lossless depth and malformed bytes, exact-stamp pairing,
  bounded transport behavior, and precision. Retain these alongside streaming E2E.
- Perception: deterministic depth/projection/association and geometric faults
  while NPU/camera hardware acceptance remains separate.
- Camera/vehicle configuration, launch/network validation, and file-scoped cache
  cleanup retain their current checks until runtime replacements cover their
  exact requirements. This consolidation does not claim a repository-wide
  replacement of every configuration assertion.

## Consolidation record

[E2E consolidation specification](../plans/E2E_TEST_CONSOLIDATION.md) and
[host evidence](evidence/E2E_TEST_CONSOLIDATION_HOST.md) map 28 removed cases to
replacement runtime coverage. Older validation records retain their original
counts; they describe earlier suites, not today's default test inventory.

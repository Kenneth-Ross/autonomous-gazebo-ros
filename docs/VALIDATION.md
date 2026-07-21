# Validation and Evidence

- **Implemented:** source/configuration exists.
- **Host verified:** repeatable host check passed with retained output.
- **Edge verified:** repeatable Orange Pi check passed with retained output.
- **End-to-end verified:** synchronized host/edge checks passed for one revision/configuration.
- **Adversarially verified:** required fault, boundary, loss, restart, unavailability, resource-pressure, and recovery cases passed with retained evidence.
- **Planned:** intended work without sufficient evidence.
- **Historical:** earlier design or unretained result.

No dated, revision-linked end-to-end result is recorded here yet. Retrospectives are not acceptance evidence.

## Current audit result — 2026-07-17 America/Los_Angeles

- Host packages `gazebo_oakd_stream_sender`, `my_gazebo_package`, and `sim_camera_encoder` built successfully from clean temporary build/install directories with system setuptools 68.
- `sim_camera_decoder` built successfully on the server; this is compilation evidence, not Orange Pi runtime verification.
- Host tests ran: 26 tests, 18 failures, 2 skipped. Failures are existing Python/C++ style and copyright checks; no behavioral streaming tests exist yet.
- No Gazebo-to-Orange-Pi throughput, latency, depth-error, or restart test was run.
 The host build was reported to fail under active Miniconda; repeat it in a clean Jazzy shell.

## Host

```bash
git rev-parse HEAD
source /opt/ros/jazzy/setup.bash
cd server_sim
colcon build --symlink-install
colcon test
colcon test-result --verbose
```

## Orange Pi

```bash
git rev-parse HEAD
source /opt/ros/jazzy/setup.bash
cd edge_stack
colcon build --symlink-install --merge-install
source install/local_setup.bash
ros2 topic hz /edge/camera/rgb/image_raw
ros2 topic hz /edge/camera/depth/image_raw
```

Confirm exact transport names with `ros2 topic list`.

## Required streaming tests

1. Round-trip deterministic depth values and report per-pixel error.
2. Verify paired monotonic stamps, frame ID, 1280×800, `bgr8`, and `16UC1`.
3. Measure source/transport/output rates; decoder defaults to 5 Hz through the configurable `output_rate_hz` parameter.
4. Measure latency with synchronized clocks and state the method.
5. Test loss, restart, DDS rediscovery, and sustained operation.
6. Compare intrinsics with Gazebo configuration.

## Required adversarial passes

1. Reject invalid dimensions, encodings, parameter ranges, and malformed frames without unsafe publication.
2. Exercise missing, duplicate, delayed, out-of-order, and discontinuous timestamps.
3. Inject DDS/network loss and interruption; verify bounded memory and defined recovery.
4. Restart sender, decoder, and edge launch independently; verify clean shutdown and rediscovery.
5. Remove or fail codec/hardware dependencies and verify actionable failure without silent fallback claims.
6. Apply CPU, memory, and compression backpressure; verify the bounded newest-frame policy and safe shutdown.
7. Run sustained operation and confirm no thread growth, unbounded queueing, stale data, or resource leak.

Each behavior or defect must first be represented by a failing automated test where it can be deterministic. Hardware-only cases require a repeatable harness and retained logs/metrics.

Retain date/timezone, commit, hardware/software versions, network configuration, commands/parameters, selected producer, results, utilization, artifacts, verdict, and defects.

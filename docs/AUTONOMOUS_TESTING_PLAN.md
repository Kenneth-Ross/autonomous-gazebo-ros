# [W.I.P] Autonomous Navigation: Validation & Testing Plan (Sim-to-Real)

> **Acceptance procedure:** Automated contract coverage is implemented. Runtime
> simulation and Orange Pi requirements below are not pass results until retained
> in [VALIDATION.md](VALIDATION.md).

## 1. Overview
This plan establishes a rigid protocol to verify the **Brain-ECU (v11)** architecture. Testing is hierarchical: we first verify the low-level safety "reflexes" (ECU), then the high-level geometric intent (Brain), and finally the integrated autonomous performance.

Until the SVG import pipeline is implemented, server simulation and autonomous acceptance default to the high-resolution `catalunya` SVG-to-vector translation. Procedural `random` and coarse synthetic layouts remain opt-in fixtures, not default acceptance maps.

## 1.1 Implemented automated acceptance

The package test suites now enforce the deterministic portions of this plan:

- ECU watchdog emergency state at the 0.2-second boundary and immediately before it;
- physical steering slew rate and full-lock reversal duration;
- the exact two-second manual-override exclusion window;
- bicycle-model conversion, low-speed direction, and physical steering clamping;
- shared global/local costmap footprint and inflation settings; and
- Smac Hybrid turning radius plus regulated pure-pursuit curvature settings.

A launch test also executes the installed `driving_model_node.py` and verifies the
watchdog transition on ROS topics, the two-second manual exclusion window, smooth
full-lock steering reversal, and clean shutdown. This is ECU runtime evidence; it
does not substitute for Gazebo wheel motion or integrated Nav2 mission evidence.

Run on the simulation server:

```bash
source /opt/ros/jazzy/setup.bash
cd server_sim
colcon build --symlink-install --packages-select my_gazebo_package
colcon test --packages-select my_gazebo_package
colcon test-result --verbose
```

Run retained Gazebo vehicle acceptance after the package build:

```bash
./scripts/validation/autonomous_gazebo_acceptance.sh nominal
./scripts/validation/autonomous_gazebo_acceptance.sh adversarial
./scripts/validation/nav2_mission_acceptance.sh
./scripts/validation/nav2_wall_clearance_acceptance.sh
```

The `edge_nav2` tests are host-runnable configuration and kinematics checks. They
do not prove execution on the Orange Pi:

```bash
source /opt/ros/jazzy/setup.bash
# Jazzy colcon requires Ubuntu setuptools rather than ROS's bundled v82.
export PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH
cd edge_stack
colcon build --symlink-install --merge-install --packages-select edge_nav2
colcon test --merge-install --packages-select edge_nav2
colcon test-result --verbose
```

Host result on 2026-08-10: `my_gazebo_package` built cleanly and its scoped
suite passed 17 pytest cases with zero failures or skips; its launch
runtime suite passed 2 tests. The launched ECU logged
its 0.20-second watchdog boundary, actuator limits, and clean shutdown.

Host `edge_nav2` result on 2026-08-10: the package built with
`--symlink-install --merge-install`; 11 tests passed, one copyright check was
skipped, and zero failures occurred. The real bridge runtime test verified the
20 Hz `/nav_cmd_vel` to `/car/control_request` path, `base_link`, low-speed turn
direction, moving yaw-rate limiting, and the 0.6108 rad steering cap.

Nav2 Jazzy planner result on 2026-08-10: lifecycle plugins loaded with the
Ackermann-safe no-spin behavior tree. Smac Hybrid planned a goal directly behind
the vehicle using 90 poses over 9.545 m, a five-pose minimum measured radius of
1.438 m, 3.057 m lateral extent, and no in-place segment. Evidence:
`validation_evidence/nav2_u_turn_20260811T050152Z.log`.

Host closed-loop controller result on 2026-08-10: the real FollowPath action
completed the synthetic physical U-turn with 0.241 m goal error and 0.112 rad
yaw error, then completed the S-turn with 0.234 m error, 3.000 m/s straight
speed versus 0.519 m/s in the turn, and 13 pre-turn reduced-speed samples. No
in-place rotation command was emitted and peak steering was 0.6108 rad.
Evidence: `validation_evidence/nav2_controller_20260811T050126Z.log`.

Gazebo physical result on 2026-08-10: the real Ackermann vehicle completed the
U-turn with 0.250 m goal error, 0.101 rad yaw error, 6.000 m lateral extent,
zero spin samples, 10,745 steering-joint samples, and 0.6108 rad peak steering.
It completed the physical S-turn with 0.218 m goal error, 1.000 m/s straight
speed versus 0.902 m/s in the turn, 15,201 joint samples, and 0.6108 rad peak
steering. Evidence: `validation_evidence/gazebo_nav2_20260811T050330Z.log`.
The S-turn harness uses a bounded 1.0 m/s simulator fixture speed; this is not an
Orange Pi or hardware result.

The active track metadata contract is `DEFAULT_TRACK == "catalunya"` with
`TRACK_LAYOUTS["catalunya"]["source_type"] == "svg_vector_translation"`, at
least 100 translated points, and a declared spawn/sample distance. The
`test_track_selection_contract.py` regression also checks every server,
validation, and autonomous-racing entry point uses that default. Procedural
layouts remain opt-in fixtures.

Wall-clearance runtime result on 2026-08-10: the host-time Nav2 global raw
costmap represented the test wall as cost 254, retained inflation costs 85 at
1.0 m and 34 at 1.3 m, returned zero cost at 1.6 m, and kept the robot cell at
zero. Evidence: `validation_evidence/nav2_wall_clearance_20260811T053206Z.log`.

Physical U-turn/S-turn, wall-clearance, planner, controller, ECU, and SVG-vector
regression gates now have retained host evidence. Promotion to `[VERIFICATION]`
still requires end-to-end deployment validation; Orange Pi execution remains
unverified.

Autonomous-racing production-core result on 2026-08-10: the canonical
`autonomous_racing_msgs` package built and passed 2 interface-contract tests;
`autonomous_racing_core` built and passed 9 gtests plus cppcheck, CMake,
uncrustify, and XML lint; and `autonomous_racing` passed 11 Python contract,
launch, and lint tests with one copyright check skipped. The production host
launch resolves the typed cone-map adapter, midpoint planner, pure-pursuit
controller, safety supervisor, recorder heartbeat, and explicit prepare/start/
abort services. These are host regressions only; Gate A still requires Orange Pi
execution and retained fixed-track/unseen-track MCAP evidence.

The retained full-Gazebo lifecycle smoke passed the explicit sequence
`/racing/prepare`, `/racing/recorder/prepare`, healthy recorder heartbeat,
`/racing/recorder/start`, `/racing/start`, `/racing/abort`, and
`/racing/recorder/abort`. Evidence is
`validation_evidence/autonomous_racing_lifecycle_lifecycle_20260812T0549Z.log`;
the MCAP container summary is valid and finalized `ABORTED`; required-topic
population and perception-driven lap evidence remain separate gates. The
supervisor lifecycle process uses Fast DDS so high-rate Gazebo Cyclone DDS
traffic cannot starve control-plane service replies. This remains host evidence,
not Orange Pi Gate A.

## 1.2 Foxglove MCP-assisted review gate (non-gating)

Foxglove Desktop now offers a local MCP server for an attached agent. The
[Foxglove MCP contract](FOXGLOVE_INTEGRATION.md#mcp-assisted-review-investigation)
defines a safe use: open the retained server MCAP, inspect schemas and bounded
samples, replay/seek, search by run ID, and capture layout screenshots. Keep the
source local and offline from ROS; never point this review at the live edge
WebSocket.

This review can make failures easier to triage, but it cannot pass a gate.
Planner geometry, controller behavior, ECU timing, transport metrics, command
freshness, and MCAP integrity remain script/test-owned. MCP review is rejected
when source identity, topic/schema parity, required-topic coverage, recorder
heartbeat, or tool-surface safety checks fail. Layout, script, device, Site, and
event writes stay disabled for the mandatory run; a human may add a post-verdict
event as a separately retained annotation.

Candidate review sequence:

1. Record Foxglove Desktop version, MCP endpoint/token provenance, and the
   selected `run_id`; never store the token.
2. Open `telemetry/run_<UTC>_<run_id>/bag` as local MCAP and record source
   identity plus the discovered tool catalog.
3. Compare MCP topic/schema/time-range results with the run manifest, summary,
   `ros2 bag info`, and required-topic allowlist.
4. Inspect `/racing/*`, `/car/control_request`, `/odometry/filtered`, and
   `/racing/recorder/heartbeat`; capture confidence/fault screenshots.
5. Retain review metadata and screenshots beside the MCAP, while keeping the
   automated verdict authoritative.

MCP adoption remains `[PLAN]` until one nominal and one adversarial retained
MCAP review prove deterministic source selection, reconnect behavior, token
rotation, and no control-surface exposure. No Foxglove MCP run is claimed in
this document yet.

## 2. Phase 1: ECU Reflex & Safety (Low-Level)
**Objective**: Ensure the vehicle fails safely and respects physical limits regardless of the Brain's state.

### Test 1.1: Heartbeat Watchdog Failsafe
*   **Procedure**: 
    1. Launch Gazebo and `driving_model_node`.
    2. Publish a high-speed target to `/car/control_request` (e.g., `linear.x = 10.0`).
    3. Abruptly kill the publisher (Ctrl+C).
*   **Verification**:
    *   The car must initiate emergency braking (`brake = 1.0`) within exactly **0.2 seconds**.
    *   Verify `WATCHDOG TRIGGERED` appears in the terminal.
    *   Confirm `V_tgt` in the Heartbeat log resets to `0.00`.

### Test 1.2: Steering Slew Rate Limiting
*   **Procedure**:
    1. Send a step-change steering command: `angular.z = -0.6` (full left) followed immediately by `angular.z = 0.6` (full right).
*   **Verification**:
    *   The simulated wheels in Gazebo must turn smoothly over ~0.6 seconds (calculated by `slew_rate = 2.0 rad/s`).
    *   Verify no "teleportation" or instantaneous snapping of wheels occurs.

### Test 1.3: Manual Override Mux
*   **Procedure**:
    1. Activate autonomous driving to a target velocity.
    2. Tap the manual brake (`/car/brake`) or throttle once.
*   **Verification**:
    *   ECU must ignore the Brain for **2.0 seconds** (`_is_manual_override_active`).
    *   Verify the autonomous `target_vel` remains suppressed until the timeout expires.

---

## 3. Phase 2: Brain Intent & Kinematics (Mid-Level)
**Objective**: Verify the Orange Pi correctly translates high-level plans into vehicle targets.

### Test 2.1: Bicycle Model Accuracy
*   **Procedure**:
    1. Use `ros2 topic pub` to send a `Twist` to `/nav_cmd_vel` [1.0 m/s, 0.5 rad/s].
*   **Verification**:
    *   Echo `/car/control_request` and verify the `angular.z` (Target Steering Angle) correctly calculates $\delta = \arctan(L \cdot \omega / v)$.
    *   For $L=1.511$, $v=1.0$, $\omega=0.5$, $\delta$ should be $\approx 0.64$ rad (clamped to `max_steering_angle`).

### Test 2.2: Nav2 Footprint & Inflation
*   **Procedure**:
    1. Drive the car near a wall in simulation.
*   **Verification**:
    *   Check Foxglove to ensure the **Inflation Layer** on the costmap matches the vehicle's `2.0m x 1.25m` footprint plus a safety buffer.

---

## 4. Phase 3: Integrated Autonomous Mission (High-Level)
**Objective**: Verify end-to-end SLAM -> Nav2 -> Bridge -> ECU stability.

### Test 3.1: The "Tight U-Turn" (Feasibility Test)
*   **Procedure**:
    1. Set a navigation goal directly behind the car.
*   **Verification**:
    *   **Planner**: `SmacPlannerHybrid` must generate a path that respects the `minimum_turning_radius: 1.5`.
    *   **Execution**: The car must execute the turn without stopping or attempting to "spin" in place.

### Test 3.2: Curvature-Regulated Braking
*   **Procedure**:
    1. Set a high-speed goal (10 m/s) through a sequence of sharp S-turns.
*   **Verification**:
    *   **Observation**: The `RegulatedPurePursuitController` must proactively reduce the ECU's `target_vel` *before* the car enters the turn.
    *   **Success**: The car completes the course without skidding off-track or exceeding kinematic limits.

---

## 5. Tuning Guide: ECU Velocity PID
If the car "surges" (accelerates/brakes repeatedly) during autonomous flight, follow this sequence:
1.  **Lower $K_i$ to 0.0**: Integration windup is the #1 cause of surging.
2.  **Tune $K_p$**: Increase until the car is responsive but doesn't "hunt" for speed.
3.  **Tune $K_d$**: Increase to dampen the "hunting" behavior caused by Ethernet latency.
4.  **Slow Nav2**: If surging persists, reduce `controller_frequency` in `nav2_params.yaml` to 10Hz to give the ECU PID more "breathing room" between target updates.

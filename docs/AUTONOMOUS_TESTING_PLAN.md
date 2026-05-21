# Autonomous Navigation: Validation & Testing Plan (Sim-to-Real)

## 1. Overview
This plan establishes a rigid protocol to verify the **Brain-ECU (v11)** architecture. Testing is hierarchical: we first verify the low-level safety "reflexes" (ECU), then the high-level geometric intent (Brain), and finally the integrated autonomous performance.

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

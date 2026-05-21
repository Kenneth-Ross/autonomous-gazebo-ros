# Nav2 Ackermann System: Implementation Retrospective & Future Blockers

## 1. Final Architecture (v9 Hardened)
The system implements a **High-Compute Edge / Low-Level ECU** split, optimized for wired connectivity (Ethernet/UART).

*   **Orange Pi 5 (The Brain)**: 
    *   **RTAB-Map**: Localization & 2D Occupancy Mapping.
    *   **Nav2**: Global (Smac Hybrid-A*) and Local (Regulated Pure Pursuit) planning.
    *   **Ackermann Bridge**: Calculates high-level **Target Velocity** and **Target Steering Angle** using the Bicycle Model.
    *   **Packet**: Unified `geometry_msgs/TwistStamped` sent to `/car/control_request`.
*   **Desktop (The ECU)**:
    *   **Low-Level Control**: Implements the **Velocity PID Loop** internally.
    *   **Watchdog**: 500ms heartbeat monitor for wired connection integrity.
    *   **Failsafe**: Emergency braking if control targets are lost.
    *   **Interface**: Maps PID-modulated throttle/brake and target steering to the Gazebo Ackermann plugin.

## 2. Testing Procedures (Rigid Protocol)

### Phase A: SIL (Software-In-Loop) Math Validation
1.  **Objective**: Verify the Brain sends correct high-level targets.
2.  **Procedure**: Publish `/nav_cmd_vel` [1.0 m/s, 0.2 rad/s].
3.  **Validation**: Verify `/car/control_request` contains `linear.x = 1.0` (m/s) and `angular.z` (radians) matches the wheelbase-normalized angle.

### Phase B: HIL (Hardware-In-Loop) Safety Validation
1.  **Objective**: Verify the ECU's internal PID and failsafe.
2.  **Procedure**: Launch full stack. Manually kill the Orange Pi bridge node.
3.  **Validation**: Verify the car in Gazebo applies brakes immediately and the console logs `WATCHDOG TRIGGERED`. Verify the PID-controlled acceleration is smooth.

## 3. Future Integration Blockers

### A. UART Throughput & Latency
*   **Problem**: While wired, high-baud UART (e.g., 921600) is required to ensure the 20Hz control loop doesn't saturate the serial bus when multiplexed with other telemetry.
*   **Mitigation**: Use a binary protocol or efficient serialization (Protobuf/Micro-ROS) for the real UART link.

### B. RTAB-Map Transform Latency
*   **Problem**: RTAB-Map's `map -> odom` transform is compute-intensive. If loop closure takes >200ms, Nav2 will experience a 'jump' in localized pose.
*   **Mitigation**: Set `transform_tolerance: 0.5` in Nav2 and use a high-frequency EKF for local smoothing.


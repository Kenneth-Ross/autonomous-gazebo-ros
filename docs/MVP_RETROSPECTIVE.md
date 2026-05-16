# RTAB-Map SLAM MVP: Project Retrospective

## 1. What Worked: The "Virtual OAK-D" Success
The primary achievement of this phase was replicating the industrial specifications of a physical OAK-D camera within a Gazebo-to-Edge pipeline.

*   **Vertical Super-Frame Architecture**: Stacking RGB, MSB Depth, and LSB Depth vertically (1280x2400) into a single HEVC stream guaranteed perfect temporal synchronization.
*   **16-bit Depth Preservation**: By replicating depth bits across BGR channels (utilizing the HEVC Luminance/Y channel), we preserved millimeter-level precision over a lossy 8-bit video codec.
*   **RK3588 Hardware Acceleration**: Offloading decoding to the `hevc_rkmpp` VPU allowed the Orange Pi 5 to maintain 30 FPS while leaving CPU head-room for RTAB-Map and EKF processing.
*   **The "Island Strategy"**: Keeping high-bandwidth raw data on the local Ethernet link while bridging only low-bandwidth metadata (TFs, Maps) to Foxglove Studio over Tailscale.

## 2. Successes & Architectural Wins
*   **Jazzy Migration**: Moving to ROS 2 Jazzy (Ubuntu 24.04) provided modern `ffmpeg_image_transport` plugins that integrated seamlessly with Rockchip's patched libraries.
*   **Visual Odometry Quality**: Logs confirmed high-quality VO (quality > 300) using reconstructed depth, proving that the simulation-to-edge reconstruction is mapping-ready.
*   **Digital Twin Integration**: Successfully bridged Gazebo ground truth to the Edge, allowing side-by-side performance verification in Foxglove.

## 3. Failures & Lessons Learned (What to Avoid)
*   **The "DDS Broadcast Storm"**:
    *   *Failure*: Initially publishing the 1280x2400 raw frame on a global topic caused CycloneDDS to attempt a 2.1 Gbps transmission over a 1 Gbps link, crashing the network.
    *   *Lesson*: Use **local-only namespaces** (e.g., `~/raw_image_local`) for massive buffers that should only be consumed by local encoders/decoders.
*   **TF Tree Fragmentation**:
    *   *Failure*: SLAM failed to initialize because the EKF was missing IMU inputs and had topic mismatches, resulting in "unconnected trees."
    *   *Lesson*: Always verify sensor bridges early. A single missing IMU topic can prevent the entire coordinate system from anchoring.
*   **Setuptools Deprecation**:
    *   *Failure*: Build warnings from dash-separated options in `setup.cfg`.
    *   *Lesson*: Modern ROS 2 (Jazzy+) requires underscores (`script_dir`) instead of dashes.

## 4. Future Plans: The Path to Autonomous Racing
*   **Semantic NPU Layer**: Transition from raw geometry to intelligent landmarks. Use the RK3588 NPU to run YOLOv11 for 3D cone detection.
*   **Nav2 Integration**: Implement the ROS 2 Navigation Stack using the 2D Occupancy Grid we are now natively generating.
*   **Loop Closure Optimization**: Fine-tune the RTAB-Map database to handle high-speed racing environments with aggressive lighting/texture changes.

---
**Status**: MVP Verified. Ready for Semantic Integration.

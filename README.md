# Autonomous Gazebo ROS

This project enables autonomous navigation and SLAM in a Gazebo simulation by offloading heavy processing (like computer vision and SLAM) to an edge device (e.g., Orange Pi 5).

## Overview

- **Simulation Host:** Runs Gazebo and ROS2. Streams camera data over the network using GStreamer or ROS2 topics.
- **Edge Device:** Receives the stream, performs inference (YOLOv11), and runs SLAM (ORB-SLAM3 or RTAB-Map).
- **Communication:** Uses ROS2 for control and state, and GStreamer for high-performance video streaming.

## Project Structure

- `ros2_ws/`: ROS2 workspace for the simulation host.
  - `my_gazebo_package`: Contains URDF models and Gazebo worlds.
  - `gazebo_oakd_stream_sender`: Node for streaming OAK-D camera data.
- `ros2_ws_receiver/`: ROS2 workspace for the edge device.
  - `edge_device_slam_node`: ORB-SLAM3 integration for the edge device.
  - `rtabmap_bridge`: Bridge for RTAB-Map SLAM.
- `external/`: Third-party dependencies.
  - `ORB_SLAM3`: Modified version of ORB-SLAM3 for edge processing.
  - `rknpu2`: Rockchip NPU driver and API.
- `scripts/`: Deployment and setup scripts for both host and edge device.

## Getting Started

### Prerequisites

- ROS2 Foxy or Humble
- Gazebo Ignition (Fortress/Garden)
- GStreamer (for video streaming)

### Host Setup

1. Build the ROS2 workspace:
   ```bash
   cd ros2_ws
   colcon build
   ```
2. Launch the simulation:
   ```bash
   source install/setup.bash
   ros2 launch my_gazebo_package launch_sim.launch.py
   ```

### Edge Device Setup

1. Run the setup script for your device:
   ```bash
   ./scripts/setup_orangepi_foxy.sh
   ```
2. Build the receiver workspace:
   ```bash
   cd ros2_ws_receiver
   colcon build
   ```

## Documentation

- [Tutorial: Offloading Gazebo Camera Data](docs/TUTORIAL.md)
- [Edge Device SLAM Plan](ros2_ws/docs/edge_device_slam_plan.md)

## License

[Add License Info Here]

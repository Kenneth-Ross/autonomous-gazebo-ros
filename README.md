# Autonomous Gazebo ROS

This project enables autonomous navigation and SLAM in a Gazebo simulation by offloading heavy processing (like computer vision and SLAM) to an edge device (e.g., Orange Pi 5).

## Overview

- **Simulation Host:** Runs Gazebo and ROS2. Streams camera data over the network using GStreamer or ROS2 topics.
- **Edge Device:** Receives the stream, performs inference (YOLOv11), and runs SLAM (RTAB-Map).
- **Communication:** Uses ROS2 for control and state, and GStreamer for high-performance video streaming.

## Project Structure

- `ros2_ws/`: ROS2 workspace for the simulation host.
  - `my_gazebo_package`: Contains URDF models and Gazebo worlds.
  - `gazebo_oakd_stream_sender`: Node for streaming OAK-D camera data.
- `ros2_ws_receiver/`: ROS2 workspace for the edge device.
  - `rtabmap_bridge`: Bridge for RTAB-Map SLAM.
  - `edge_oakd_camera_node`: Receiver for OAK-D camera streams.
  - `edge_nav2`: Navigation stack configuration for the edge device.
- `external/`: Third-party dependencies.
  - `rknpu2`: Rockchip NPU driver and API.
- `scripts/`: Deployment and setup scripts for both host and edge device.

## Getting Started

### Prerequisites

- ROS 2 Jazzy (for Ubuntu 24.04) or Humble (for Ubuntu 22.04)
- Gazebo Harmonic or Ignition
- GStreamer (with Rockchip multimedia plugins for edge devices)

### Host Setup

1. Build the ROS 2 workspace:
   ```bash
   cd ros2_ws
   colcon build
   ```
2. Launch the simulation and streamer:
   ```bash
   source install/setup.bash
   ros2 launch gazebo_oakd_stream_sender stream_to_remote.launch.py host:=<EDGE_DEVICE_IP>
   ```

### Edge Device Setup

1. Run the setup script for Ubuntu 24.04:
   ```bash
   ./scripts/setup_orangepi_receiver.sh
   ```
2. Build the receiver workspace:
   ```bash
   cd ros2_ws_receiver
   source /opt/ros/jazzy/setup.bash
   colcon build
   ```

## Documentation

- [Tutorial: Offloading Gazebo Camera Data](docs/TUTORIAL.md)
- [RTAB-Map SLAM Plan](plans/rtabmap_edge_slam_plan.md)

## License

[Add License Info Here]

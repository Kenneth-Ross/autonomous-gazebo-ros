# Foxglove Integration & Digital Twin Architecture

This document describes the architecture for remote visualization and the "Digital Twin" ground truth integration used in this project.

## Table of Contents
1. [Overview](#overview)
2. [Data Flow Diagram](#data-flow-diagram)
3. [Ground Truth Path](#ground-truth-path)
4. [Edge Visualization (Orange Pi)](#edge-visualization-orange-pi)
5. [Remote Monitoring & Island Strategy](#remote-monitoring--island-strategy)
6. [Digital Twin Debugging Guide](#digital-twin-debugging-guide)

---

## Overview

The system uses **Foxglove Studio** for remote monitoring. To maintain high performance on the Edge device (Orange Pi 5) while allowing remote debugging, we employ an **"Island Strategy"**:
- **High-Bandwidth Data (RGB-D)**: Stays on the local `wlan0` network between the Host and the Edge.
- **Low-Bandwidth Metadata (TFs, Pose, Status)**: Streamed over **Tailscale VPN** to remote clients via the **Foxglove Bridge**.

A key feature is the **Digital Twin**, where the Gazebo ground truth pose is sent to the Edge device to allow side-by-side comparison with the SLAM-estimated pose.

## Data Flow Diagram

```mermaid
graph TD
    subgraph Host_Machine [Host Machine (Gazebo Sim)]
        GZ[Gazebo Sim] -->|PosePublisher 30Hz| GZ_TOPIC[/model/my_robot/pose/]
        GZ_TOPIC -->|gz.msgs.Pose_V| GZ_BRIDGE[ros_gz_bridge]
        GZ_BRIDGE -->|tf2_msgs/TFMessage| ROS_GT_TOPIC[/ground_truth/tf/]
    end

    subgraph Orange_Pi [Orange Pi 5 (Edge Device)]
        ROS_GT_TOPIC -->|wlan0 / CycloneDDS| GT_BROADCASTER[ground_truth_broadcaster]
        GT_BROADCASTER -->|Local /tf| TF_TREE[TF Tree: world -> ground_truth_base_link]
        STATIC_TF[static_transform_publisher] -->|Local /tf| TF_TREE
        TF_TREE -->|Metadata| FOX_BRIDGE[Foxglove Bridge :8765]
        
        RTAB[RTAB-Map SLAM] -->|Metadata| FOX_BRIDGE
        RTAB -->|Local /tf| TF_TREE
    end

    subgraph Remote_Client [Remote Client (Foxglove Studio)]
        FOX_BRIDGE -->|Tailscale VPN| FOX_STUDIO[Foxglove Studio]
    end

    style Host_Machine fill:#f9f,stroke:#333,stroke-width:2px
    style Orange_Pi fill:#bbf,stroke:#333,stroke-width:2px
    style Remote_Client fill:#dfd,stroke:#333,stroke-width:2px
```

## Ground Truth Path

To visualize the "True" position of the robot against the SLAM estimate:
1.  **Gazebo Side**: The `PosePublisher` plugin in the robot's URDF is configured to publish the model pose at **30Hz**.
2.  **Bridge**: The `ros_gz_bridge` maps the Gazebo `Pose_V` message to a ROS 2 `tf2_msgs/TFMessage` on the topic `/ground_truth/tf`.
3.  **Throttling**: By using the `PosePublisher` update frequency, we avoid saturating the network with high-frequency physics updates.

## Edge Visualization (Orange Pi)

The Orange Pi runs several nodes to facilitate visualization:
- **Foxglove Bridge**: Listens on `0.0.0.0:8765`. It provides a WebSocket interface for Foxglove Studio.
- **Ground Truth Broadcaster**: A custom Python node that:
    - Subscribes to `/ground_truth/tf`.
    - Remaps the child frame from `my_robot` to `ground_truth_base_link`.
    - Sets the parent frame to `world`.
    - Publishes to the local `/tf` topic.
- **Static Transform**: A `static_transform_publisher` anchors `world` to `map` at the origin, allowing the SLAM trajectory (in `map` frame) and Ground Truth (in `world` frame) to be aligned.

## Remote Monitoring & Island Strategy

| Network | Traffic Type | Purpose |
| :--- | :--- | :--- |
| **wlan0 (Local)** | RGB-D Images, Raw Sensors | High-bandwidth data for SLAM processing. |
| **Tailscale (VPN)** | TFs, Markers, Low-res Poses | Remote monitoring and "Digital Twin" visualization. |

**CycloneDDS Configuration**: To prevent ROS 2 from attempting to send large image packets over the VPN (which causes crashes and lag), we force CycloneDDS to bind only to `wlan0`.

## Digital Twin Debugging Guide

If the Digital Twin or Foxglove visualization is not working, follow these steps:

### 1. Verify Ground Truth Flow
On the Orange Pi, check if the ground truth messages are arriving from the host:
```bash
ros2 topic echo /ground_truth/tf
```
If no data appears, check the `ros_gz_bridge` on the Host machine.

### 2. Check TF Tree Consistency
The Digital Twin relies on a specific TF structure. Verify it using:
```bash
ros2 run tf2_tools view_frames
```
Expected links:
- `world` -> `ground_truth_base_link` (via `ground_truth_broadcaster`)
- `world` -> `map` (via `static_transform_publisher`)
- `map` -> `odom` -> `base_link` (via SLAM/EKF)

### 3. Foxglove Bridge Status
Ensure the bridge is running and reachable:
```bash
netstat -tuln | grep 8765
```
In Foxglove Studio, connect to the Tailscale IP of the Orange Pi (e.g., `ws://100.x.y.z:8765`).

### 4. Island Strategy Check
If Foxglove is laggy, ensure you are NOT subscribing to raw image topics (e.g., `/camera/rgb/image_raw`) over the VPN. Use compressed streams or metadata-only views for remote monitoring.

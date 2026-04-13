# OAK-D Gazebo Stream Receiver Setup (for Orange Pi 5 Pro)

This document outlines the setup for the ROS2 receiver nodes that subscribe to GStreamer UDP streams and publish them as ROS2 Image topics.

## 1. Conda Environment Setup

This setup is designed to run within a self-contained Conda environment to ensure all GStreamer and ROS2 dependencies are managed correctly.

**Run these commands on your Orange Pi 5 Pro:**

```bash
# Create a new conda environment
conda create -n ros_gst_receiver python=3.10 -y

# Activate the environment
conda activate ros_gst_receiver

# Install dependencies from conda-forge
# This can take some time
conda install -c conda-forge 
    gstreamer 
    gst-plugins-base 
    gst-plugins-good 
    gst-plugins-ugly 
    gst-libav 
    pygobject 
    numpy 
    opencv -y
```

## 2. ROS2 Installation

Install ROS2 Jazzy within the activated conda environment.

```bash
# Ensure you are in the ros_gst_receiver conda environment
conda install -c conda-forge ros-jazzy-ros-base ros-jazzy-cv-bridge -y
```

## 3. System Dependencies

While most packages are in conda, some system-level dependencies might be required.

```bash
sudo apt-get update && sudo apt-get install -y build-essential
```
---
*This file will be updated as we proceed.*

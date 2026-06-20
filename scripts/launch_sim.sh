#!/bin/bash

# Configuration
WORKSPACE_DIR="/home/k-dev/dev/ros2_gazebo/ros2_ws"
PACKAGE_NAME="my_gazebo_package"
LAUNCH_FILE="gazebo.launch.py"

# 1. Enable Network Networking
export GZ_IP=127.0.0.1
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
# CYCLONEDDS_URI removed to allow default multi-interface binding (lo + eno1)
unset CYCLONEDDS_URI

# Force NVIDIA discrete GPU for hybrid rendering
export __NV_PRIME_RENDER_OFFLOAD=1
export __GLX_VENDOR_LIBRARY_NAME=nvidia
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json
export QT_QPA_PLATFORM=xcb

# 2. Source ROS2 and Workspace
if [ -f "/opt/ros/jazzy/setup.bash" ]; then
    source /opt/ros/jazzy/setup.bash
fi

if [ -f "$WORKSPACE_DIR/install/setup.bash" ]; then
    source "$WORKSPACE_DIR/install/setup.bash"
else
    echo "Error: Workspace setup.bash not found. Did you build the project?"
    exit 1
fi

# 3. Handle Arguments
# Usage: ./launch_sim.sh [track_name] [headless_true_false]
# Track names: oval, figure_eight, hairpin, slalom, rectangle, random (default)
TRACK_NAME=${1:-"random"}
HEADLESS=${2:-"false"}

echo "------------------------------------------------"
echo "Launching ROS2 Gazebo Simulation"
echo "Initial Track: $TRACK_NAME"
echo "Headless Mode: $HEADLESS"
echo "------------------------------------------------"

# 4. Cleanup old processes (Optional but recommended)
pkill -9 -f "gz sim" || true
pkill -9 -f "ros2" || true

# 5. Launch
trap "kill 0" EXIT

echo "Starting OAK-D Stream Sender..."
ros2 launch gazebo_oakd_stream_sender stream_to_remote.launch.py host:=10.10.12.9 &

echo "Starting Gazebo Simulation..."
ros2 launch $PACKAGE_NAME $LAUNCH_FILE initial_track:=$TRACK_NAME headless:=$HEADLESS

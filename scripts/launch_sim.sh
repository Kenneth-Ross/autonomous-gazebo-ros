#!/bin/bash

# Configuration
WORKSPACE_DIR="/home/k-dev/dev/ros2_gazebo/ros2_ws"
PACKAGE_NAME="my_gazebo_package"
LAUNCH_FILE="gazebo.launch.py"

# 1. Force Localhost Networking
# This prevents ROS2 and Gazebo from binding to VPN/WiFi interfaces (like Tailscale)
# which causes service timeouts and discovery issues.
export GZ_IP=127.0.0.1
export ROS_LOCALHOST_ONLY=1

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
# Usage: ./launch_sim.sh [track_name]
# Track names: oval, figure_eight, hairpin, slalom, rectangle, random (default)
TRACK_NAME=${1:-"random"}

echo "------------------------------------------------"
echo "Launching ROS2 Gazebo Simulation"
echo "Network: Localhost Only"
echo "Initial Track: $TRACK_NAME"
echo "------------------------------------------------"

# 4. Cleanup old processes (Optional but recommended)
pkill -9 -f "gz sim" || true
pkill -9 -f "ros2" || true

# 5. Launch
ros2 launch $PACKAGE_NAME $LAUNCH_FILE initial_track:=$TRACK_NAME

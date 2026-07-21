#!/usr/bin/env bash

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd -- "$SCRIPT_DIR/../server_sim" && pwd)"
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
if [ ! -f "/opt/ros/jazzy/setup.bash" ]; then
    echo "Error: ROS 2 Jazzy was not found at /opt/ros/jazzy." >&2
    exit 1
fi
set +u
source /opt/ros/jazzy/setup.bash
set -u

if [ -f "$WORKSPACE_DIR/install/setup.bash" ]; then
    set +u
    source "$WORKSPACE_DIR/install/setup.bash"
    set -u
else
    echo "Error: Workspace setup.bash not found. Did you build the project?"
    exit 1
fi

# 3. Handle Arguments
# Usage: ./launch_sim.sh [track_name] [headless_true_false]
# Track names: oval, figure_eight, hairpin, slalom, rectangle, random (default)
TRACK_NAME=${1:-random}
HEADLESS=${2:-false}

echo "------------------------------------------------"
echo "Launching ROS2 Gazebo Simulation"
echo "Initial Track: $TRACK_NAME"
echo "Headless Mode: $HEADLESS"
echo "------------------------------------------------"

# 4. Launch. Only stop the stream launch started by this script; do not kill
# unrelated ROS or Gazebo processes on the machine.
STREAM_PID=""
cleanup() {
    trap - EXIT INT TERM
    if [[ -n "$STREAM_PID" ]] && kill -0 "$STREAM_PID" 2>/dev/null; then
        kill -TERM "$STREAM_PID" 2>/dev/null || true
        wait "$STREAM_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

echo "Starting OAK-D Stream Sender..."
ros2 launch gazebo_oakd_stream_sender stream_to_remote.launch.py &
STREAM_PID=$!

echo "Starting Gazebo Simulation..."
ros2 launch "$PACKAGE_NAME" "$LAUNCH_FILE" \
    "initial_track:=$TRACK_NAME" "headless:=$HEADLESS"

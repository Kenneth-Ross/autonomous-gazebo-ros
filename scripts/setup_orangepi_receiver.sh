#!/bin/bash
set -e

echo "--- Starting Optimized ROS 2 Jazzy Setup for RK3588 ---"

# Set up ROS 2 APT Repository
echo "--- Setting up ROS 2 APT repository... ---"
sudo apt-get update
sudo apt-get install -y software-properties-common curl
sudo add-apt-repository universe -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Install ROS 2 Jazzy (Base) and bridge dependencies
echo "--- Installing ROS 2 Jazzy (Base) and Bridge Dependencies... ---"
sudo apt-get update
sudo apt-get install -y \
    ros-jazzy-ros-base \
    ros-dev-tools \
    ros-jazzy-cv-bridge \
    ros-jazzy-rtabmap-ros \
    ros-jazzy-robot-localization \
    ros-jazzy-rmw-cyclonedds-cpp \
    ros-jazzy-depthimage-to-laserscan \
    python3-opencv \
    python3-numpy \
    python3-gi \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev

# Build the workspace
echo "--- Building the ROS2 workspace... ---"
# Assuming we are in the repo root on the OPi
WORKSPACE_DIR="$HOME/ros2_gazebo/ros2_ws_receiver"
mkdir -p "$WORKSPACE_DIR/src"
cd "$WORKSPACE_DIR"
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install

echo "--- Build Complete ---"
echo "--- Orange Pi setup is complete. ---"

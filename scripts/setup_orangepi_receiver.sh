#!/bin/bash
set -e

echo "--- Starting Native ROS 2 Jazzy Setup (v2) ---"

# Set up ROS 2 APT Repository
echo "--- Setting up ROS 2 and Rockchip Multimedia APT repositories... ---"
sudo apt-get update
sudo apt-get install -y software-properties-common
sudo add-apt-repository universe -y
sudo add-apt-repository ppa:jjriek/rockchip-multimedia -y
sudo apt-get update
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Install ROS 2 Jazzy and all dependencies on a single line
echo "--- Installing ROS 2 Jazzy, GStreamer, and Python dependencies via APT... ---"
sudo apt-get update
sudo apt-get install -y \
    ros-jazzy-desktop \
    ros-dev-tools \
    ros-jazzy-cv-bridge \
    python3-opencv \
    python3-numpy \
    python3-gi \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav

# Build the workspace
echo "--- Building the ROS2 workspace 'ros2_ws_receiver'... ---"
mkdir -p ~/ros2_ws_receiver/src
cd ~/ros2_ws_receiver
source /opt/ros/jazzy/setup.bash
colcon build

echo "--- Build Complete ---"
echo "--- Orange Pi setup is complete with native ROS 2 Jazzy. ---"

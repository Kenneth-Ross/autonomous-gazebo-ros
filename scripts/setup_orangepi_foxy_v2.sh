#!/bin/bash
set -e

echo "--- Starting Native ROS 2 Foxy Setup (v3 - with apt fix) ---"

# Set up ROS 2 APT Repository
echo "--- Setting up ROS 2 APT repository... ---"
sudo apt-get update
sudo apt-get install -y software-properties-common
sudo add-apt-repository universe -y
sudo apt-get update
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt-get update

# Attempt to fix broken packages and upgrade system
echo "--- Fixing any broken dependencies and upgrading system packages... ---"
sudo apt-get --fix-broken install -y
sudo apt-get upgrade -y

# Install ROS 2 Foxy first
echo "--- Installing ROS 2 Foxy... ---"
sudo apt-get install -y ros-foxy-desktop ros-dev-tools

# Install other dependencies
echo "--- Installing GStreamer and Python dependencies... ---"
sudo apt-get install -y python3-opencv python3-numpy python3-gi gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly gstreamer1.0-libav

# Clone vision_opencv for Foxy
echo "--- Cloning vision_opencv repository (for cv_bridge on Foxy) ---"
mkdir -p ~/ros2_ws_receiver/src
cd ~/ros2_ws_receiver/src
if [ ! -d "vision_opencv" ]; then
    git clone https://github.com/ros-perception/vision_opencv.git -b foxy
else
    echo "vision_opencv directory already exists, switching to foxy branch."
    cd vision_opencv
    git checkout foxy
    git pull
    cd ..
fi

# Build the workspace
echo "--- Building the ROS2 workspace 'ros2_ws_receiver'... ---"
cd ~/ros2_ws_receiver
source /opt/ros/foxy/setup.bash
colcon build

echo "--- Build Complete ---"
echo "--- Orange Pi setup is complete with native ROS 2 Foxy. ---"

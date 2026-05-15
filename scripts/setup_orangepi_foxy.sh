#!/bin/bash
set -e

echo "--- Starting Native ROS 2 Foxy Setup for Orange Pi 5 (Official 20.04) ---"

# 1. Set up ROS 2 APT Repository (Standard)
echo "--- Setting up ROS 2 APT repository... ---"
sudo apt-get update
sudo apt-get install -y software-properties-common curl
sudo add-apt-repository universe -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# 2. Install ROS 2 and Base GStreamer Tools
echo "--- Fixing potential package skews and installing dependencies... ---"
sudo apt-get update
sudo apt-get upgrade -y  # This often resolves the "1.1.2 vs 1.1.1" dependency version mismatch

echo "--- Installing ROS 2 Foxy and support libraries... ---"
sudo apt-get install -y \
    ros-foxy-desktop \
    ros-foxy-rtabmap-ros \
    ros-foxy-robot-localization \
    ros-foxy-depthimage-to-laserscan \
    ros-foxy-cv-bridge \
    python3-opencv \
    python3-numpy \
    python3-gi \
    ros-foxy-rmw-cyclonedds-cpp \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav

# Fix any lingering dependency issues
sudo apt-get install -f -y

# 3. Verify Hardware Acceleration Presence
echo "--- Verifying Rockchip Hardware Acceleration... ---"
if gst-inspect-1.0 mppvideodec > /dev/null 2>&1; then
    echo "SUCCESS: mppvideodec found (VPU Acceleration Available)"
else
    echo "WARNING: mppvideodec NOT found. Hardware decoding may not work."
    echo "You may need to install the vendor-specific GStreamer plugins from the Orange Pi resources."
fi

# 4. Build the local ROS 2 workspace
echo "--- Building the local ROS 2 workspace... ---"
mkdir -p ~/ros2_ws_receiver/src
cd ~/ros2_ws_receiver
source /opt/ros/foxy/setup.bash

# Ensure we have the necessary Python dependencies for the bridge
pip3 install numpy --upgrade

colcon build --symlink-install

echo "--- Setup Complete ---"
echo "To ensure large depth packets are handled correctly, use Cyclone DDS:"
echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp"

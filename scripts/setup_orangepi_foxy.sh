#!/bin/bash
set -e

echo "--- Starting Native ROS 2 Foxy Setup for Orange Pi 5 ---"

# 1. Set up ROS 2 APT Repository
echo "--- Setting up ROS 2 APT repository... ---"
sudo apt-get update
sudo apt-get install -y software-properties-common curl
sudo add-apt-repository universe -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# 2. Set up Rockchip Multimedia PPA for Hardware Acceleration
echo "--- Setting up Rockchip Multimedia PPA... ---"
sudo add-apt-repository ppa:liujianfeng1994/rockchip-multimedia -y
sudo apt-get update

# 3. Install ROS 2 Foxy and Optimized GStreamer Binaries
echo "--- Installing ROS 2 Foxy and Rockchip-optimized GStreamer... ---"
sudo apt-get install -y \
    ros-foxy-desktop \
    ros-foxy-rtabmap-ros \
    ros-foxy-robot-localization \
    ros-foxy-depthimage-to-laserscan \
    ros-foxy-cv-bridge \
    gstreamer1.0-rockchip \
    librockchip-mpp-dev \
    librockchip-vpu0 \
    rockchip-multimedia-config \
    python3-opencv \
    python3-numpy \
    python3-gi \
    ros-foxy-rmw-cyclonedds-cpp

# 4. Build the workspace (using system binaries)
echo "--- Building the local ROS 2 workspace... ---"
mkdir -p ~/ros2_ws_receiver/src
cd ~/ros2_ws_receiver
source /opt/ros/foxy/setup.bash

# Note: We NO LONGER clone vision_opencv. We use the system-installed ros-foxy-cv-bridge.
colcon build --symlink-install

echo "--- Setup Complete ---"
echo "To ensure large depth packets are handled correctly, use Cyclone DDS:"
echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp"

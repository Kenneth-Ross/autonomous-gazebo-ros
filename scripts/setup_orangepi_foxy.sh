#!/bin/bash
set -e

echo "--- Starting Native ROS 2 Foxy Setup ---"

# Set up ROS 2 APT Repository
echo "--- Setting up ROS 2 APT repository... ---"
sudo apt-get update
sudo apt-get install -y software-properties-common
sudo add-apt-repository universe -y
sudo apt-get update
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Set up Rockchip Multimedia PPA for Hardware Acceleration
echo "--- Setting up Rockchip Multimedia PPA... ---"
sudo add-apt-repository ppa:liujianfeng1994/rockchip-multimedia -y
sudo apt-get update

# Install ROS 2 Foxy, Rockchip MPP, and Optimized GStreamer
echo "--- Installing ROS 2 Foxy and Rockchip-optimized GStreamer... ---"
sudo apt-get install -y \
    ros-foxy-desktop \
    ros-foxy-rtabmap-ros \
    ros-foxy-robot-localization \
    ros-foxy-depthimage-to-laserscan \
    gstreamer1.0-rockchip \
    librockchip-mpp-dev \
    librockchip-vpu0 \
    rockchip-multimedia-config \
    python3-opencv \
    python3-numpy \
    python3-gi

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

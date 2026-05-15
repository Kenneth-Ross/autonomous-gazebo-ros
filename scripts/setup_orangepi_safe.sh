#!/bin/bash
set -e

echo "--- Starting SAFE ROS 2 Foxy Setup for Orange Pi 5 (Focal) ---"
echo "--- This version respects your pre-installed GStreamer hardware acceleration. ---"

# 1. Repair potential broken APT state from previous attempts
echo "--- Repairing APT state... ---"
sudo apt-get update
sudo apt-get install -f -y

# 2. Set up ROS 2 APT Repository (Standard)
if [ ! -f /etc/apt/sources.list.d/ros2.list ]; then
    echo "--- Setting up ROS 2 APT repository... ---"
    sudo apt-get install -y software-properties-common curl
    sudo add-apt-repository universe -y
    sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
    sudo apt-get update
fi

# 3. Identify and Protect Vendor Packages
echo "--- Protecting existing GStreamer and OpenCV packages... ---"
# This prevents APT from trying to replace them with standard Ubuntu versions
for pkg in $(dpkg -l | grep -E "gstreamer|opencv" | awk '{print $2}'); do
    echo "Holding $pkg"
    sudo apt-mark hold $pkg || true
done

# 4. Install MINIMAL ROS 2 Foxy
# We use ros-foxy-ros-base to avoid pulling in desktop/gui dependencies that conflict with vendor libs.
# We use --no-install-recommends to be surgical.
echo "--- Installing MINIMAL ROS 2 Foxy... ---"
sudo apt-get install -y --no-install-recommends \
    ros-foxy-ros-base \
    ros-foxy-cv-bridge \
    ros-foxy-rmw-cyclonedds-cpp \
    ros-foxy-robot-localization \
    python3-gi \
    python3-numpy \
    python3-opencv

# 5. Build the workspace
echo "--- Building the local ROS 2 workspace... ---"
mkdir -p ~/ros2_ws_receiver/src
cd ~/ros2_ws_receiver
# Note: We need to source ROS 2 to build
source /opt/ros/foxy/setup.bash
colcon build --symlink-install --packages-select rtabmap_bridge edge_oakd_camera_node

echo "--- Setup Complete ---"
echo "Verification: Running 'gst-inspect-1.0 mppvideodec'..."
if gst-inspect-1.0 mppvideodec > /dev/null 2>&1; then
    echo "SUCCESS: Hardware acceleration is still intact!"
else
    echo "WARNING: mppvideodec not found. You may need to reinstall vendor plugins."
fi

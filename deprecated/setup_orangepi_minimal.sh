#!/bin/bash
set -e

# --- Minimalist Setup Script for Orange Pi 5 (RK3588) ---
# Goal: Install ROS 2 Foxy while respecting vendor-optimized GStreamer/OpenCV.

echo "--- [1/5] Identifying System State ---"
if gst-inspect-1.0 mppvideodec > /dev/null 2>&1; then
    echo "SUCCESS: Rockchip MPP Hardware Decoder found."
else
    echo "WARNING: Rockchip MPP Hardware Decoder NOT found in default path."
    echo "Ensure vendor GStreamer is installed and GST_PLUGIN_PATH is correct."
fi

echo "--- [2/5] Setting up ROS 2 Foxy Repository ---"
sudo apt-get update && sudo apt-get install -y curl gnupg2 lsb-release
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt-get update

echo "--- [3/5] Installing Minimal ROS 2 Core ---"
# We use --no-install-recommends to avoid pulling in standard GStreamer/OpenCV packages
# that might conflict with vendor-optimized versions.
sudo apt-get install -y --no-install-recommends \
    ros-foxy-ros-base \
    ros-dev-tools \
    python3-colcon-common-extensions

echo "--- [4/5] Installing Python Bridge Dependencies ---"
# python3-gi: For GStreamer Python bindings (pygobject)
# gir1.2-gstreamer-1.0: For GObject introspection of GStreamer
# python3-numpy: For high-performance image reconstruction
sudo apt-get install -y \
    python3-gi \
    gir1.2-gstreamer-1.0 \
    python3-numpy

echo "--- [5/5] Building Workspace ---"
# Note: We avoid installing ros-foxy-cv-bridge to prevent OpenCV 4.2 conflict.
# The bridge node should use NumPy for image conversion.
cd ~/ros2_ws_receiver
source /opt/ros/foxy/setup.bash
colcon build --packages-select edge_oakd_camera_node

echo "--- Setup Complete ---"
echo "To ensure hardware acceleration is used, verify your GST_PLUGIN_PATH:"
echo "export GST_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/gstreamer-1.0:\$GST_PLUGIN_PATH"

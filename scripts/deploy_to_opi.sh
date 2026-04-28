#!/bin/bash
set -e

# --- CONFIGURATION ---
# Replace with your Orange Pi's Tailscale IP and username
TARGET_IP="100.88.199.104"
TARGET_USER="kennethsross20"
TARGET_DIR="~/ros2_ws_receiver"

# Source directory (built on host)
INSTALL_DIR="$(pwd)/ros2_ws_receiver/install"
MODEL_FILE="$(pwd)/yolo11n_416_qat_int8_fp16out.rknn"

echo "--- Deploying to Orange Pi ($TARGET_IP) ---"

# Create target directory
ssh $TARGET_USER@$TARGET_IP "mkdir -p $TARGET_DIR"

# Sync the install folder
# Note: --delete will remove files on target that don't exist on host
rsync -avz --progress $INSTALL_DIR $TARGET_USER@$TARGET_IP:$TARGET_DIR/

# Sync the model file
rsync -avz --progress $MODEL_FILE $TARGET_USER@$TARGET_IP:$TARGET_DIR/

# Sync the RKNN library
rsync -avz --progress $(pwd)/external/rknpu2/librknnrt.so $TARGET_USER@$TARGET_IP:/usr/lib/ || \
echo "Warning: Could not sync to /usr/lib directly. Trying $TARGET_DIR/lib" && \
ssh $TARGET_USER@$TARGET_IP "mkdir -p $TARGET_DIR/lib" && \
rsync -avz --progress $(pwd)/external/rknpu2/librknnrt.so $TARGET_USER@$TARGET_IP:$TARGET_DIR/lib/

echo "--- Deployment Complete ---"
echo "To run on OPi:"
echo "ssh $TARGET_USER@$TARGET_IP"
echo "source $TARGET_DIR/install/setup.bash"
echo "# Start the RTAB-Map SLAM System"
echo "ros2 launch rtabmap_bridge rtabmap_slam.launch.py"

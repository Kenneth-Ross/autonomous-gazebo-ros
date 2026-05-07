#!/bin/bash
set -e

# --- CONFIGURATION ---
# Use the Ethernet (eth0) IP of your Orange Pi (Direct Hardware Connection)
# Example: 10.42.0.1 or 192.168.1.x
TARGET_IP="${TARGET_IP:-10.42.0.1}"
TARGET_USER="kennethsross20"
TARGET_DIR="~/ros2_ws_receiver"

# Source directory (src folder for native build)
SOURCE_DIR="$(pwd)/ros2_ws_receiver/src"
SCRIPTS_DIR="$(pwd)/scripts"
MODEL_FILE="$(pwd)/yolo11n_416_qat_int8_fp16out.rknn"

echo "--- Deploying SOURCE and SCRIPTS to Orange Pi ($TARGET_IP) ---"

# Create target directory
ssh $TARGET_USER@$TARGET_IP "mkdir -p $TARGET_DIR/src"

# Sync the src folder
rsync -avz --progress $SOURCE_DIR $TARGET_USER@$TARGET_IP:$TARGET_DIR/

# Sync the setup scripts
rsync -avz --progress $SCRIPTS_DIR/setup_orangepi_foxy.sh $TARGET_USER@$TARGET_IP:$TARGET_DIR/

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

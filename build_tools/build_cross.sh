#!/bin/bash
set -e

# Configuration
IMAGE_NAME="ros2-foxy-arm64-native-builder"
WORKSPACE_DIR="$(pwd)/ros2_ws_receiver"

# Ensure QEMU is registered for ARM64 (required once on host)
# sudo apt-get install -y qemu-user-static
# sudo docker run --rm --privileged multiarch/qemu-user-static --reset -p yes

# Build the Docker image for ARM64 platform
if [[ "$(sudo docker images -q $IMAGE_NAME 2> /dev/null)" == "" ]]; then
    echo "--- Building Pure ARM64 Build Image ---"
    # Use project root (.) as context, but point to the Dockerfile in build_tools
    sudo docker build --platform linux/arm64 -t $IMAGE_NAME -f build_tools/cross_compile/Dockerfile .
fi

echo "--- Starting Native ARM64 Build inside Container ---"

# Run the build inside the ARM64 container
# We don't need the toolchain file anymore because the container is already ARM64!
sudo docker run --rm --platform linux/arm64 \
    -v $(pwd):/workspace \
    $IMAGE_NAME \
    /bin/bash -c "source /opt/ros/foxy/setup.bash && \
                  cd /workspace/ros2_ws_receiver && \
                  colcon build \
                  --merge-install \
                  --cmake-args \
                  -DAMENT_CMAKE_SYMLINK_INSTALL=OFF"

echo "--- Build Complete ---"

#!/bin/bash
set -e

# Configuration
BUILDER_IMAGE="ros2-foxy-hybrid-builder"
SYSROOT_IMAGE="ros:foxy"
SYSROOT_DIR="$(pwd)/.hybrid_sysroot"
WORKSPACE_DIR="$(pwd)/ros2_ws_receiver"

echo "--- Phase 1: Environment & Sysroot Setup ---"

# 1. Build the x86 Hybrid Builder Image
if [[ "$(sudo docker images -q $BUILDER_IMAGE 2> /dev/null)" == "" ]]; then
    echo "Creating x86 Hybrid Builder image..."
    sudo docker build -t $BUILDER_IMAGE -f build_tools/cross_compile/Dockerfile.hybrid .
fi

# 2. Extract Sysroot from ARM64 image if it doesn't exist
if [ ! -d "$SYSROOT_DIR" ]; then
    echo "Extracting ARM64 Sysroot from $SYSROOT_IMAGE (this may take a while)..."
    mkdir -p "$SYSROOT_DIR"
    TEMP_ID=$(sudo docker create --platform linux/arm64 $SYSROOT_IMAGE)
    sudo docker export $TEMP_ID | tar -C "$SYSROOT_DIR" -xf -
    sudo docker rm $TEMP_ID
fi

# Always fix symlinks to ensure they are relative to current absolute path
echo "Fixing absolute symlinks in sysroot..."
python3 build_tools/cross_compile/symlink_fix.py "$SYSROOT_DIR"

echo "--- Phase 2: Patching Source Code (via sed) ---"
if [ -d "external/ORB_SLAM3" ]; then
    echo "Patching ORB_SLAM3 architecture and headless flags..."
    cd external/ORB_SLAM3
    find . -name "CMakeLists.txt" -exec sed -i 's/-march=native//g' {} +
    sed -i 's/find_package(OpenCV 4.4)/find_package(OpenCV REQUIRED)/g' CMakeLists.txt
    sed -i '/if(NOT OpenCV_FOUND)/,+2d' CMakeLists.txt
    sed -i 's/find_package(Pangolin REQUIRED)/#find_package(Pangolin REQUIRED)/g' CMakeLists.txt
    sed -i 's/${Pangolin_LIBRARIES}//g' CMakeLists.txt
    sed -i 's/src\/Viewer.cc//g' CMakeLists.txt
    sed -i 's/src\/MapDrawer.cc//g' CMakeLists.txt
    sed -i 's/src\/FrameDrawer.cc//g' CMakeLists.txt
    sed -i 's|mpFrameDrawer = new FrameDrawer|mpFrameDrawer = nullptr; //new FrameDrawer|' src/System.cc
    sed -i 's|mpMapDrawer = new MapDrawer|mpMapDrawer = nullptr; //new MapDrawer|' src/System.cc
    sed -i 's|mpViewer = new Viewer|mpViewer = nullptr; //new Viewer|' src/System.cc
    sed -i 's|mptViewer = new thread|//mptViewer = new thread|' src/System.cc
    sed -i 's|mpFrameDrawer->Update|//mpFrameDrawer->Update|' src/Tracking.cc
    cd ../..
fi

echo "--- Phase 3: Building Dependencies (ORB-SLAM3) ---"

# Common CMake Arguments
CMAKE_ARGS="-DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_TOOLCHAIN_FILE=/workspace/build_tools/cross_compile/aarch64_toolchain.cmake \
    -DCMAKE_PREFIX_PATH=/opt/arm64_sysroot/usr:/opt/arm64_sysroot/usr/lib/aarch64-linux-gnu:/opt/arm64_sysroot/opt/ros/foxy \
    -DOpenCV_DIR=/opt/arm64_sysroot/usr/lib/aarch64-linux-gnu/cmake/opencv4 \
    -DEigen3_DIR=/opt/arm64_sysroot/usr/lib/cmake/eigen3"

sudo docker run --rm \
    -v $(pwd):/workspace \
    -v "$SYSROOT_DIR":/opt/arm64_sysroot:ro \
    $BUILDER_IMAGE \
    /bin/bash -c "
        cd /workspace/external/ORB_SLAM3
        if [ ! -f Vocabulary/ORBvoc.txt ]; then 
            cd Vocabulary && tar -xf ORBvoc.txt.tar.gz && cd ..
        fi
        
        echo 'Building DBoW2...'
        mkdir -p Thirdparty/DBoW2/build && cd Thirdparty/DBoW2/build && cmake .. $CMAKE_ARGS && make -j\$(nproc)
        
        echo 'Building g2o...'
        cd /workspace/external/ORB_SLAM3 && mkdir -p Thirdparty/g2o/build && cd Thirdparty/g2o/build && cmake .. $CMAKE_ARGS && make -j\$(nproc)
        
        echo 'Building Sophus...'
        cd /workspace/external/ORB_SLAM3 && mkdir -p Thirdparty/Sophus/build && cd Thirdparty/Sophus/build && cmake .. $CMAKE_ARGS && make -j\$(nproc)
        
        echo 'Building ORB_SLAM3...'
        cd /workspace/external/ORB_SLAM3 && mkdir -p build && cd build && cmake .. $CMAKE_ARGS && make -j\$(nproc) ORB_SLAM3
    "

echo "--- Phase 4: Building ROS 2 Workspace ---"

sudo docker run --rm \
    -v $(pwd):/workspace \
    -v "$SYSROOT_DIR":/opt/arm64_sysroot:ro \
    $BUILDER_IMAGE \
    /bin/bash -c "
        export PKG_CONFIG_SYSROOT_DIR=/opt/arm64_sysroot
        export PKG_CONFIG_LIBDIR=/opt/arm64_sysroot/usr/lib/aarch64-linux-gnu/pkgconfig:/opt/arm64_sysroot/usr/share/pkgconfig:/opt/arm64_sysroot/opt/ros/foxy/lib/pkgconfig
        export ORB_SLAM3_ROOT=/workspace/external/ORB_SLAM3
        export PYTHONPATH=/opt/arm64_sysroot/opt/ros/foxy/lib/python3.8/site-packages:\$PYTHONPATH
        export AMENT_PREFIX_PATH=/opt/arm64_sysroot/opt/ros/foxy
        export OpenCV_DIR=/opt/arm64_sysroot/usr/lib/aarch64-linux-gnu/cmake/opencv4
        
        cd /workspace/ros2_ws_receiver
        colcon build \
            --merge-install \
            --cmake-args \
            -DCMAKE_TOOLCHAIN_FILE=/workspace/build_tools/cross_compile/aarch64_toolchain.cmake \
            -DAMENT_CMAKE_SYMLINK_INSTALL=OFF \
            -DORB_SLAM3_ROOT=\$ORB_SLAM3_ROOT \
            -DOpenCV_DIR=\$OpenCV_DIR
    "

echo "--- Phase 5: Verification ---"
LIB_SLAM="external/ORB_SLAM3/lib/libORB_SLAM3.so"
NODE_BIN="ros2_ws_receiver/install/lib/edge_device_slam_node/edge_device_slam_node"

if [ -f "$LIB_SLAM" ]; then file "$LIB_SLAM"; fi
if [ -f "$NODE_BIN" ]; then file "$NODE_BIN"; fi

echo "--- Build Complete ---"

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

# The sysroot is mounted at this path inside the builder container
set(CMAKE_SYSROOT /opt/arm64_sysroot)

# Specify the cross compiler (available in the hybrid builder image)
set(CMAKE_C_COMPILER /usr/bin/aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER /usr/bin/aarch64-linux-gnu-g++)

# Force search paths to ARM64 locations inside the sysroot
set(CMAKE_FIND_ROOT_PATH 
    /opt/arm64_sysroot/usr/lib/aarch64-linux-gnu
    /opt/arm64_sysroot/opt/ros/foxy
)

# Search for programs on the host, but libs/headers ONLY in the sysroot
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

# ROS 2 Specific paths inside the sysroot
set(CMAKE_PREFIX_PATH "/opt/arm64_sysroot/opt/ros/foxy")

# RK3588 Optimizations (Cortex-A76/A55 with dotprod/fp16)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -march=armv8.2-a+fp16+dotprod -mtune=cortex-a76 -O3" CACHE STRING "" FORCE)
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -march=armv8.2-a+fp16+dotprod -mtune=cortex-a76 -O3" CACHE STRING "" FORCE)

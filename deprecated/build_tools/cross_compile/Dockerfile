# Use the official ROS 2 Foxy ARM64 image directly
FROM --platform=linux/arm64 ros:foxy-ros-base

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install RTAB-Map and Bridge dependencies for ARM64
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    pkg-config \
    python3-colcon-common-extensions \
    libopencv-dev \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-good1.0-dev \
    ros-foxy-cv-bridge \
    ros-foxy-tf2-ros \
    ros-foxy-sensor-msgs \
    ros-foxy-nav-msgs \
    ros-foxy-robot-localization \
    ros-foxy-rtabmap-ros \
    && rm -rf /var/lib/apt/lists/*

ENV ROS_DISTRO=foxy
WORKDIR /workspace

# By default, we just want to source ROS and be ready to build
CMD ["/bin/bash"]

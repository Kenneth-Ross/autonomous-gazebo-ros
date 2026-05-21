cmake_minimum_required(VERSION 3.8)
project(edge_device_slam_node)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(OpenCV REQUIRED)

# GStreamer
find_package(PkgConfig REQUIRED)
pkg_check_modules(GSTREAMER REQUIRED gstreamer-1.0 gstreamer-app-1.0)

# RKNN
set(RKNN_INCLUDE_DIR ${CMAKE_SOURCE_DIR}/../../../external/rknpu2/include)
set(RKNN_LIB ${CMAKE_SOURCE_DIR}/../../lib/librknnrt.so)

# ORB-SLAM3
set(ORB_SLAM3_ROOT $ENV{ORB_SLAM3_ROOT})
if(NOT ORB_SLAM3_ROOT)
    set(ORB_SLAM3_ROOT "/opt/ORB_SLAM3")
endif()
message(STATUS "ORB_SLAM3_ROOT: ${ORB_SLAM3_ROOT}")
include_directories(
  ${ORB_SLAM3_ROOT}
  ${ORB_SLAM3_ROOT}/include
  ${ORB_SLAM3_ROOT}/include/CameraModels
  ${ORB_SLAM3_ROOT}/Thirdparty/Sophus
)

add_executable(edge_device_slam_node src/edge_device_slam_node.cpp)
target_include_directories(edge_device_slam_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${GSTREAMER_INCLUDE_DIRS}
  ${RKNN_INCLUDE_DIR}
)

target_link_libraries(edge_device_slam_node
  ${GSTREAMER_LIBRARIES}
  ${RKNN_LIB}
  ${ORB_SLAM3_ROOT}/lib/libORB_SLAM3.so
)

ament_target_dependencies(edge_device_slam_node
  rclcpp
  sensor_msgs
  nav_msgs
  visualization_msgs
  cv_bridge
  geometry_msgs
  tf2
  tf2_ros
  OpenCV
)

install(TARGETS edge_device_slam_node
  DESTINATION lib/${PROJECT_NAME})

ament_package()

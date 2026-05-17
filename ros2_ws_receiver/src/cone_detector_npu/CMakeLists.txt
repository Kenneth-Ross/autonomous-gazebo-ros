cmake_minimum_required(VERSION 3.8)
project(cone_detector_npu)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(vision_msgs REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(rclcpp REQUIRED)
find_package(OpenCV REQUIRED)

# RKNN SDK Discovery
find_path(RKNN_INCLUDE_DIR NAMES rknn_api.h
  HINTS "${RKNN_SDK_PATH}" "$ENV{RKNN_SDK_PATH}"
  PATHS 
    "${PROJECT_SOURCE_DIR}/../../../../external/rknpu2"
    "${PROJECT_SOURCE_DIR}/../../../external/rknpu2"
    "${PROJECT_SOURCE_DIR}/../../external/rknpu2"
  PATH_SUFFIXES include
)

find_library(RKNN_LIBRARY NAMES rknnrt
  HINTS "${RKNN_SDK_PATH}" "$ENV{RKNN_SDK_PATH}"
  PATHS 
    "${PROJECT_SOURCE_DIR}/../../../../external/rknpu2"
    "${PROJECT_SOURCE_DIR}/../../../external/rknpu2"
    "${PROJECT_SOURCE_DIR}/../../external/rknpu2"
)

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(RKNN REQUIRED_VARS RKNN_LIBRARY RKNN_INCLUDE_DIR)

if(RKNN_FOUND AND NOT TARGET RKNN::RKNN)
  add_library(RKNN::RKNN UNKNOWN IMPORTED)
  set_target_properties(RKNN::RKNN PROPERTIES
    INTERFACE_INCLUDE_DIRECTORIES "${RKNN_INCLUDE_DIR}"
    IMPORTED_LOCATION "${RKNN_LIBRARY}")
endif()

add_executable(cone_detector_npu src/cone_detector_npu.cpp)
target_include_directories(cone_detector_npu PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include/${PROJECT_NAME}>
  ${OpenCV_INCLUDE_DIRS}
  ${cv_bridge_INCLUDE_DIRS}
)

target_compile_features(cone_detector_npu PUBLIC cxx_std_17)

ament_target_dependencies(
  cone_detector_npu
  "sensor_msgs"
  "vision_msgs"
  "cv_bridge"
  "rclcpp"
)

target_link_libraries(cone_detector_npu
  ${OpenCV_LIBS}
  RKNN::RKNN
)

install(TARGETS cone_detector_npu
  DESTINATION lib/${PROJECT_NAME})

ament_package()

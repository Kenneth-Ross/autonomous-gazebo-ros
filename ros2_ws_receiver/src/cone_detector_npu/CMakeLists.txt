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

# RKNN setup
set(RKNN_BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../../external/rknpu2")
find_library(RKNN_LIB rknnrt PATHS "${RKNN_BASE_DIR}" NO_DEFAULT_PATH)
set(RKNN_INCLUDE_DIR "${RKNN_BASE_DIR}/include")

add_executable(cone_detector_npu src/cone_detector_npu.cpp)
target_include_directories(cone_detector_npu PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include/${PROJECT_NAME}>
  ${OpenCV_INCLUDE_DIRS}
  ${RKNN_INCLUDE_DIR}
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
  ${RKNN_LIB}
)

install(TARGETS cone_detector_npu
  DESTINATION lib/${PROJECT_NAME})

ament_package()

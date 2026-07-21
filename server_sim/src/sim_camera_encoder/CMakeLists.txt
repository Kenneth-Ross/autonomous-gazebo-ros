cmake_minimum_required(VERSION 3.8)
project(sim_camera_encoder)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(image_transport REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(OpenCV REQUIRED)
set(ENV{PKG_CONFIG_PATH} "$ENV{PKG_CONFIG_PATH}:/usr/lib/x86_64-linux-gnu/pkgconfig:/opt/ros/jazzy/opt/gz_transport_vendor/lib/pkgconfig")

find_package(gz-transport13 REQUIRED)
find_package(gz-msgs10 REQUIRED)

add_executable(sim_camera_encoder_node src/sim_camera_encoder_node.cpp)
target_include_directories(sim_camera_encoder_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

target_link_libraries(sim_camera_encoder_node
  gz-transport13::gz-transport13
  gz-msgs10::gz-msgs10
  ${OpenCV_LIBRARIES}
)

ament_target_dependencies(sim_camera_encoder_node
  rclcpp
  sensor_msgs
  image_transport
  cv_bridge
)

install(TARGETS sim_camera_encoder_node
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()

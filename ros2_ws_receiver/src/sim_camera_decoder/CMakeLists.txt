cmake_minimum_required(VERSION 3.8)
project(sim_camera_decoder)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_components REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(image_transport REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(OpenCV REQUIRED)

add_library(sim_camera_decoder_component SHARED src/sim_camera_decoder_node.cpp)
target_include_directories(sim_camera_decoder_component PUBLIC ${OpenCV_INCLUDE_DIRS})
ament_target_dependencies(sim_camera_decoder_component rclcpp rclcpp_components sensor_msgs image_transport cv_bridge)
target_link_libraries(sim_camera_decoder_component ${OpenCV_LIBRARIES})
rclcpp_components_register_node(sim_camera_decoder_component PLUGIN "SimCameraDecoder" EXECUTABLE sim_camera_decoder_node)

install(TARGETS
  sim_camera_decoder_component
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()

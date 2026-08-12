cmake_minimum_required(VERSION 3.8)
project(autonomous_racing_core)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(autonomous_racing_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)

add_library(autonomous_racing_core SHARED
  src/midpoint_planner.cpp
  src/pure_pursuit_controller.cpp
  src/safety_supervisor.cpp
)
target_include_directories(autonomous_racing_core PUBLIC include)
ament_target_dependencies(autonomous_racing_core
  autonomous_racing_msgs geometry_msgs nav_msgs rclcpp std_msgs)

add_executable(cone_map_adapter_node src/cone_map_adapter_node.cpp)
target_link_libraries(cone_map_adapter_node autonomous_racing_core)
ament_target_dependencies(cone_map_adapter_node
  autonomous_racing_msgs rclcpp visualization_msgs)

add_executable(racing_planner_node src/racing_planner_node.cpp)
target_link_libraries(racing_planner_node autonomous_racing_core)
ament_target_dependencies(racing_planner_node
  autonomous_racing_msgs rclcpp)

add_executable(racing_controller_node src/racing_controller_node.cpp)
target_link_libraries(racing_controller_node autonomous_racing_core)
ament_target_dependencies(racing_controller_node
  autonomous_racing_msgs geometry_msgs nav_msgs rclcpp)

add_executable(racing_supervisor_node src/racing_supervisor_node.cpp)
target_link_libraries(racing_supervisor_node autonomous_racing_core)
ament_target_dependencies(racing_supervisor_node
  autonomous_racing_msgs geometry_msgs rclcpp)

install(TARGETS autonomous_racing_core cone_map_adapter_node racing_planner_node racing_controller_node
  racing_supervisor_node
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY include/ DESTINATION include)
install(FILES resource/autonomous_racing_core DESTINATION share/ament_index/resource_index/packages)
install(FILES package.xml DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_racing_core test/test_racing_core.cpp)
  target_link_libraries(test_racing_core autonomous_racing_core)
  target_include_directories(test_racing_core PRIVATE include)
  ament_target_dependencies(test_racing_core
    autonomous_racing_msgs geometry_msgs nav_msgs rclcpp std_msgs)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_export_include_directories(include)
ament_export_dependencies(autonomous_racing_msgs geometry_msgs nav_msgs rclcpp std_msgs visualization_msgs)
ament_package()

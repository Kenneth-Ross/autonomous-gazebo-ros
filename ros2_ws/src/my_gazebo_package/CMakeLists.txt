cmake_minimum_required(VERSION 3.8)
project(my_gazebo_package)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(Python3 3.12 EXACT REQUIRED COMPONENTS Interpreter)
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(ros_gz_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)

# Define interfaces
rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/ChangeTrack.srv"
  DEPENDENCIES geometry_msgs
)

# Install Python modules
# This installs the directory 'my_gazebo_package_py'
ament_python_install_package(my_gazebo_package_py)

# Install Python nodes
install(PROGRAMS
  my_gazebo_package_py/nodes/track_generator_node.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME track_generator_node
)

# Install data files
install(DIRECTORY
  launch
  models
  worlds
  resource
  DESTINATION share/${PROJECT_NAME}
)

# Install ament index
ament_index_register_resource("package")

ament_package()

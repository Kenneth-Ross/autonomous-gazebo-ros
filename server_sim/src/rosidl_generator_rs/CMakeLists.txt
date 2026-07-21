cmake_minimum_required(VERSION 3.8)
project(rosidl_generator_rs)

find_package(ament_cmake REQUIRED)

# This package intentionally does NOTHING.
# By existing in the workspace with version 99.99.99, 
# it shadows the system /opt/ros version and prevents it from running.

ament_package()

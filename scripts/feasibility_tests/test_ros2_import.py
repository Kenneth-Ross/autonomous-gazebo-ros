#!/usr/bin/env python3
import sys
import os

print(f"Python Version: {sys.version}")

def test_import(module_name):
    try:
        __import__(module_name)
        print(f"SUCCESS: {module_name} imported successfully.")
        return True
    except ImportError as e:
        print(f"FAILURE: Could not import {module_name}. Error: {e}")
        return False

if __name__ == '__main__':
    print("--- ROS 2 Jazzy Import Test ---")
    
    # Check if ROS 2 environment is sourced
    if 'ROS_DISTRO' not in os.environ:
        print("WARNING: ROS_DISTRO not found. Did you source /opt/ros/jazzy/setup.bash?")
    else:
        print(f"Detected ROS 2 Distro: {os.environ['ROS_DISTRO']}")

    results = []
    results.append(test_import("rclpy"))
    results.append(test_import("sensor_msgs"))
    results.append(test_import("vision_msgs"))
    results.append(test_import("cv_bridge"))
    
    # Try importing a specific message type
    try:
        from vision_msgs.msg import Detection2DArray
        print("SUCCESS: vision_msgs.msg.Detection2DArray imported.")
    except Exception as e:
        print(f"FAILURE: Could not import Detection2DArray. Error: {e}")

    if all(results):
        print("\nCONCLUSION: This Python environment IS COMPATIBLE with ROS 2 Jazzy.")
    else:
        print("\nCONCLUSION: This Python environment IS NOT fully compatible with ROS 2 Jazzy.")

# Semantic Mapping Feasibility Tests

This directory contains scripts to determine if we can use the RKNN Python API (`rknn-toolkit-lite2`) directly with ROS 2 Jazzy on Ubuntu 24.04.

## Background
*   **ROS 2 Jazzy:** Requires Python 3.12.
*   **RKNN-Toolkit-Lite2:** Traditionally supports Python 3.7, 3.8, 3.9, and 3.10.
*   **Problem:** If we run inference in a Python 3.8 environment, we might not be able to import `rclpy` (ROS 2) because it was built for Python 3.12.

## Test Procedures

### 1. RKNN Inference Test
Verify that the NPU driver and `rknn-toolkit-lite2` are working in your current environment.
```bash
python3 scripts/feasibility_tests/test_rknn_inference.py
```

### 2. ROS 2 Import Test
Verify that ROS 2 Jazzy packages can be imported in your current environment.
```bash
# First, source ROS 2
source /opt/ros/jazzy/setup.bash
# Then run the test
python3 scripts/feasibility_tests/test_ros2_import.py
```

## How to Interpret Results

| Test 1 (RKNN) | Test 2 (ROS 2) | Recommendation |
| :--- | :--- | :--- |
| **SUCCESS** | **SUCCESS** | **Path A:** Develop the inference node in Python. This is the easiest path. |
| **SUCCESS** | **FAILURE** | **Path B:** Develop the inference node in **C++**. This avoids the Python version mismatch entirely and provides lower latency. |
| **FAILURE** | **SUCCESS** | Check `rknn-toolkit-lite2` installation or NPU driver status. |
| **FAILURE** | **FAILURE** | Serious environment issue. Verify OS and ROS 2 installation. |

# Semantic Sensor & NPU Integration Plan

## Objective
Implement a real-time semantic sensing layer on the Orange Pi 5 using the RK3588 NPU for YOLOv11 cone detection. This will provide RTAB-Map with persistent 3D landmarks for better loop closure and high-speed autonomous racing.

## Current State
- **Video Pipeline**: 16-bit Depth + RGB Super-Frame is decoded and unpacked on the Orange Pi.
- **SLAM**: RTAB-Map is running with fused sensor data (EKF).
- **Goal**: Transition from raw point clouds to "Intelligent Landmarks."

## Proposed Architecture

1.  **NPU Detection Node (`cone_detector_npu`)**:
    - **Language**: C++ (Leveraging RKNN API for performance).
    - **Input**: `/camera/rgb/image_raw`.
    - **Logic**: 
        - Convert ROS Image to OpenCV.
        - Pre-process (resize 416x416, RGB conversion).
        - Run RKNN Inference (YOLOv11n).
        - Post-process (NMS, box decoding).
    - **Output**: `vision_msgs/Detection2DArray` containing cone bounding boxes.

2.  **Landmark Projection Node (`cone_landmark_processor`)**:
    - **Language**: Python.
    - **Input**: `vision_msgs/Detection2DArray` + `/camera/depth/image_raw`.
    - **Logic**:
        - Sync detection with high-fidelity depth frame.
        - Calculate median depth of the cone bounding box.
        - Project (u, v, z) -> (x, y, z) in `camera_link_optical` frame.
    - **Output**: `visualization_msgs/MarkerArray` (for Foxglove) and `rtabmap/user_data` (for SLAM).

## Implementation Steps

### Step 1: RKNN Detector Implementation
- Extract RKNN initialization and inference logic from boilerplate.
- Create a dedicated ROS 2 package for NPU detection.
- Optimize the pre-processing loop to ensure <15ms latency.

### Step 2: Model Deployment
- Deploy the quantized YOLOv11n `.rknn` model to the Orange Pi.
- Verify NPU utilization.

### Step 3: 3D Projection Math
- Implement the geometry math to convert pixel bounding boxes into metric landmarks.
- Utilize the static camera intrinsics to ensure sub-centimeter accuracy.

### Step 4: RTAB-Map Landmark Injection
- Configure RTAB-Map to process `user_data` as persistent landmarks.
- Enable loop closure based on landmark geometry (Graph Optimization).

## Verification & Testing
1.  **Inference FPS**: Maintain >15 FPS on the RK3588 NPU.
2.  **Distance Accuracy**: Compare detected cone distance against Gazebo ground truth.
3.  **Foxglove View**: Visualize persistent cone markers in the 3D SLAM map.

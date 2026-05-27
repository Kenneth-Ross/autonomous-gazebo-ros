# [FINISHED] Semantic Sensor & NPU Integration Plan

## Objective
Implement a real-time semantic sensing layer on the Orange Pi 5 using the RK3588 NPU for YOLOv11 cone detection. This provides RTAB-Map with persistent 3D landmarks for better loop closure and high-speed autonomous racing.

## Status: [FINISHED]
All phases of the integration are complete and verified. The system is able to stream super-frames from simulation, decode and unpack them, detect cones on the NPU using YOLOv11 at high speed, project the detections into 3D, and publish them as native RTAB-Map `LandmarkDetections` to achieve robust loop closures.

## Architecture

1.  **NPU Detection Node (`cone_detector_npu`)**:
    - **Language**: Python (leveraging `rknnlite` on Python 3.12).
    - **Input**: `/camera/rgb/image_raw` (reconstructed BGR image).
    - **Logic**:
        - Convert ROS Image to OpenCV.
        - Pre-process (resize to 416x416, BGR to RGB).
        - Run RKNN Inference using QAT INT8 YOLOv11n model on RK3588 NPU.
        - Post-process (parse (5, 3549) output tensor, confidence thresholding, NMS).
    - **Output**: `vision_msgs/Detection2DArray` containing synchronized bounding boxes.

2.  **Landmark Projection Node (`cone_landmark_processor`)**:
    - **Language**: Python.
    - **Input**: `vision_msgs/Detection2DArray` + `/camera/depth/image_raw`.
    - **Logic**:
        - Synchronize 2D detections and depth images via `ApproximateTimeSynchronizer` (100ms slop).
        - Filter depth noise using a 5x5 median window around the bounding box center.
        - Project pixel coordinates (u, v, z) to 3D camera coordinates (x, y, z) using intrinsics.
        - Perform data association by tracking landmarks in the `map` or `odom` frame using Euclidean distance.
        - Publish persistent landmarks with relative poses and covariances.
    - **Output**: `rtabmap_msgs/LandmarkDetections` published to `/rtabmap/landmarks`.

## Implementation Steps

### Step 1: RKNN Detector Implementation - [FINISHED]
- Implemented `cone_detector_npu` in Python.
- Preprocessing and NMS optimized for latency.

### Step 2: Model Deployment - [FINISHED]
- Quantized YOLOv11n `.rknn` model deployed and tested with hardware acceleration on RK3588.

### Step 3: 3D Projection Math - [FINISHED]
- Developed 5x5 median filter logic to handle depth holes and noise.
- Calculated metric coords and transformed to map/odom frame using TF2 listener.

### Step 4: RTAB-Map Landmark Injection - [FINISHED]
- Remapped landmark topic to `/rtabmap/landmarks` and enabled `subscribe_landmark_detections`.
- Landmark-based loop closure is active and tested.

## Verification & Testing
1.  **Inference FPS**: Maintained stable >20 FPS on the RK3588 NPU.
2.  **Distance Accuracy**: Sub-centimeter projection accuracy verified by comparison against ground truth.
3.  **Foxglove View**: 3D Landmark visualization configured and verified in Foxglove.

# Plan: Gazebo OAK-D Camera Streaming to Edge Device for Computer Vision

## Objective:
Establish an efficient camera streaming pipeline for the **three distinct camera streams (RGB, Left, Right)** from a Gazebo OAK-D camera simulation over an Ethernet port to an edge device. This setup will enable subsequent computer vision processing within a ROS2 environment, prioritizing low latency, efficient bandwidth usage, and minimal CPU overhead on the edge device.

## Approach:
A hybrid approach will be used: Gazebo will provide simulated camera data for RGB, Left, and Right cameras via separate ROS2 topics. Dedicated ROS2 nodes will then bridge these data streams to GStreamer for high-performance, codec-driven network streaming and decoding, leveraging hardware acceleration on the edge device. Finally, ROS2 will integrate the decoded video frames for computer vision processing and overall system management.

## High-Level Steps:

1.  **Configure Gazebo OAK-D Camera Output:**
    *   Ensure the Gazebo OAK-D camera (`oakd_camera.urdf.xacro`) is correctly loaded and publishing data for all three sensors.
    *   Verify that Gazebo publishes `sensor_msgs/msg/Image` messages on the following ROS2 topics:
        *   `/oakd/rgb/image_raw` (Format: R8G8B8)
        *   `/oakd/left/image_raw` (Format: L8)
        *   `/oakd/right/image_raw` (Format: L8)
    *   Confirm corresponding camera info topics are also published.

2.  **ROS2-GStreamer Bridge (Sender Side - One per stream or multiplexed):**
    *   Develop a new ROS2 package (e.g., `gazebo_oakd_stream_sender`).
    *   Implement **three separate ROS2 nodes, or a single node managing three independent pipelines**, one for each camera stream (RGB, Left, Right). Each node/pipeline will:
        *   Subscribe to its respective Gazebo camera `sensor_msgs/msg/Image` topic (`/oakd/rgb/image_raw`, `/oakd/left/image_raw`, `/oakd/right/image_raw`).
        *   Convert the ROS2 image messages into raw video frames suitable for GStreamer (e.g., using `cv_bridge`).
        *   Feed these raw frames into a dedicated GStreamer pipeline for encoding and network streaming.
        *   Each GStreamer pipeline should:
            *   Encode the video using an appropriate codec (H.264/H.265) suitable for the image format, with hardware acceleration if available on the sender system (or software encoding).
            *   Stream the encoded video over the Ethernet port using the selected protocol (e.g., RTSP, RTP/UDP) to distinct ports or RTSP paths.
    *   Test each sender pipeline individually to ensure stable streaming from Gazebo.

3.  **GStreamer Receiver Pipeline on Edge Device (One per stream):**
    *   Develop **three separate GStreamer pipelines** on the edge device, one for each incoming camera stream (RGB, Left, Right). Each pipeline will:
        *   Receive its respective network stream (e.g., `rtspsrc`, `udpsrc`) from the sender.
        *   Depayload the stream (e.g., `rtph264depay`).
        *   Decode the video (e.g., `avdec_h264`, `nvh264dec`, `omxh264dec`) using hardware acceleration if available on the edge device.
        *   Convert the decoded video to a raw image format suitable for computer vision (e.g., RGB for RGB stream, grayscale for mono streams) using `videoconvert`.
        *   Output the raw frames to a dedicated GStreamer `appsink` element.
    *   Test each receiver pipeline independently to verify successful reception and decoding of all three streams.

4.  **Create ROS2 Wrapper Node (Receiver Side - One per stream or unified):**
    *   Develop a new ROS2 package (e.g., `edge_oakd_camera_node`).
    *   Implement **three separate ROS2 nodes, or a single node managing three independent interfaces**, one for each camera stream. Each node/interface will:
        *   Initialize and manage its respective GStreamer receiver pipeline defined in Step 3.
        *   Continuously pull frames from its dedicated GStreamer `appsink`.
        *   Convert the raw image data from GStreamer into `sensor_msgs/msg/Image` messages.
        *   Publish these `sensor_msgs/msg/Image` messages on dedicated ROS2 topics (e.g., `/edge_oakd/rgb/image_raw`, `/edge_oakd/left/image_raw`, `/edge_oakd/right/image_raw`).
        *   Ensure proper synchronization (e.g., using `message_filters` if processing multiple streams together) and handling of metadata (frame ID, timestamp).

5.  **Develop/Integrate ROS2 Computer Vision Nodes:**
    *   Create or integrate existing ROS2 packages (e.g., using `vision_opencv` or custom nodes) that subscribe to the *relevant* `/edge_oakd/X/image_raw` topic(s).
    *   Implement the desired computer vision algorithms (e.g., object detection on RGB, stereo matching for depth estimation using Left/Right mono streams, tracking) within these nodes.
    *   Publish results (e.g., bounding boxes, depth maps, processed images) on their respective ROS2 topics.

6.  **System Testing and Optimization:**
    *   Deploy all components (Gazebo, ROS2-GStreamer bridge, GStreamer receivers, ROS2 wrappers, ROS2 CV nodes) on the target hardware/systems.
    *   Perform end-to-end testing to verify functionality of all three streams and their processing.
    *   Monitor system performance (CPU/GPU utilization, memory, network bandwidth, end-to-end latency, frame rate) for each stream and overall system using tools like `htop`, `nvtop`, `rqt_plot`, `ros2 topic bw`.
    *   Optimize GStreamer pipeline parameters, codec settings, ROS2 QoS profiles, and computer vision algorithm efficiency to meet performance requirements across all streams.

## Key Tools and Technologies:

*   **Gazebo:** For simulating OAK-D camera sensor data (RGB, Left, Right).
*   **ROS2:** For robotics framework integration, inter-node communication, and computer vision processing.
*   **GStreamer:** For multimedia pipeline construction, encoding, decoding, and network streaming of multiple streams.
*   **Python/C++:** For implementing the ROS2 nodes and computer vision algorithms.
*   **Hardware Acceleration:** Crucial for efficient encoding/decoding on both sender (if applicable) and receiver (edge device) systems, especially with multiple high-resolution streams.
*   **`cv_bridge`:** For converting between ROS2 `sensor_msgs/msg/Image` and OpenCV image formats.
*   **`message_filters` (ROS2):** Potentially useful for synchronizing multiple image streams on the receiver side for tasks like stereo vision.

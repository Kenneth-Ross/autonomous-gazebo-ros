# Plan for Implementing RTSP Streaming

This plan outlines the steps to implement RTSP streaming of a camera feed from a Gazebo simulation.

## 1. Create a new ROS2 node for RTSP streaming

A new Python-based ROS2 node will be created within the `my_gazebo_package`. This node will be responsible for the following:

- Subscribing to the `/oakd/rgb/image_raw` ROS2 topic to receive camera images.
- Using `cv_bridge` to convert the ROS `sensor_msgs/Image` messages to OpenCV images.
- Using GStreamer with Python bindings to create an RTSP server.
- Constructing a GStreamer pipeline to encode the OpenCV images into H.264 format and stream them over RTSP.

The new node will be a file named `rtsp_server_node.py` in a new `nodes` directory inside `my_gazebo_package/my_gazebo_package`.

## 2. Update package dependencies

The `package.xml` and `setup.py` files will be updated to include the necessary dependencies for the new RTSP streaming node.

### `package.xml`
The following dependencies will be added:
- `cv_bridge`: For converting between ROS image messages and OpenCV images.
- `python3-gst-1.0`: The GStreamer Python bindings.

### `setup.py`
A new entry point for the `rtsp_server_node` will be added to the `console_scripts` section.

## 3. Update the launch file

The `gazebo.launch.py` file will be updated to launch the new `rtsp_server_node` alongside the existing simulation components. A new `Node` action will be added to execute the `rtsp_server_node`.

## 4. Implementation Details

### `rtsp_server_node.py`

The node will be implemented as a class. The `__init__` method will initialize the ROS2 node, create the subscriber, and set up the GStreamer pipeline.

The subscriber callback will receive the `sensor_msgs/Image` message, convert it to an OpenCV image using `cv_bridge`, and push it to the GStreamer pipeline.

The GStreamer pipeline will be constructed using the following elements:
- `appsrc`: To feed the image data from the Python script into the pipeline.
- `videoconvert`: To convert the color format of the image.
- `x264enc`: To encode the video into H.264 format.
- `rtspclientsink`: To create the RTSP server and stream the data.

The RTSP server will be available at an address like `rtsp://<host_ip>:8554/stream`. The port and stream name will be configurable as ROS2 parameters.

This plan provides a complete solution for streaming the camera feed from the Gazebo simulation to a standard video consumer using RTSP.

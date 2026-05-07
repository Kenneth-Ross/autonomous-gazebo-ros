#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import numpy as np
import threading
from collections import deque

class RTABMapBridgeNode(Node):
    def __init__(self):
        super().__init__('rtabmap_bridge')
        
        self.declare_parameter('port', 5000)
        self.port = self.get_parameter('port').value
        
        self.lock = threading.Lock()
        
        # Buffers for CameraInfo synchronization
        self.rgb_info_buffer = deque(maxlen=30)
        self.depth_info_buffer = deque(maxlen=30)
        
        # Publishers
        self.rgb_pub = self.create_publisher(Image, '/camera/rgb/image_raw', 10)
        self.rgb_info_pub = self.create_publisher(CameraInfo, '/camera/rgb/camera_info', 10)
        self.depth_pub = self.create_publisher(Image, '/camera/depth/image_raw', 10)
        self.depth_info_pub = self.create_publisher(CameraInfo, '/camera/depth/camera_info', 10)
        
        # Subscribers for CameraInfo (from Gazebo)
        self.rgb_info_sub = self.create_subscription(CameraInfo, '/oakd/rgb/camera_info', self.rgb_info_callback, 10)
        self.depth_info_sub = self.create_subscription(CameraInfo, '/oakd/depth/camera_info', self.depth_info_callback, 10)
        
        Gst.init(None)
        
        # Single Pipeline: H.265 (Hardware Dec)
        self.pipeline = self.create_pipeline(self.port)
        
        self.get_logger().info(f"OAK-D Bridge (Sync Bit-Split): Receiving H.265 on port {self.port}")
        self.get_logger().info("Mode: OpenCV-Independent (NumPy Optimized)")
        
        self.pipeline.set_state(Gst.State.PLAYING)

    def rgb_info_callback(self, msg):
        with self.lock:
            self.rgb_info_buffer.append(msg)

    def depth_info_callback(self, msg):
        with self.lock:
            self.depth_info_buffer.append(msg)

    def find_nearest_info(self, buffer, target_stamp_ns):
        if not buffer:
            return None
        best_msg = None
        min_diff = float('inf')
        for msg in buffer:
            msg_ns = msg.header.stamp.sec * 1e9 + msg.header.stamp.nanosec
            diff = abs(msg_ns - target_stamp_ns)
            if diff < min_diff:
                min_diff = diff
                best_msg = msg
        if min_diff > 1e8: # 100ms
            return None
        return best_msg

    def create_pipeline(self, port):
        # Using mppvideodec for RK3588 hardware-accelerated H.265 decoding
        pipeline_str = (
            f"udpsrc port={port} ! "
            "application/x-rtp, encoding-name=H265, payload=96 ! "
            "rtph265depay ! h265parse ! mppvideodec ! videoconvert ! "
            "video/x-raw, format=BGR ! appsink name=sink emit-signals=True sync=False"
        )
        pipeline = Gst.parse_launch(pipeline_str)
        appsink = pipeline.get_by_name("sink")
        appsink.connect("new-sample", self.on_new_sample)
        return pipeline

    def on_new_sample(self, sink):
        arrival_time_ns = self.get_clock().now().nanoseconds
        sample = sink.emit("pull-sample")
        if not sample: return Gst.FlowReturn.ERROR
            
        buf = sample.get_buffer()
        caps = sample.get_caps()
        height = caps.get_structure(0).get_value("height")
        width = caps.get_structure(0).get_value("width") # Expecting 3840 (1280*3)
        
        res, map_info = buf.map(Gst.MapFlags.READ)
        if not res: return Gst.FlowReturn.ERROR
            
        # 1. Map to NumPy directly (Zero-Copy)
        raw_frame = np.frombuffer(map_info.data, dtype=np.uint8).reshape((height, width, 3))
        
        # 2. Slice the frame: [ RGB (0:1280) | MSB (1280:2560) | LSB (2560:3840) ]
        single_w = width // 3
        rgb_part = raw_frame[:, 0:single_w, :]
        msb_part = raw_frame[:, single_w:2*single_w, 0] # Use only one channel for grayscale depth bytes
        lsb_part = raw_frame[:, 2*single_w:3*single_w, 0]
        
        # 3. Reconstruct 16-bit Depth (Vectorized NumPy)
        depth_16bit = (msb_part.astype(np.uint16) << 8) | lsb_part.astype(np.uint16)
        
        buf.unmap(map_info)

        # 4. Sync with CameraInfo
        with self.lock:
            info = self.find_nearest_info(self.rgb_info_buffer, arrival_time_ns)
            depth_info = self.find_nearest_info(self.depth_info_buffer, arrival_time_ns)

        stamp = info.header.stamp if info else self.get_clock().now().to_msg()
        
        # 5. Manually populate ROS 2 Image Messages (Bypass cv_bridge)
        
        # RGB Message
        rgb_msg = Image()
        rgb_msg.header.stamp = stamp
        rgb_msg.header.frame_id = "camera_link_optical"
        rgb_msg.height = height
        rgb_msg.width = single_w
        rgb_msg.encoding = "bgr8"
        rgb_msg.step = single_w * 3
        rgb_msg.data = rgb_part.tobytes()
        self.rgb_pub.publish(rgb_msg)
        
        if info:
            info.header.stamp = stamp
            info.header.frame_id = "camera_link_optical"
            self.rgb_info_pub.publish(info)

        # Depth Message
        depth_msg = Image()
        depth_msg.header.stamp = stamp
        depth_msg.header.frame_id = "camera_link_optical"
        depth_msg.height = height
        depth_msg.width = single_w
        depth_msg.encoding = "16UC1"
        depth_msg.step = single_w * 2
        depth_msg.data = depth_16bit.tobytes()
        self.depth_pub.publish(depth_msg)

        if depth_info:
            depth_info.header.stamp = stamp
            depth_info.header.frame_id = "camera_link_optical"
            self.depth_info_pub.publish(depth_info)
            
        return Gst.FlowReturn.OK

def main(args=None):
    rclpy.init(args=args)
    node = RTABMapBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.pipeline.set_state(Gst.State.NULL)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

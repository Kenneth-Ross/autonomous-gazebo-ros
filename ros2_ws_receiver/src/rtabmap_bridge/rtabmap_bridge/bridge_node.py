#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import numpy as np
import threading
from collections import deque

class RTABMapBridgeNode(Node):
    def __init__(self):
        super().__init__('rtabmap_bridge')
        
        self.declare_parameter('rgb_port', 5000)
        self.declare_parameter('depth_port', 5001)
        
        self.rgb_port = self.get_parameter('rgb_port').value
        self.depth_port = self.get_parameter('depth_port').value
        
        self.bridge = CvBridge()
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
        
        # Dual Pipelines: RGB (Hardware H.264) / Depth (Lossless PNG)
        self.rgb_pipeline = self.create_rgb_pipeline(self.rgb_port)
        self.depth_pipeline = self.create_depth_pipeline(self.depth_port)
        
        self.get_logger().info(f"OAK-D Dual-Stream Bridge: RGB:{self.rgb_port} (MPP), Depth:{self.depth_port} (PNG)")
        
        self.rgb_pipeline.set_state(Gst.State.PLAYING)
        self.depth_pipeline.set_state(Gst.State.PLAYING)

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

    def create_rgb_pipeline(self, port):
        # mppvideodec for RK3588 H.264
        pipeline_str = (
            f"udpsrc port={port} ! "
            "application/x-rtp, encoding-name=H264, payload=96 ! "
            "rtph264depay ! h264parse ! mppvideodec ! videoconvert ! "
            "video/x-raw, format=BGR ! appsink name=sink_rgb emit-signals=True sync=False"
        )
        pipeline = Gst.parse_launch(pipeline_str)
        appsink = pipeline.get_by_name("sink_rgb")
        appsink.connect("new-sample", self.on_new_sample, "rgb")
        return pipeline

    def create_depth_pipeline(self, port):
        # PNG lossless decoding (CPU)
        pipeline_str = (
            f"udpsrc port={port} ! "
            "application/x-rtp, encoding-name=PNG, payload=96 ! "
            "rtppngdepay ! pngdec ! videoconvert ! "
            "video/x-raw, format=GRAY16_LE ! appsink name=sink_depth emit-signals=True sync=False"
        )
        pipeline = Gst.parse_launch(pipeline_str)
        appsink = pipeline.get_by_name("sink_depth")
        appsink.connect("new-sample", self.on_new_sample, "depth")
        return pipeline

    def on_new_sample(self, sink, stream_type):
        arrival_time_ns = self.get_clock().now().nanoseconds
        sample = sink.emit("pull-sample")
        if not sample: return Gst.FlowReturn.ERROR
            
        buf = sample.get_buffer()
        caps = sample.get_caps()
        height = caps.get_structure(0).get_value("height")
        width = caps.get_structure(0).get_value("width")
        
        res, map_info = buf.map(Gst.MapFlags.READ)
        if not res: return Gst.FlowReturn.ERROR
            
        with self.lock:
            if stream_type == "rgb":
                frame = np.frombuffer(map_info.data, dtype=np.uint8).reshape((height, width, 3))
                info = self.find_nearest_info(self.rgb_info_buffer, arrival_time_ns)
                encoding = "bgr8"
                pub, info_pub = self.rgb_pub, self.rgb_info_pub
            else:
                frame = np.frombuffer(map_info.data, dtype=np.uint16).reshape((height, width))
                info = self.find_nearest_info(self.depth_info_buffer, arrival_time_ns)
                encoding = "16UC1"
                pub, info_pub = self.depth_pub, self.depth_info_pub
        
        stamp = info.header.stamp if info else self.get_clock().now().to_msg()
        
        msg = self.bridge.cv2_to_imgmsg(frame, encoding=encoding)
        msg.header.stamp = stamp
        msg.header.frame_id = "camera_link_optical"
        pub.publish(msg)
        
        if info:
            info.header.stamp = stamp
            info.header.frame_id = "camera_link_optical"
            info_pub.publish(info)
            
        buf.unmap(map_info)
        return Gst.FlowReturn.OK

def main(args=None):
    rclpy.init(args=args)
    node = RTABMapBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.rgb_pipeline.set_state(Gst.State.NULL)
        node.depth_pipeline.set_state(Gst.State.NULL)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

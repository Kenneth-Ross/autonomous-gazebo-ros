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
from copy import deepcopy

class RTABMapBridgeNode(Node):
    def __init__(self):
        super().__init__('rtabmap_bridge')
        
        self.declare_parameter('rgb_port', 5000)
        self.declare_parameter('depth_port', 5001)
        
        self.rgb_port = self.get_parameter('rgb_port').value
        self.depth_port = self.get_parameter('depth_port').value
        
        self.bridge = CvBridge()
        self.lock = threading.Lock() # Fix race conditions on CameraInfo
        
        # Publishers
        self.rgb_pub = self.create_publisher(Image, 'camera/rgb/image_raw', 10)
        self.rgb_info_pub = self.create_publisher(CameraInfo, 'camera/rgb/camera_info', 10)
        self.depth_pub = self.create_publisher(Image, 'camera/depth/image_raw', 10)
        self.depth_info_pub = self.create_publisher(CameraInfo, 'camera/depth/camera_info', 10)
        
        # Subscribers for CameraInfo (to get original simulation timestamps)
        self.rgb_info_sub = self.create_subscription(CameraInfo, '/oakd/rgb/camera_info', self.rgb_info_callback, 10)
        self.depth_info_sub = self.create_subscription(CameraInfo, '/oakd/depth/camera_info', self.depth_info_callback, 10)
        
        self.latest_rgb_info = None
        self.latest_depth_info = None
        
        Gst.init(None)
        
        # Pipelines: RGB (Hardware Dec) / Depth (CPU PNG Dec)
        self.rgb_pipeline = self.create_rgb_pipeline(self.rgb_port)
        self.depth_pipeline = self.create_depth_pipeline(self.depth_port)
        
        self.get_logger().info("RTAB-Map Bridge: Frame IDs set to camera_link_optical.")
        
        self.start_pipeline(self.rgb_pipeline)
        self.start_pipeline(self.depth_pipeline)

    def rgb_info_callback(self, msg):
        with self.lock:
            self.latest_rgb_info = msg

    def depth_info_callback(self, msg):
        with self.lock:
            self.latest_depth_info = msg

    def create_rgb_pipeline(self, port):
        pipeline_str = (
            f"udpsrc port={port} ! "
            "application/x-rtp, encoding-name=H264, payload=96 ! "
            "rtph264depay ! "
            "h264parse ! "
            "mppvideodec ! "
            "videoconvert ! "
            "video/x-raw, format=BGR ! "
            "appsink name=sink_rgb emit-signals=True sync=False"
        )
        pipeline = Gst.parse_launch(pipeline_str)
        appsink = pipeline.get_by_name("sink_rgb")
        appsink.connect("new-sample", self.on_new_sample, "rgb")
        return pipeline

    def create_depth_pipeline(self, port):
        pipeline_str = (
            f"udpsrc port={port} ! "
            "application/x-rtp, encoding-name=PNG, payload=96 ! "
            "rtppngdepay ! "
            "pngdec ! "
            "videoconvert ! "
            "video/x-raw, format=GRAY16_LE ! "
            "appsink name=sink_depth emit-signals=True sync=False"
        )
        pipeline = Gst.parse_launch(pipeline_str)
        appsink = pipeline.get_by_name("sink_depth")
        appsink.connect("new-sample", self.on_new_sample, "depth")
        return pipeline

    def start_pipeline(self, pipeline):
        pipeline.set_state(Gst.State.PLAYING)
        
    def on_new_sample(self, sink, name):
        sample = sink.emit("pull-sample")
        if not sample: return Gst.FlowReturn.ERROR
            
        buf = sample.get_buffer()
        caps = sample.get_caps()
        height = caps.get_structure(0).get_value("height")
        width = caps.get_structure(0).get_value("width")
        
        res, map_info = buf.map(Gst.MapFlags.READ)
        if not res: return Gst.FlowReturn.ERROR
            
        with self.lock:
            if name == "rgb":
                frame = np.array(np.frombuffer(map_info.data, dtype=np.uint8), copy=True).reshape((height, width, 3))
                encoding = "bgr8"
                info = deepcopy(self.latest_rgb_info)
                pub, info_pub = self.rgb_pub, self.rgb_info_pub
            else:
                frame = np.array(np.frombuffer(map_info.data, dtype=np.uint16), copy=True).reshape((height, width))
                encoding = "16UC1"
                info = deepcopy(self.latest_depth_info)
                pub, info_pub = self.depth_pub, self.depth_info_pub
            
        buf.unmap(map_info)
        
        # Use Simulation Timestamp + Optical Frame ID
        stamp = info.header.stamp if info else self.get_clock().now().to_msg()
        
        msg = self.bridge.cv2_to_imgmsg(frame, encoding=encoding)
        msg.header.stamp = stamp
        msg.header.frame_id = "camera_link_optical" 
        
        pub.publish(msg)
        
        if info:
            info.header.stamp = stamp
            info.header.frame_id = "camera_link_optical"
            info_pub.publish(info)
            
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

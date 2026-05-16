import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import numpy as np
import threading
from collections import deque
import cv2
from cv_bridge import CvBridge

class RTABMapBridgeNode(Node):
    def __init__(self):
        super().__init__('rtabmap_bridge')
        
        self.declare_parameter('port', 5000)
        self.port = self.get_parameter('port').value
        
        self.lock = threading.Lock()
        self.frame_count = 0
        self.br = CvBridge()
        
        # Buffers for CameraInfo synchronization
        self.rgb_info_buffer = deque(maxlen=30)
        self.depth_info_buffer = deque(maxlen=30)
        
        # Publishers
        self.rgb_pub = self.create_publisher(Image, '/camera/rgb/image_raw', 10)
        self.rgb_info_pub = self.create_publisher(CameraInfo, '/camera/rgb/camera_info', 10)
        self.depth_pub = self.create_publisher(Image, '/camera/depth/image_raw', 10)
        self.depth_info_pub = self.create_publisher(CameraInfo, '/camera/depth/camera_info', 10)
        
        # Static Camera Info (Standard OAK-D 1280x800 calibration)
        self.static_info = CameraInfo()
        self.static_info.header.frame_id = "camera_link_optical"
        self.static_info.width = 1280
        self.static_info.height = 800
        self.static_info.k = [800.0, 0.0, 640.0, 0.0, 800.0, 400.0, 0.0, 0.0, 1.0]
        self.static_info.p = [800.0, 0.0, 640.0, 0.0, 0.0, 800.0, 400.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        self.static_info.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        self.static_info.distortion_model = "plumb_bob"
        self.static_info.d = [0.0, 0.0, 0.0, 0.0, 0.0]

        self.rgb_info_sub = self.create_subscription(CameraInfo, '/oakd/rgb/camera_info', self.rgb_info_callback, 10)
        self.depth_info_sub = self.create_subscription(CameraInfo, '/oakd/depth/camera_info', self.depth_info_callback, 10)
        
        Gst.init(None)
        self.pipeline = self.create_pipeline(self.port)
        self.get_logger().info(f"OAK-D Bridge (OpenCV Mode): Port {self.port}")
        self.pipeline.set_state(Gst.State.PLAYING)

    def rgb_info_callback(self, msg):
        with self.lock:
            self.rgb_info_buffer.append(msg)

    def depth_info_callback(self, msg):
        with self.lock:
            self.depth_info_buffer.append(msg)

    def find_nearest_info(self, buffer, target_stamp_ns):
        if not buffer: return None
        best_msg = None
        min_diff = float('inf')
        for msg in buffer:
            msg_ns = msg.header.stamp.sec * 1e9 + msg.header.stamp.nanosec
            diff = abs(msg_ns - target_stamp_ns)
            if diff < min_diff:
                min_diff = diff
                best_msg = msg
        return best_msg if min_diff < 1e8 else None

    def create_pipeline(self, port):
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
        self.frame_count += 1
        arrival_time_ns = self.get_clock().now().nanoseconds
        sample = sink.emit("pull-sample")
        if not sample: return Gst.FlowReturn.ERROR
            
        buf = sample.get_buffer()
        target_ts_ns = buf.pts if buf.pts != Gst.CLOCK_TIME_NONE else arrival_time_ns
        
        caps = sample.get_caps()
        h = caps.get_structure(0).get_value("height")
        w = caps.get_structure(0).get_value("width")
        
        res, map_info = buf.map(Gst.MapFlags.READ)
        if not res: return Gst.FlowReturn.ERROR
            
        # Convert GStreamer buffer to OpenCV/NumPy
        frame = np.frombuffer(map_info.data, dtype=np.uint8).reshape((h, w, 3))
        
        # Slice: [ RGB (1280) | MSB (1280) | LSB (1280) ]
        sw = w // 3
        bgr_frame = frame[:, 0:sw, :]
        msb_frame = frame[:, sw:2*sw, 0] # Use only one channel
        lsb_frame = frame[:, 2*sw:3*sw, 0]
        
        # Reconstruct 16-bit Depth
        depth_16bit = (msb_frame.astype(np.uint16) << 8) | lsb_frame.astype(np.uint16)
        
        buf.unmap(map_info)

        # Sync/Fallback Timestamps
        with self.lock:
            info = self.find_nearest_info(self.rgb_info_buffer, target_ts_ns)
            depth_info = self.find_nearest_info(self.depth_info_buffer, target_ts_ns)

        if info is not None:
            stamp = info.header.stamp
        else:
            stamp = rclpy.time.Time(nanoseconds=target_ts_ns).to_msg()
            info = self.static_info
            depth_info = self.static_info

        # Force valid stamp
        if stamp.sec == 0 and stamp.nanosec == 0:
            stamp = rclpy.time.Time(nanoseconds=target_ts_ns).to_msg()

        # Publish Images
        self.rgb_pub.publish(self.br.cv2_to_imgmsg(bgr_frame, encoding="bgr8", header=info.header))
        self.depth_pub.publish(self.br.cv2_to_imgmsg(depth_16bit, encoding="16UC1", header=info.header))
        
        # Update and publish info
        info.header.stamp = stamp
        info.header.frame_id = "camera_link_optical"
        self.rgb_info_pub.publish(info)
        
        depth_info.header.stamp = stamp
        depth_info.header.frame_id = "camera_link_optical"
        self.depth_info_pub.publish(depth_info)
            
        if self.frame_count % 30 == 0:
            self.get_logger().info(f"Published frame {self.frame_count}")
            
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

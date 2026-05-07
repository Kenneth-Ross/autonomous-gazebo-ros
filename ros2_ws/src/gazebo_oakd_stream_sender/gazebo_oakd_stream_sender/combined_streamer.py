import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import numpy as np
import message_filters

class CombinedStreamer(Node):
    def __init__(self):
        super().__init__('combined_streamer')

        self.declare_parameter('host', '127.0.0.1')
        self.host = self.get_parameter('host').get_parameter_value().string_value

        # OAK-D Resolution
        self.width = 1280
        self.height = 800
        
        # Combined frame will be 3x width: [RGB | Depth_MSB | Depth_LSB]
        # All parts will be 8-bit to fit into a standard video stream
        self.combined_width = self.width * 3
        self.combined_height = self.height
        
        self.br = CvBridge()

        # Synchronized Subscriptions
        self.rgb_sub = message_filters.Subscriber(self, Image, '/oakd/rgb/image_raw')
        self.depth_sub = message_filters.Subscriber(self, Image, '/oakd/depth/image_raw')
        
        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.rgb_sub, self.depth_sub], queue_size=10, slop=0.05
        )
        self.ts.registerCallback(self.callback)

        # GStreamer setup
        Gst.init(None)
        self.pipeline = self.create_gstreamer_pipeline()
        self.appsrc = self.pipeline.get_by_name('appsrc')

        caps_str = (
            f"video/x-raw,"
            f"format=BGR,"
            f"width={self.combined_width},"
            f"height={self.combined_height},"
            f"framerate=30/1"
        )
        self.appsrc.set_property('caps', Gst.Caps.from_string(caps_str))
        self.appsrc.set_property('format', 'time')
        
        self.pipeline.set_state(Gst.State.PLAYING)
        self.get_logger().info(f'OAK-D Combined Streamer started. Streaming to {self.host}:5000')

    def create_gstreamer_pipeline(self):
        # Using H.265 (HEVC) for better compression of the combined frame
        # x265enc is used on the server; mppvideodec will be used on the RK3588
        pipeline_str = (
            "appsrc name=appsrc ! "
            "videoconvert ! "
            "x265enc tune=zerolatency speed-preset=ultrafast bitrate=8000 ! "
            "rtph265pay ! "
            f"udpsink host={self.host} port=5000"
        )
        return Gst.parse_launch(pipeline_str)

    def callback(self, rgb_msg, depth_msg):
        # 1. Convert messages to OpenCV
        rgb_frame = self.br.imgmsg_to_cv2(rgb_msg, "bgr8")
        depth_meters = self.br.imgmsg_to_cv2(depth_msg, "32FC1")
        
        # 2. Process Depth: Meters -> Millimeters (16-bit)
        depth_meters = np.nan_to_num(depth_meters, nan=0.0, posinf=0.0, neginf=0.0)
        depth_mm = np.clip(depth_meters * 1000.0, 0, 65535).astype(np.uint16)
        
        # 3. Bit-Split: 16-bit -> Two 8-bit channels
        depth_msb = (depth_mm >> 8).astype(np.uint8)
        depth_lsb = (depth_mm & 0xFF).astype(np.uint8)
        
        # Convert mono depth parts to BGR to match the combined frame format
        depth_msb_bgr = cv2.cvtColor(depth_msb, cv2.COLOR_GRAY2BGR)
        depth_lsb_bgr = cv2.cvtColor(depth_lsb, cv2.COLOR_GRAY2BGR)
        
        # 4. Concatenate: [RGB | MSB | LSB]
        combined_frame = np.hstack((rgb_frame, depth_msb_bgr, depth_lsb_bgr))
        
        # 5. Push to GStreamer
        gst_buffer = Gst.Buffer.new_wrapped(combined_frame.tobytes())
        self.appsrc.emit('push-buffer', gst_buffer)

import cv2
def main(args=None):
    rclpy.init(args=args)
    streamer = CombinedStreamer()
    try:
        rclpy.spin(streamer)
    except KeyboardInterrupt:
        pass
    finally:
        streamer.pipeline.set_state(Gst.State.NULL)
        streamer.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import numpy as np
import message_filters
import cv2

class CombinedStreamer(Node):
    def __init__(self):
        super().__init__('combined_streamer')

        self.declare_parameter('host', '127.0.0.1')
        self.host = self.get_parameter('host').get_parameter_value().string_value

        # OAK-D Resolution
        self.width = 1280
        self.height = 800
        
        # Combined frame: [RGB | MSB | LSB]
        self.combined_width = self.width * 3
        self.combined_height = self.height
        
        self.br = CvBridge()

        # Synchronized Subscriptions
        self.rgb_sub = message_filters.Subscriber(self, Image, '/oakd/rgb/image_raw')
        self.depth_sub = message_filters.Subscriber(self, Image, '/oakd/depth/image_raw')
        
        # Debug connections
        self.rgb_sub.registerCallback(lambda msg: self.get_logger().info("Got RGB", once=True))
        self.depth_sub.registerCallback(lambda msg: self.get_logger().info("Got Depth", once=True))
        
        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.rgb_sub, self.depth_sub], queue_size=30, slop=0.2
        )
        self.ts.registerCallback(self.callback)
        self.frame_count = 0

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
        self.get_logger().info(f'OAK-D Combined Streamer (Bit-Split) started. Port: 5000')

    def create_gstreamer_pipeline(self):
        # Use high bitrate to preserve depth MSB/LSB bits
        pipeline_str = (
            "appsrc name=appsrc ! "
            "videoconvert ! "
            "x264enc tune=zerolatency speed-preset=ultrafast bitrate=12000 ! "
            "rtph264pay ! "
            f"udpsink host={self.host} port=5000"
        )
        return Gst.parse_launch(pipeline_str)

    def callback(self, rgb_msg, depth_msg):
        self.frame_count += 1
        if self.frame_count % 30 == 0:
            self.get_logger().info(f"Streaming frame {self.frame_count}...")
        # 1. Convert to OpenCV
        rgb_frame = self.br.imgmsg_to_cv2(rgb_msg, "bgr8")
        depth_meters = self.br.imgmsg_to_cv2(depth_msg, "32FC1")
        
        # 2. Meters -> Millimeters (16-bit)
        depth_meters = np.nan_to_num(depth_meters, nan=0.0, posinf=0.0, neginf=0.0)
        depth_mm = np.clip(depth_meters * 1000.0, 0, 65535).astype(np.uint16)
        
        # 3. Bit-Split: MSB and LSB
        depth_msb = (depth_mm >> 8).astype(np.uint8)
        depth_lsb = (depth_mm & 0xFF).astype(np.uint8)
        
        # 4. Replicate to 3 channels (to stay in BGR stream, preserved in Luminance)
        depth_msb_bgr = cv2.cvtColor(depth_msb, cv2.COLOR_GRAY2BGR)
        depth_lsb_bgr = cv2.cvtColor(depth_lsb, cv2.COLOR_GRAY2BGR)
        
        # 5. Concatenate
        combined_frame = np.hstack((rgb_frame, depth_msb_bgr, depth_lsb_bgr))
        
        # 6. Push
        gst_buffer = Gst.Buffer.new_wrapped(combined_frame.tobytes())
        # Embed ROS 2 Timestamp into GStreamer PTS (nanoseconds)
        ts_ns = rgb_msg.header.stamp.sec * 1_000_000_000 + rgb_msg.header.stamp.nanosec
        gst_buffer.pts = ts_ns
        self.appsrc.emit('push-buffer', gst_buffer)

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

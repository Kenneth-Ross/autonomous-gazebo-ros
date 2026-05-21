import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import numpy as np
import message_filters
import cv2
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

class CombinedStreamer(Node):
    def __init__(self):
        super().__init__('combined_streamer')

        # OAK-D Resolution
        self.width = 1280
        self.height = 800
        
        # Super-Frame (Horizontal Panorama): [RGB | MSB | LSB] stacked horizontally
        # Resulting size: 3840 x 800 (Within 4K horizontal limits)
        
        self.br = CvBridge()

        # Publisher for the Super-Frame (Local-only)
        # Using SENSOR_DATA (Best Effort) for high bandwidth
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5
        )
        self.pub = self.create_publisher(Image, '~/super_frame_local', qos_profile)

        # Synchronized Subscriptions (Using Best Effort to match Gazebo bridge)
        self.rgb_sub = message_filters.Subscriber(
            self, Image, '/oakd/rgb/image_raw', qos_profile=qos_profile)
        self.depth_sub = message_filters.Subscriber(
            self, Image, '/oakd/depth/image_raw', qos_profile=qos_profile)
        
        # Diagnostic counters to see if we're even receiving raw data
        self.rgb_count = 0
        self.depth_count = 0
        self.rgb_sub.registerCallback(lambda _: setattr(self, 'rgb_count', self.rgb_count + 1))
        self.depth_sub.registerCallback(lambda _: setattr(self, 'depth_count', self.depth_count + 1))

        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.rgb_sub, self.depth_sub], queue_size=50, slop=0.05
        )
        self.ts.registerCallback(self.callback)
        self.frame_count = 0

        self.get_logger().info('Horizontal OAK-D Super-Frame Streamer started (QoS: Best Effort).')
        
        # Diagnostic timer
        self.timer = self.create_timer(5.0, self.diagnose)

    def diagnose(self):
        self.get_logger().info(
            f"DIAGNOSTIC: RGB received: {self.rgb_count}, Depth received: {self.depth_count}, Super-Frames Sent: {self.frame_count}")
        if self.rgb_count > 0 and self.frame_count == 0:
            self.get_logger().warn("Receiving raw data but NO Super-Frames! Check timestamp sync.")

    def callback(self, rgb_msg, depth_msg):
        self.frame_count += 1
        if self.frame_count % 30 == 0:
            self.get_logger().info(f"Processing Super-Frame {self.frame_count}...")
        
        # 1. Convert to OpenCV
        rgb_frame = self.br.imgmsg_to_cv2(rgb_msg, "bgr8")
        depth_meters = self.br.imgmsg_to_cv2(depth_msg, "32FC1")
        
        # 2. Meters -> Millimeters (16-bit)
        depth_meters = np.nan_to_num(depth_meters, nan=0.0, posinf=0.0, neginf=0.0)
        depth_mm = np.clip(depth_meters * 1000.0, 0, 65535).astype(np.uint16)
        
        # 3. Bit-Split: MSB and LSB
        depth_msb = (depth_mm >> 8).astype(np.uint8)
        depth_lsb = (depth_mm & 0xFF).astype(np.uint8)
        
        # 4. Replicate to 3 channels
        depth_msb_bgr = cv2.cvtColor(depth_msb, cv2.COLOR_GRAY2BGR)
        depth_lsb_bgr = cv2.cvtColor(depth_lsb, cv2.COLOR_GRAY2BGR)
        
        # 5. Horizontal Stack: [RGB (1280) | MSB (1280) | LSB (1280)] -> 3840 width
        super_frame = np.hstack((rgb_frame, depth_msb_bgr, depth_lsb_bgr))
        
        # 6. Publish with the original timestamp
        msg = self.br.cv2_to_imgmsg(super_frame, encoding="bgr8")
        msg.header = rgb_msg.header
        self.pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    streamer = CombinedStreamer()
    try:
        rclpy.spin(streamer)
    except KeyboardInterrupt:
        pass
    finally:
        streamer.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

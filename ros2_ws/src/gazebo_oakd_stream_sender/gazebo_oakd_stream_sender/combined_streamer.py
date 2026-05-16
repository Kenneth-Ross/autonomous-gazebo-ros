import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import numpy as np
import message_filters
import cv2

class CombinedStreamer(Node):
    def __init__(self):
        super().__init__('combined_streamer')

        # OAK-D Resolution
        self.width = 1280
        self.height = 800
        
        # Super-Frame: [RGB | MSB | LSB] stacked vertically
        # Resulting size: 1280 x 2400
        
        self.br = CvBridge()

        # Publisher for the Super-Frame
        self.pub = self.create_publisher(Image, '/oakd/super_frame/image_raw', 10)

        # Synchronized Subscriptions
        self.rgb_sub = message_filters.Subscriber(self, Image, '/oakd/rgb/image_raw')
        self.depth_sub = message_filters.Subscriber(self, Image, '/oakd/depth/image_raw')
        
        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.rgb_sub, self.depth_sub], queue_size=30, slop=0.2
        )
        self.ts.registerCallback(self.callback)
        self.frame_count = 0

        self.get_logger().info('Virtual OAK-D Super-Frame Streamer started.')

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
        
        # 4. Replicate to 3 channels (to stay in BGR stream, preserved in Luminance)
        depth_msb_bgr = cv2.cvtColor(depth_msb, cv2.COLOR_GRAY2BGR)
        depth_lsb_bgr = cv2.cvtColor(depth_lsb, cv2.COLOR_GRAY2BGR)
        
        # 5. Vertical Stack: [RGB (800) / MSB (800) / LSB (800)] -> 2400 height
        super_frame = np.vstack((rgb_frame, depth_msb_bgr, depth_lsb_bgr))
        
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

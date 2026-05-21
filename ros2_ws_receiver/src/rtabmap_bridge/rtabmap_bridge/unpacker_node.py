import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
import numpy as np

from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

class UnpackerNode(Node):
    def __init__(self):
        super().__init__('unpacker_node')
        self.br = CvBridge()
        
        # OAK-D Specs
        self.width = 1280
        self.height = 800
        
        # Publishers for SLAM consumption
        # Using SENSOR_DATA (Best Effort) for consistency
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5
        )

        self.rgb_pub = self.create_publisher(Image, '/camera/rgb/image_raw', qos_profile)
        self.rgb_info_pub = self.create_publisher(CameraInfo, '/camera/rgb/camera_info', qos_profile)
        self.depth_pub = self.create_publisher(Image, '/camera/depth/image_raw', qos_profile)
        self.depth_info_pub = self.create_publisher(CameraInfo, '/camera/depth/camera_info', qos_profile)
        
        # Static Camera Info (Standard OAK-D 1280x800 calibration)
        self.static_info = CameraInfo()
        self.static_info.width = self.width
        self.static_info.height = self.height
        # Standard OAK-D FOV ~70 deg
        self.static_info.k = [800.0, 0.0, 640.0, 0.0, 800.0, 400.0, 0.0, 0.0, 1.0]
        self.static_info.p = [800.0, 0.0, 640.0, 0.0, 0.0, 800.0, 400.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        self.static_info.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        self.static_info.distortion_model = "plumb_bob"
        self.static_info.d = [0.0, 0.0, 0.0, 0.0, 0.0]

        # Subscriber to the Super-Frame
        self.sub = self.create_subscription(
            Image,
            'image_in',
            self.callback,
            qos_profile
        )
        
        self.get_logger().info('Horizontal OAK-D Unpacker Node started (QoS: Best Effort).')

    def callback(self, msg):
        # 1. Convert Super-Frame to OpenCV
        try:
            combined_frame = self.br.imgmsg_to_cv2(msg, "bgr8")
        except Exception as e:
            self.get_logger().error(f"Failed to convert image: {str(e)}")
            return
            
        if combined_frame.shape[1] != self.width * 3:
            self.get_logger().error(f"Unexpected Super-Frame width: {combined_frame.shape[1]}")
            return

        # 2. Slice Horizontally [Left: RGB | Mid: MSB | Right: LSB]
        rgb_frame = combined_frame[:, 0:self.width, :]
        msb_frame = combined_frame[:, self.width:2*self.width, 0] 
        lsb_frame = combined_frame[:, 2*self.width:3*self.width, 0]
        
        # 3. Reconstruct 16-bit Depth (mm)
        depth_16bit = (msb_frame.astype(np.uint16) << 8) | lsb_frame.astype(np.uint16)
        
        # 4. Prepare Header
        header = msg.header
        header.frame_id = "camera_link_optical"

        # 5. Publish RGB and Depth with IDENTICAL timestamp
        rgb_msg = self.br.cv2_to_imgmsg(rgb_frame, encoding="bgr8")
        rgb_msg.header = header
        self.rgb_pub.publish(rgb_msg)
        
        depth_msg = self.br.cv2_to_imgmsg(depth_16bit, encoding="16UC1")
        depth_msg.header = header
        self.depth_pub.publish(depth_msg)

        # 6. Publish Camera Info
        self.static_info.header = header
        self.rgb_info_pub.publish(self.static_info)
        self.depth_info_pub.publish(self.static_info)

def main(args=None):
    rclpy.init(args=args)
    node = UnpackerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

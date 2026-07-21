import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class FrameSaver(Node):
    def __init__(self):
        super().__init__('frame_saver')
        self.sub = self.create_subscription(Image, '/oakd/super_frame/image_raw', self.callback, 10)
        self.br = CvBridge()
        self.saved = False

    def callback(self, msg):
        if not self.saved:
            cv_img = self.br.imgmsg_to_cv2(msg, "bgr8")
            width = 1280
            rgb_frame = cv_img[:, 0:width]
            cv2.imwrite('test_image.jpg', rgb_frame)
            self.get_logger().info('Saved test_image.jpg')
            self.saved = True
            raise SystemExit

rclpy.init()
node = FrameSaver()
try:
    rclpy.spin(node)
except SystemExit:
    pass
rclpy.shutdown()

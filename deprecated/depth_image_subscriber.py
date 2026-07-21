import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import numpy as np

class DepthImageSubscriber(Node):
    def __init__(self):
        super().__init__('depth_image_subscriber')

        self.declare_parameter('host', '127.0.0.1')
        self.host = self.get_parameter('host').get_parameter_value().string_value

        self.image_width = 1280
        self.image_height = 800
        self.image_framerate = 30
        self.image_format_gst = 'GRAY16_LE' 

        # Corrected Topic from the new rgbd_camera sensor
        self.subscription = self.create_subscription(
            Image,
            '/oakd/depth/image_raw',
            self.listener_callback,
            10)
        self.br = CvBridge()

        Gst.init(None)
        self.pipeline = self.create_gstreamer_pipeline()
        self.appsrc = self.pipeline.get_by_name('appsrc')

        caps_str = (
            f"video/x-raw,"
            f"format={self.image_format_gst},"
            f"width={self.image_width},"
            f"height={self.image_height},"
            f"framerate={self.image_framerate}/1"
        )
        self.appsrc.set_property('caps', Gst.Caps.from_string(caps_str))
        self.appsrc.set_property('format', 'time')
        
        self.pipeline.set_state(Gst.State.PLAYING)
        self.get_logger().info('Depth Sender: Metrics Fixed (Meters -> Millimeters).')

    def create_gstreamer_pipeline(self):
        # CPU-based lossless PNG encoding
        pipeline_str = (
            "appsrc name=appsrc ! "
            "videoconvert ! "
            "pngenc ! "
            "rtppngpay ! "
            f"udpsink host={self.host} port=5001"
        )
        return Gst.parse_launch(pipeline_str)

    def listener_callback(self, data):
        # 1. Convert Gazebo Depth (32FC1 meters) to Numpy
        depth_meters = self.br.imgmsg_to_cv2(data, "32FC1")
        
        # 2. Scale to Millimeters (16UC1) - CRITICAL FOR SLAM
        # Replace NaNs/Infs with 0 and scale. Clip to max uint16 (65.5 meters).
        depth_meters = np.nan_to_num(depth_meters, nan=0.0, posinf=0.0, neginf=0.0)
        depth_mm = np.clip(depth_meters * 1000.0, 0, 65535).astype(np.uint16)
        
        # 3. Push to GStreamer
        gst_buffer = Gst.Buffer.new_wrapped(depth_mm.tobytes())
        self.appsrc.emit('push-buffer', gst_buffer)

    def destroy_node(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    depth_image_subscriber = DepthImageSubscriber()
    try:
        rclpy.spin(depth_image_subscriber)
    except KeyboardInterrupt:
        pass
    finally:
        depth_image_subscriber.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

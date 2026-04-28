import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import numpy as np

class RightImageSubscriber(Node):
    def __init__(self):
        super().__init__('right_image_subscriber')

        self.declare_parameter('host', '127.0.0.1')
        self.host = self.get_parameter('host').get_parameter_value().string_value

        # Hardcoded properties from the OAK-D URDF
        self.image_width = 1280
        self.image_height = 800
        self.image_framerate = 30
        # Format from cv_bridge conversion, and for GStreamer x-raw
        self.image_format_cv = 'mono8'
        self.image_format_gst = 'GRAY8'
        self.udp_port = 5002

        self.subscription = self.create_subscription(
            Image,
            '/oakd/right/image_raw',
            self.listener_callback,
            10)
        self.subscription
        self.br = CvBridge()

        # GStreamer setup
        Gst.init(None)
        self.pipeline = self.create_gstreamer_pipeline()
        self.appsrc = self.pipeline.get_by_name('appsrc')

        # Configure appsrc
        caps_str = (
            f"video/x-raw,"
            f"format={self.image_format_gst},"
            f"width={self.image_width},"
            f"height={self.image_height},"
            f"framerate={self.image_framerate}/1"
        )
        self.get_logger().info(f"Setting appsrc caps to: {caps_str}")
        caps = Gst.Caps.from_string(caps_str)
        self.appsrc.set_property('caps', caps)
        self.appsrc.set_property('format', 'time')
        
        self.pipeline.set_state(Gst.State.PLAYING)
        self.get_logger().info('Right Image Subscriber Node with GStreamer has been started.')

    def create_gstreamer_pipeline(self):
        pipeline_str = (
            "appsrc name=appsrc ! "
            "videoconvert ! "
            "video/x-raw,format=I420 ! " # Common intermediate format for x264enc
            "x264enc tune=zerolatency speed-preset=ultrafast ! "
            "rtph264pay ! "
            f"udpsink host={self.host} port={self.udp_port}"
        )
        self.get_logger().info(f'GStreamer Pipeline: {pipeline_str}')
        return Gst.parse_launch(pipeline_str)

    def listener_callback(self, data):
        # self.get_logger().info(f'Receiving video frame') # Too noisy
        current_frame = self.br.imgmsg_to_cv2(data, self.image_format_cv)
        
        gst_buffer = Gst.Buffer.new_wrapped(current_frame.tobytes())
        self.appsrc.emit('push-buffer', gst_buffer)

    def destroy_node(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    right_image_subscriber = RightImageSubscriber()
    try:
        rclpy.spin(right_image_subscriber)
    except KeyboardInterrupt:
        pass
    finally:
        right_image_subscriber.get_logger().info('Shutting down node.')
        right_image_subscriber.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import threading

class UnifiedReceiverNode(Node):
    def __init__(self):
        super().__init__('unified_receiver_node')
        self.br = CvBridge()

        # Stream configurations
        self.stream_configs = {
            'rgb': {'port': 5000, 'topic': '/edge_oakd/rgb/image_raw', 'format': 'BGR'},
            'left': {'port': 5001, 'topic': '/edge_oakd/left/image_raw', 'format': 'mono8'},
            'right': {'port': 5002, 'topic': '/edge_oakd/right/image_raw', 'format': 'mono8'}
        }

        self.pipelines = {}
        self.publishers = {}

        Gst.init(None)

        for name, config in self.stream_configs.items():
            self.get_logger().info(f"Setting up stream: {name}")
            # Create publisher
            self.publishers[name] = self.create_publisher(Image, config['topic'], 10)
            
            # Create pipeline
            pipeline = self.create_gstreamer_pipeline(name, config['port'])
            self.pipelines[name] = pipeline

            # Set pipeline to playing state
            pipeline.set_state(Gst.State.PLAYING)

        # Run GLib main loop in a separate thread
        self.loop = GLib.MainLoop()
        self.loop_thread = threading.Thread(target=self.loop.run)
        self.loop_thread.start()
        
        self.get_logger().info('Unified Receiver Node has been started.')

    def create_gstreamer_pipeline(self, name, port):
        # For the Orange Pi 5 Pro, you can try replacing 'avdec_h264' 
        # with 'mppvideodec' for hardware accelerated decoding.
        pipeline_str = (
            f"udpsrc port={port} "
            f"caps="application/x-rtp, media=(string)video, clock-rate=(int)90000, encoding-name=(string)H264, payload=(int)96" ! "
            "rtph264depay ! "
            "h264parse ! "
            "avdec_h264 ! "
            "videoconvert ! "
            "video/x-raw ! "
            "appsink name=appsink emit-signals=true"
        )
        self.get_logger().info(f"GStreamer Pipeline for {name}: {pipeline_str}")
        pipeline = Gst.parse_launch(pipeline_str)
        
        appsink = pipeline.get_by_name('appsink')
        appsink.connect('new-sample', self.on_new_sample, name)
        return pipeline

    def on_new_sample(self, appsink, stream_name):
        sample = appsink.emit('pull-sample')
        if sample:
            buf = sample.get_buffer()
            caps = sample.get_caps()
            
            # Extract video frame properties
            height = caps.get_structure(0).get_value('height')
            width = caps.get_structure(0).get_value('width')
            
            # Get data from Gst.Buffer as numpy array
            frame_data = buf.extract_dup(0, buf.get_size())
            frame = np.ndarray((height, width), buffer=frame_data, dtype=np.uint8)

            # For RGB stream, reshape to 3 channels
            if stream_name == 'rgb':
                frame = np.ndarray((height, width, 3), buffer=frame_data, dtype=np.uint8)

            # Convert to ROS message and publish
            config = self.stream_configs[stream_name]
            img_msg = self.br.cv2_to_imgmsg(frame, encoding=config['format'])
            img_msg.header.stamp = self.get_clock().now().to_msg()
            img_msg.header.frame_id = stream_name + '_camera'
            self.publishers[stream_name].publish(img_msg)
            
        return Gst.FlowReturn.OK

    def destroy_node(self):
        self.get_logger().info('Shutting down GStreamer pipelines.')
        for name, pipeline in self.pipelines.items():
            pipeline.set_state(Gst.State.NULL)
        self.loop.quit()
        self.loop_thread.join()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    unified_receiver_node = UnifiedReceiverNode()
    try:
        rclpy.spin(unified_receiver_node)
    except KeyboardInterrupt:
        pass
    finally:
        unified_receiver_node.get_logger().info('Shutting down node.')
        unified_receiver_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

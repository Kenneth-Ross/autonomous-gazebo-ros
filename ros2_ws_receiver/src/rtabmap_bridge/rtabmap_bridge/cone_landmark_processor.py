#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
import numpy as np
import message_filters
from std_msgs.msg import String

class ConeLandmarkProcessor(Node):
    def __init__(self):
        super().__init__('cone_landmark_processor')
        self.bridge = CvBridge()
        
        self.depth_sub = message_filters.Subscriber(self, Image, '/camera/depth/image_raw')
        self.yolo_sub = message_filters.Subscriber(self, String, '/yolo/detections')
        
        # Approximate sync for jittery streams
        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.depth_sub, self.yolo_sub], queue_size=10, slop=0.2
        )
        self.ts.registerCallback(self.callback)
        
        self.landmark_pub = self.create_publisher(Image, 'rtabmap/user_data', 10)
        self.get_logger().info("Cone Landmark Processor (Robust) initialized.")

    def callback(self, depth_msg, yolo_msg):
        try:
            coords = [int(c) for c in yolo_msg.data.split(',')]
            cx, cy = coords[0] + coords[2]//2, coords[1] + coords[3]//2
        except Exception as e:
            self.get_logger().warn(f"Failed to parse YOLO detections: {e}")
            return

        depth_img = self.bridge.imgmsg_to_cv2(depth_msg, desired_encoding='passthrough')
        h, w = depth_img.shape[:2]

        # FIX: 5x5 Window average to handle noise and holes (Metric rescue)
        window_size = 5
        half_w = window_size // 2
        
        # Clamp bounds
        y_start = max(0, cy - half_w)
        y_end = min(h, cy + half_w + 1)
        x_start = max(0, cx - half_w)
        x_end = min(w, cx + half_w + 1)
        
        roi = depth_img[y_start:y_end, x_start:x_end]
        
        # Mask out invalid pixels (0 or NaN)
        valid_mask = (roi > 0) & (~np.isnan(roi))
        if not np.any(valid_mask):
            self.get_logger().debug("No valid depth pixels in 5x5 window.")
            return
            
        z = np.mean(roi[valid_mask])
        
        self.get_logger().info(f"Robustly detected cone at distance: {z:.3f}m")
        
        # In the future, project to 3D and publish to RTAB-Map landmarks
        # landmarks = ...
        # self.landmark_pub.publish(landmarks)

def main(args=None):
    rclpy.init(args=args)
    node = ConeLandmarkProcessor()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

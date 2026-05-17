#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from vision_msgs.msg import Detection2DArray
from cv_bridge import CvBridge
import numpy as np
import message_filters

from rtabmap_msgs.msg import UserData
from geometry_msgs.msg import Point
import cv2

class ConeLandmarkProcessor(Node):
    def __init__(self):
        super().__init__('cone_landmark_processor')
        self.bridge = CvBridge()
        self.camera_info = None
        
        # Subscribers
        self.depth_sub = message_filters.Subscriber(self, Image, '/camera/depth/image_raw')
        self.det_sub = message_filters.Subscriber(self, Detection2DArray, '/cone_detections')
        self.info_sub = self.create_subscription(CameraInfo, '/camera/rgb/camera_info', self.info_callback, 10)
        
        # Precise sync using standard ROS headers
        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.depth_sub, self.det_sub], queue_size=10, slop=0.05
        )
        self.ts.registerCallback(self.callback)
        
        self.landmark_pub = self.create_publisher(UserData, 'rtabmap/user_data', 10)
        self.get_logger().info("Cone Landmark Processor (RTAB-Map Ready) initialized.")

    def info_callback(self, msg):
        self.camera_info = msg

    def callback(self, depth_msg, det_msg):
        if self.camera_info is None:
            self.get_logger().warn("Waiting for CameraInfo...")
            return

        depth_img = self.bridge.imgmsg_to_cv2(depth_msg, desired_encoding='passthrough')
        h, w = depth_img.shape[:2]
        
        # Intrinsics: fx, fy, cx, cy
        fx = self.camera_info.k[0]
        fy = self.camera_info.k[4]
        ppx = self.camera_info.k[2]
        ppy = self.camera_info.k[5]

        landmarks_3d = []

        for det in det_msg.detections:
            cx = int(det.bbox.center.position.x)
            cy = int(det.bbox.center.position.y)
            sx = int(det.bbox.size_x)
            sy = int(det.bbox.size_y)

            # Define ROI for depth sampling
            y_start = max(0, cy - sy//4)
            y_end = min(h, cy + sy//4)
            x_start = max(0, cx - sx//4)
            x_end = min(w, cx + sx//4)
            
            roi = depth_img[y_start:y_end, x_start:x_end]
            valid_mask = (roi > 0) & (~np.isnan(roi))
            if not np.any(valid_mask):
                continue
            
            z = np.median(roi[valid_mask])
            z_meters = z / 1000.0 if depth_msg.encoding == "16UC1" else z
            
            # 3D Projection: (u, v, z) -> (x, y, z)
            x = (cx - ppx) * z_meters / fx
            y = (cy - ppy) * z_meters / fy
            
            landmarks_3d.append([x, y, z_meters])
            self.get_logger().info(f"Landmark at: x={x:.2f}, y={y:.2f}, z={z_meters:.2f}")

        if landmarks_3d:
            # Package as UserData for RTAB-Map
            user_data_msg = UserData()
            user_data_msg.header = depth_msg.header
            
            # Simple serialization: flat array of [x, y, z] triples
            # RTAB-Map's UserData is flexible, but a common pattern is 
            # to serialize custom objects using pickle or a byte array.
            # Here we'll use a simple byte array of floats.
            landmarks_np = np.array(landmarks_3d, dtype=np.float32)
            user_data_msg.data = landmarks_np.tobytes()
            
            self.landmark_pub.publish(user_data_msg)

def main(args=None):
    rclpy.init(args=args)
    node = ConeLandmarkProcessor()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

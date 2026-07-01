#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from vision_msgs.msg import Detection2DArray
from rtabmap_msgs.msg import LandmarkDetections, LandmarkDetection
from geometry_msgs.msg import PointStamped, Pose
from cv_bridge import CvBridge
import numpy as np
import message_filters
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from tf2_ros import Buffer, TransformListener
import tf2_geometry_msgs

class ConeLandmarkProcessor(Node):
    def __init__(self):
        super().__init__('cone_landmark_processor')
        self.bridge = CvBridge()
        
        # TF Buffer and Listener
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        # Database of persistent landmarks in the map frame
        # List of dicts: {'id': int, 'position': np.array([x, y, z]), 'class': str}
        self.landmarks = []
        self.next_landmark_id = 1
        self.association_threshold = 1.0 # meters
        
        # Standardized Pipeline QoS (Best Effort) for high bandwidth depth stream
        pipeline_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            durability=DurabilityPolicy.VOLATILE
        )
        
        # Subscribe to CameraInfo dynamically
        self.camera_info = None
        self.info_sub = self.create_subscription(
            CameraInfo,
            '/edge/camera/depth/camera_info',
            self.info_callback,
            pipeline_qos
        )
        
        # Subscribe to Depth and YOLO Detections using message_filters
        self.depth_sub = message_filters.Subscriber(
            self, Image, '/edge/camera/depth/image_raw', qos_profile=pipeline_qos
        )
        self.yolo_sub = message_filters.Subscriber(
            self, Detection2DArray, '/yolo/detections', qos_profile=10
        )
        
        # Approximate time synchronizer (100ms slop to handle network jitter)
        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.depth_sub, self.yolo_sub], queue_size=10, slop=0.1
        )
        self.ts.registerCallback(self.callback)
        
        # Publisher for RTAB-Map Landmarks
        self.landmark_pub = self.create_publisher(LandmarkDetections, '/rtabmap/landmark_detections', 10)
        self.get_logger().info("Cone Landmark Processor (Robust) initialized.")

    def info_callback(self, msg):
        self.camera_info = msg

    def transform_point(self, x, y, z, from_frame, to_frame, stamp):
        p = PointStamped()
        p.header.frame_id = from_frame
        p.header.stamp = stamp
        p.point.x = float(x)
        p.point.y = float(y)
        p.point.z = float(z)
        try:
            # Lookup transform with a small timeout
            t = self.tf_buffer.lookup_transform(
                to_frame, from_frame, stamp, rclpy.duration.Duration(seconds=0.1)
            )
            p_transformed = tf2_geometry_msgs.do_transform_point(p, t)
            return np.array([p_transformed.point.x, p_transformed.point.y, p_transformed.point.z])
        except Exception as e:
            self.get_logger().debug(f"TF transform failed from {from_frame} to {to_frame}: {e}")
            return None

    def callback(self, depth_msg, yolo_msg):
        if self.camera_info is None:
            self.get_logger().warn("Waiting for camera_info...")
            return
            
        if not yolo_msg.detections:
            return

        # Parse Camera Intrinsics
        fx = self.camera_info.k[0]
        fy = self.camera_info.k[4]
        cx = self.camera_info.k[2]
        cy = self.camera_info.k[5]
        
        if fx == 0 or fy == 0:
            self.get_logger().error("Invalid camera intrinsics (fx/fy is 0).")
            return

        # Convert Depth image
        try:
            depth_img = self.bridge.imgmsg_to_cv2(depth_msg, desired_encoding='passthrough')
        except Exception as e:
            self.get_logger().error(f"Failed to convert depth image: {e}")
            return
            
        h, w = depth_img.shape[:2]
        
        # Prepare RTAB-Map LandmarkDetections message
        landmarks_msg = LandmarkDetections()
        landmarks_msg.header = depth_msg.header # Publish relative to camera_link_optical
        
        # Track the stamp for TF lookups
        stamp = depth_msg.header.stamp

        for det in yolo_msg.detections:
            # Extract 2D bounding box
            u_center = det.bbox.center.position.x
            v_center = det.bbox.center.position.y
            size_x = det.bbox.size_x
            size_y = det.bbox.size_y
            
            # Setup 5x5 window around the center
            window_size = 5
            half_w = window_size // 2
            
            y_start = max(0, int(v_center - half_w))
            y_end = min(h, int(v_center + half_w + 1))
            x_start = max(0, int(u_center - half_w))
            x_end = min(w, int(u_center + half_w + 1))
            
            roi = depth_img[y_start:y_end, x_start:x_end]
            
            # Filter out invalid depth pixels (0 or NaN)
            valid_mask = (roi > 0) & (~np.isnan(roi))
            if not np.any(valid_mask):
                continue
                
            # Median depth in millimeters, convert to meters
            z_m = np.median(roi[valid_mask]) / 1000.0
            
            # Project to 3D Camera Coordinates
            x_c = ((u_center - cx) * z_m) / fx
            y_c = ((v_center - cy) * z_m) / fy
            z_c = z_m
            
            # Data Association: Transform to map frame for persistent ID tracking
            # We check both 'map' and fallback 'odom' as target frames
            map_pos = self.transform_point(x_c, y_c, z_c, depth_msg.header.frame_id, 'map', stamp)
            if map_pos is None:
                map_pos = self.transform_point(x_c, y_c, z_c, depth_msg.header.frame_id, 'odom', stamp)
                
            landmark_id = -1
            class_id = "cone"
            if det.results:
                class_id = det.results[0].hypothesis.class_id

            if map_pos is not None:
                # Find matching landmark of the same class within threshold distance
                matched_landmark = None
                min_dist = float('inf')
                for lm in self.landmarks:
                    if lm['class'] == class_id:
                        dist = np.linalg.norm(lm['position'] - map_pos)
                        if dist < self.association_threshold and dist < min_dist:
                            min_dist = dist
                            matched_landmark = lm
                
                if matched_landmark is not None:
                    # Update matched landmark position with a small filter gain
                    matched_landmark['position'] = 0.9 * matched_landmark['position'] + 0.1 * map_pos
                    landmark_id = matched_landmark['id']
                else:
                    # Register new landmark
                    landmark_id = self.next_landmark_id
                    self.next_landmark_id += 1
                    self.landmarks.append({
                        'id': landmark_id,
                        'position': map_pos,
                        'class': class_id
                    })
                    self.get_logger().info(f"Registered new landmark: {class_id} (ID: {landmark_id}) at {map_pos}")
            else:
                self.get_logger().debug("Could not transform landmark to map/odom frame; using transient landmark ID.")
            
            # Create LandmarkDetection (relative to camera_link_optical frame)
            lm_det = LandmarkDetection()
            lm_det.id = landmark_id
            lm_det.landmark_frame_id = f"{class_id}_{landmark_id}"
            lm_det.size = float(max(size_x, size_y) * z_m / fx) # Estimate physical width of the cone
            
            # Pose relative to camera
            lm_det.pose.pose.position.x = float(x_c)
            lm_det.pose.pose.position.y = float(y_c)
            lm_det.pose.pose.position.z = float(z_c)
            lm_det.pose.pose.orientation.w = 1.0 # Point landmark, no orientation
            
            # Add simple covariance
            lm_det.pose.covariance[0] = 0.05 # variance x
            lm_det.pose.covariance[7] = 0.05 # variance y
            lm_det.pose.covariance[14] = 0.1 # variance z
            
            landmarks_msg.detections.append(lm_det)
            
        if landmarks_msg.detections:
            self.landmark_pub.publish(landmarks_msg)

def main(args=None):
    rclpy.init(args=args)
    node = ConeLandmarkProcessor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

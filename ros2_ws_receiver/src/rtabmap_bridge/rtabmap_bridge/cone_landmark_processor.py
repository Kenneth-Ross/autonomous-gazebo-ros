#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from vision_msgs.msg import Detection2DArray
from rtabmap_msgs.msg import LandmarkDetections, LandmarkDetection
from geometry_msgs.msg import PointStamped, Pose
from visualization_msgs.msg import Marker, MarkerArray
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
        
        # Candidate tracker (debouncing)
        # List of dicts: {'position': np.array([x, y, z]), 'class': str, 'hits': int}
        self.candidates = []
        self.min_hits = 3
        
        self.next_landmark_id = 1
        
        # Standardized Pipeline QoS (Reliable)
        pipeline_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
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
        # Publisher for Foxglove Visualization
        self.marker_pub = self.create_publisher(MarkerArray, '/yolo/landmark_markers', 10)
        self.get_logger().info("Cone Landmark Processor (Robust Tracker) initialized.")

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
            # Lookup transform with a 0.3s timeout for network jitter
            t = self.tf_buffer.lookup_transform(
                to_frame, from_frame, stamp, rclpy.duration.Duration(seconds=0.3)
            )
            p_transformed = tf2_geometry_msgs.do_transform_point(p, t)
            return np.array([p_transformed.point.x, p_transformed.point.y, p_transformed.point.z])
        except Exception as e:
            # Silently return None on failure to avoid log spam on fast movement
            return None

    def get_association_threshold(self, depth_m):
        base_threshold = 0.5
        depth_scaling = 0.04 * depth_m * depth_m
        return min(base_threshold + depth_scaling, 2.5)

    def callback(self, depth_msg, yolo_msg):
        if self.camera_info is None:
            self.get_logger().warn("Waiting for camera_info...")
            return
            
        # Decay all candidate hits (simulating temporal loss)
        for cand in self.candidates:
            cand['hits'] -= 1
        
        if not yolo_msg.detections:
            self.candidates = [c for c in self.candidates if c['hits'] > 0]
            return

        # Parse Camera Intrinsics
        fx = self.camera_info.k[0]
        fy = self.camera_info.k[4]
        cx = self.camera_info.k[2]
        cy = self.camera_info.k[5]
        
        if fx == 0 or fy == 0:
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
        landmarks_msg.header = depth_msg.header
        stamp = depth_msg.header.stamp

        for det in yolo_msg.detections:
            u_center = det.bbox.center.position.x
            v_center = det.bbox.center.position.y
            size_x = det.bbox.size_x
            size_y = det.bbox.size_y
            
            window_size = 5
            half_w = window_size // 2
            
            y_start = max(0, int(v_center - half_w))
            y_end = min(h, int(v_center + half_w + 1))
            x_start = max(0, int(u_center - half_w))
            x_end = min(w, int(u_center + half_w + 1))
            
            roi = depth_img[y_start:y_end, x_start:x_end]
            valid_mask = (roi > 0) & (~np.isnan(roi))
            if not np.any(valid_mask):
                continue
                
            # 25th percentile depth (avoid background)
            z_m = np.percentile(roi[valid_mask], 25) / 1000.0
            
            # Max range cutoff (stereo depth too noisy beyond this)
            if z_m > 6.0:
                continue
            
            x_c = ((u_center - cx) * z_m) / fx
            y_c = ((v_center - cy) * z_m) / fy
            z_c = z_m
            
            # Use EXACT stamp, wait up to 0.3s
            map_pos = self.transform_point(x_c, y_c, z_c, depth_msg.header.frame_id, 'map', stamp)
            if map_pos is None:
                map_pos = self.transform_point(x_c, y_c, z_c, depth_msg.header.frame_id, 'odom', stamp)
                
            class_id = "cone"
            if det.results:
                class_id = det.results[0].hypothesis.class_id

            if map_pos is not None:
                dist_to_camera = np.linalg.norm([x_c, y_c, z_c])
                assoc_thresh = self.get_association_threshold(dist_to_camera)
                
                # Check persistent landmarks first
                matched_lm = None
                min_dist = float('inf')
                for lm in self.landmarks:
                    if lm['class'] == class_id:
                        dist = np.linalg.norm(lm['position'] - map_pos)
                        if dist < assoc_thresh and dist < min_dist:
                            min_dist = dist
                            matched_lm = lm
                
                if matched_lm is not None:
                    matched_lm['position'] = 0.9 * matched_lm['position'] + 0.1 * map_pos
                    landmark_id = matched_lm['id']
                else:
                    # Check candidates
                    matched_cand = None
                    min_dist_cand = float('inf')
                    for cand in self.candidates:
                        if cand['class'] == class_id:
                            dist = np.linalg.norm(cand['position'] - map_pos)
                            if dist < assoc_thresh and dist < min_dist_cand:
                                min_dist_cand = dist
                                matched_cand = cand
                    
                    if matched_cand is not None:
                        matched_cand['position'] = 0.5 * matched_cand['position'] + 0.5 * map_pos
                        matched_cand['hits'] += 2 # Restore the 1 we subtracted, plus 1 for this hit
                        if matched_cand['hits'] >= self.min_hits:
                            # Promote to landmark!
                            landmark_id = self.next_landmark_id
                            self.next_landmark_id += 1
                            self.landmarks.append({
                                'id': landmark_id,
                                'position': matched_cand['position'],
                                'class': class_id
                            })
                            self.get_logger().info(f"PROMOTED candidate to landmark: {class_id} (ID: {landmark_id}) at {matched_cand['position']}")
                            self.candidates.remove(matched_cand)
                        else:
                            landmark_id = -1 # Not ready yet
                    else:
                        # Create new candidate
                        self.candidates.append({
                            'position': map_pos,
                            'class': class_id,
                            'hits': 1
                        })
                        landmark_id = -1
            else:
                landmark_id = -1
            
            # Only send to RTAB-Map if it's a persistent landmark
            if landmark_id != -1:
                lm_det = LandmarkDetection()
                lm_det.id = landmark_id
                lm_det.landmark_frame_id = f"{class_id}_{landmark_id}"
                lm_det.size = float(max(size_x, size_y) * z_m / fx)
                
                lm_det.pose.pose.position.x = float(x_c)
                lm_det.pose.pose.position.y = float(y_c)
                lm_det.pose.pose.position.z = float(z_c)
                lm_det.pose.pose.orientation.w = 1.0
                
                lm_det.pose.covariance[0] = 0.05
                lm_det.pose.covariance[7] = 0.05
                lm_det.pose.covariance[14] = 0.1
                
                landmarks_msg.landmarks.append(lm_det)
                
        # Clean up dead candidates
        self.candidates = [c for c in self.candidates if c['hits'] > 0]
            
        if landmarks_msg.landmarks:
            self.landmark_pub.publish(landmarks_msg)

        # Publish MarkerArray for Foxglove visualization
        if self.landmarks:
            marker_array = MarkerArray()
            for lm in self.landmarks:
                # Text marker
                marker = Marker()
                marker.header.frame_id = 'map'
                marker.header.stamp = depth_msg.header.stamp
                marker.ns = 'landmarks'
                marker.id = lm['id']
                marker.type = Marker.TEXT_VIEW_FACING
                marker.action = Marker.ADD
                marker.pose.position.x = float(lm['position'][0])
                marker.pose.position.y = float(lm['position'][1])
                marker.pose.position.z = float(lm['position'][2]) + 0.5
                marker.pose.orientation.w = 1.0
                marker.scale.z = 0.4
                marker.color.a = 1.0
                marker.color.r = 1.0
                marker.color.g = 1.0
                marker.color.b = 0.0
                marker.text = f"{lm['class']}_{lm['id']}"
                marker_array.markers.append(marker)
                
                # Shape marker
                shape = Marker()
                shape.header.frame_id = 'map'
                shape.header.stamp = depth_msg.header.stamp
                shape.ns = 'landmarks_shapes'
                shape.id = lm['id']
                shape.type = Marker.CYLINDER
                shape.action = Marker.ADD
                shape.pose.position.x = float(lm['position'][0])
                shape.pose.position.y = float(lm['position'][1])
                shape.pose.position.z = float(lm['position'][2]) + 0.2
                shape.pose.orientation.w = 1.0
                shape.scale.x = 0.3
                shape.scale.y = 0.3
                shape.scale.z = 0.4
                shape.color.a = 0.8
                shape.color.r = 1.0
                shape.color.g = 0.5
                shape.color.b = 0.0
                marker_array.markers.append(shape)
                
            self.marker_pub.publish(marker_array)

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

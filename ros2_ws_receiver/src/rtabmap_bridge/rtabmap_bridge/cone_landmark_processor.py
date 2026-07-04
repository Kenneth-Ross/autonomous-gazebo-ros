#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo, CompressedImage
from vision_msgs.msg import Detection2DArray
from rtabmap_msgs.msg import LandmarkDetections, LandmarkDetection
from geometry_msgs.msg import PointStamped, Pose
from visualization_msgs.msg import Marker, MarkerArray
from cv_bridge import CvBridge
import numpy as np
import cv2
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
        self.min_hits = 2
        
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
        
        self.rgb_sub = message_filters.Subscriber(
            self, CompressedImage, '/edge/camera/rgb/image_raw/compressed', qos_profile=pipeline_qos
        )
        self.depth_sub = message_filters.Subscriber(
            self, Image, '/edge/camera/depth/image_raw', qos_profile=pipeline_qos
        )
        self.yolo_sub = message_filters.Subscriber(
            self, Detection2DArray, '/yolo/detections', qos_profile=10
        )
        
        # Approximate time synchronizer (100ms slop to handle network jitter)
        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.rgb_sub, self.depth_sub, self.yolo_sub], queue_size=10, slop=0.1
        )
        self.ts.registerCallback(self.callback)
        
        # Publisher for RTAB-Map Landmarks
        self.landmark_pub = self.create_publisher(LandmarkDetections, '/rtabmap/landmark_detections', 10)
        # Publisher for Foxglove Visualization
        self.marker_pub = self.create_publisher(MarkerArray, '/yolo/landmark_markers', 10)
        self.annotated_pub = self.create_publisher(CompressedImage, '/yolo/annotated/compressed', 10)
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
            # Throttle log to avoid spam, but still let us know if TF is broken
            self.get_logger().error(f"TF Error ({from_frame} -> {to_frame}): {e}", throttle_duration_sec=2.0)
            return None

    def get_association_threshold(self, depth_m):
        # Tighter threshold for dense cone tracks to prevent cross-association
        base_threshold = 1.0
        depth_scaling = 0.05 * depth_m
        return min(base_threshold + depth_scaling, 2.0)

    def callback(self, rgb_msg, depth_msg, yolo_msg):
        if self.camera_info is None:
            self.get_logger().warn("Waiting for camera_info...")
            return
            
        # Check if anyone is actually subscribing to the annotated image topic to save CPU
        if self.annotated_pub.get_subscription_count() > 0:
            try:
                np_arr = np.frombuffer(rgb_msg.data, np.uint8)
                cv_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            except Exception as e:
                self.get_logger().error(f"Failed to decode RGB image: {e}")
                cv_img = None
        else:
            cv_img = None
            
        # Decay all candidate hits (simulating temporal loss)
        for cand in self.candidates:
            cand['hits'] -= 1
        
        if not yolo_msg.detections:
            self.candidates = [c for c in self.candidates if c['hits'] > -3]
            # Always publish markers even if no detections in this frame
            self.publish_markers()
            
            # Publish unannotated image so stream doesn't freeze (only if someone is watching)
            if cv_img is not None:
                self.annotated_pub.publish(rgb_msg)
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
            
            # Use inner 50% of bbox to avoid edge artifacts
            roi_w = max(5, int(size_x * 0.5))
            roi_h = max(5, int(size_y * 0.5))
            
            y_start = max(0, int(v_center - roi_h // 2))
            y_end = min(h, int(v_center + roi_h // 2 + 1))
            x_start = max(0, int(u_center - roi_w // 2))
            x_end = min(w, int(u_center + roi_w // 2 + 1))
            
            roi = depth_img[y_start:y_end, x_start:x_end]
            valid_mask = (roi > 0) & (~np.isnan(roi))
            if not np.any(valid_mask):
                continue
                
            # 25th percentile depth (avoid background)
            raw_z = np.percentile(roi[valid_mask], 25)
            z_m = raw_z / 1000.0
            
            # Temporary logging to verify depth units (if raw_z is e.g. < 15, it's already in meters!)
            if hasattr(self, 'debug_count'):
                self.debug_count += 1
            else:
                self.debug_count = 0
                
            if self.debug_count % 30 == 0:
                self.get_logger().info(f"Depth check: raw_z={raw_z:.1f}, scaled z_m={z_m:.3f}m")
            
            # Max range cutoff (increased for simulation, real OAK-D gets noisy past 6-8m)
            if z_m > 20.0:
                continue
            
            x_c = ((u_center - cx) * z_m) / fx
            y_c = ((v_center - cy) * z_m) / fy
            z_c = z_m
            
            # Use EXACT stamp, wait up to 0.3s
            map_pos = self.transform_point(x_c, y_c, z_c, depth_msg.header.frame_id, 'map', stamp)
            if map_pos is None:
                # Discard detection if map transform isn't available yet to prevent frame mixing
                continue
                
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
                    # Do NOT update position of persistent landmarks to prevent drift from odom errors
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
                
            # Draw annotation on image if someone is watching
            if cv_img is not None:
                x1 = int(u_center - size_x / 2)
                y1 = int(v_center - size_y / 2)
                x2 = int(u_center + size_x / 2)
                y2 = int(v_center + size_y / 2)
                
                if landmark_id != -1:
                    label = f"ID {landmark_id}: {z_m:.1f} (m)"
                else:
                    label = f"ID ?: {z_m:.1f} (m)"
                    
                cv2.rectangle(cv_img, (x1, y1), (x2, y2), (0, 255, 0), 3)
                cv2.putText(cv_img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
                
        # Clean up dead candidates that haven't been seen in several frames
        self.candidates = [c for c in self.candidates if c['hits'] > -3]
            
        if landmarks_msg.landmarks:
            self.landmark_pub.publish(landmarks_msg)
            
        self.publish_markers()
        
        # Publish annotated image if someone is watching
        if cv_img is not None:
            success, compressed_data = cv2.imencode('.jpg', cv_img)
            if success:
                annotated_msg = CompressedImage()
                annotated_msg.header = rgb_msg.header
                annotated_msg.format = 'jpeg'
                annotated_msg.data = compressed_data.tobytes()
                self.annotated_pub.publish(annotated_msg)
            
    def publish_markers(self):
        # Always publish visualization markers so they don't flicker/disappear
        marker_array = MarkerArray()
        
        # Add persistent landmarks (Green)
        for lm in self.landmarks:
            marker = Marker()
            marker.header.frame_id = "map"
            marker.header.stamp = self.get_clock().now().to_msg()
            marker.ns = "persistent_cones"
            marker.id = lm['id']
            marker.type = Marker.CYLINDER
            marker.action = Marker.ADD
            marker.pose.position.x = float(lm['position'][0])
            marker.pose.position.y = float(lm['position'][1])
            marker.pose.position.z = float(lm['position'][2])
            marker.pose.orientation.w = 1.0
            marker.scale.x = 0.4
            marker.scale.y = 0.4
            marker.scale.z = 0.6
            marker.color.a = 1.0
            marker.color.r = 1.0
            marker.color.g = 0.5
            marker.color.b = 0.0
            marker_array.markers.append(marker)
            
            # Text label
            text_marker = Marker()
            text_marker.header = marker.header
            text_marker.ns = "persistent_labels"
            text_marker.id = lm['id'] + 1000
            text_marker.type = Marker.TEXT_VIEW_FACING
            text_marker.action = Marker.ADD
            text_marker.pose.position.x = float(lm['position'][0])
            text_marker.pose.position.y = float(lm['position'][1])
            text_marker.pose.position.z = float(lm['position'][2]) + 0.8
            text_marker.scale.z = 0.3
            text_marker.color.a = 1.0
            text_marker.color.r = 1.0
            text_marker.color.g = 1.0
            text_marker.color.b = 0.0
            text_marker.text = f"{lm['class']} {lm['id']}"
            marker_array.markers.append(text_marker)
            
        # Add candidates (Ghostly Red/Yellow)
        for i, cand in enumerate(self.candidates):
            marker = Marker()
            marker.header.frame_id = "map"
            marker.header.stamp = self.get_clock().now().to_msg()
            marker.ns = "candidate_cones"
            marker.id = i + 2000
            marker.type = Marker.CYLINDER
            marker.action = Marker.ADD
            marker.pose.position.x = float(cand['position'][0])
            marker.pose.position.y = float(cand['position'][1])
            marker.pose.position.z = float(cand['position'][2])
            marker.pose.orientation.w = 1.0
            marker.scale.x = 0.4
            marker.scale.y = 0.4
            marker.scale.z = 0.6
            marker.color.a = 0.4  # Semi-transparent
            marker.color.r = 1.0
            marker.color.g = 0.0
            marker.color.b = 0.0
            marker_array.markers.append(marker)
            
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

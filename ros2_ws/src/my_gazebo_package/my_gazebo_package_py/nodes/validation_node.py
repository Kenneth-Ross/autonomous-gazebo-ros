#!/usr/bin/python3
import rclpy
from rclpy.node import Node
from tf2_msgs.msg import TFMessage
from nav_msgs.msg import Odometry
from visualization_msgs.msg import MarkerArray
import math

from geometry_msgs.msg import Pose
from nav_msgs.msg import Odometry
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy, QoSDurabilityPolicy

import tf2_ros
from geometry_msgs.msg import TransformStamped

class ValidationNode(Node):
    def __init__(self):
        super().__init__('validation_node')
        
        # Ground truth states
        self.gt_cones = {} # {id: (x, y)}
        
        # Estimated states
        self.est_cones = {} # {id: (x, y)}
        
        latched_qos = QoSProfile(
            depth=1,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST
        )
        
        # Subscriptions
        self.create_subscription(Pose, '/ground_truth/car_pose', self.gt_car_cb, 10)
        self.create_subscription(MarkerArray, '/ground_truth/cones', self.gt_cones_cb, latched_qos)
        self.create_subscription(Odometry, '/odometry/filtered', self.est_odom_cb, 10)
        self.create_subscription(MarkerArray, '/yolo/landmark_markers', self.est_markers_cb, 10)
        
        self.timer = self.create_timer(2.0, self.print_validation_stats)
        self.get_logger().info('Validation node started. Waiting for data...')

    def gt_car_cb(self, msg):
        self.gt_car_pose = (msg.position.x, msg.position.y)

    def gt_cones_cb(self, msg):
        for marker in msg.markers:
            if marker.action == marker.ADD or marker.action == marker.MODIFY:
                self.gt_cones[marker.id] = (marker.pose.position.x, marker.pose.position.y)
            elif marker.action == marker.DELETEALL:
                self.gt_cones = {}

    def est_odom_cb(self, msg):
        self.est_car_pose = (msg.pose.pose.position.x, msg.pose.pose.position.y)

    def est_markers_cb(self, msg):
        for marker in msg.markers:
            if marker.action == marker.ADD or marker.action == marker.MODIFY:
                self.est_cones[marker.id] = (marker.pose.position.x, marker.pose.position.y)
            elif marker.action == marker.DELETE and marker.id in self.est_cones:
                del self.est_cones[marker.id]

    def print_validation_stats(self):
        print("\n" + "="*40, flush=True)
        print("=== AUTONOMOUS VALIDATION SCOREBOARD ===", flush=True)
        print("="*40, flush=True)
        
        # 1. Car Position Error
        if self.gt_car_pose and self.est_car_pose:
            dx = self.est_car_pose[0] - self.gt_car_pose[0]
            dy = self.est_car_pose[1] - self.gt_car_pose[1]
            car_err = math.sqrt(dx**2 + dy**2)
            print(f"Vehicle Pos Error (EKF vs Gazebo): {car_err:.3f} meters", flush=True)
        else:
            print("Vehicle Pos Error: Waiting for GT and Odom...", flush=True)
            
        # 2. Cone Position Error (Matching)
        if self.gt_cones and self.est_cones:
            total_err = 0.0
            matched_cones = 0
            
            for est_id, est_pos in self.est_cones.items():
                min_dist = float('inf')
                for gt_id, gt_pos in self.gt_cones.items():
                    dist = math.sqrt((est_pos[0] - gt_pos[0])**2 + (est_pos[1] - gt_pos[1])**2)
                    if dist < min_dist:
                        min_dist = dist
                
                if min_dist < 2.0:
                    total_err += min_dist
                    matched_cones += 1
            
            if matched_cones > 0:
                avg_err = total_err / matched_cones
                precision = (matched_cones / len(self.est_cones)) * 100
                recall = (matched_cones / len(self.gt_cones)) * 100
                print(f"Cones Found: {len(self.est_cones)} / {len(self.gt_cones)} true cones", flush=True)
                print(f"Cone Recall: {recall:.1f}%", flush=True)
                print(f"Cone False Positive Rate: {100 - precision:.1f}%", flush=True)
                print(f"Avg Cone Localization Error: {avg_err:.3f} meters", flush=True)
            else:
                print(f"Cones Found: {len(self.est_cones)}. No valid matches.", flush=True)
        else:
            print(f"Cone Mapping: Waiting for cones (GT={len(self.gt_cones)}, Est={len(self.est_cones)})", flush=True)
            
        print("="*40, flush=True)

def main(args=None):
    rclpy.init(args=args)
    node = ValidationNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

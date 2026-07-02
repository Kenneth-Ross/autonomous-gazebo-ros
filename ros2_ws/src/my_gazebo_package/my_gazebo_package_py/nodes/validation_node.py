#!/usr/bin/python3
import rclpy
from rclpy.node import Node
from tf2_msgs.msg import TFMessage
from nav_msgs.msg import Odometry
from visualization_msgs.msg import MarkerArray
import math

class ValidationNode(Node):
    def __init__(self):
        super().__init__('validation_node')
        
        # Ground truth states
        self.gt_car_pose = None
        self.gt_cones = {} # {id: (x, y)}
        
        # Estimated states
        self.est_car_pose = None
        self.est_cones = {} # {id: (x, y)}
        
        # Subscriptions
        self.create_subscription(TFMessage, '/gazebo/pose_info', self.gt_pose_cb, 10)
        self.create_subscription(Odometry, '/odometry/filtered', self.est_odom_cb, 10)
        self.create_subscription(MarkerArray, '/yolo/landmark_markers', self.est_markers_cb, 10)
        
        self.timer = self.create_timer(2.0, self.print_validation_stats)
        self.get_logger().info('Validation node started. Waiting for data...')

    def gt_pose_cb(self, msg):
        for transform in msg.transforms:
            frame_id = transform.child_frame_id
            x = transform.transform.translation.x
            y = transform.transform.translation.y
            
            if 'ackermann_car' in frame_id or 'my_robot' in frame_id:
                self.gt_car_pose = (x, y)
            elif 'cone' in frame_id:
                self.gt_cones[frame_id] = (x, y)

    def est_odom_cb(self, msg):
        self.est_car_pose = (msg.pose.pose.position.x, msg.pose.pose.position.y)

    def est_markers_cb(self, msg):
        for marker in msg.markers:
            if marker.action == marker.ADD or marker.action == marker.MODIFY:
                self.est_cones[marker.id] = (marker.pose.position.x, marker.pose.position.y)
            elif marker.action == marker.DELETE and marker.id in self.est_cones:
                del self.est_cones[marker.id]

    def print_validation_stats(self):
        print("\n" + "="*40)
        print("=== AUTONOMOUS VALIDATION SCOREBOARD ===")
        print("="*40)
        
        # 1. Car Position Error
        if self.gt_car_pose and self.est_car_pose:
            dx = self.est_car_pose[0] - self.gt_car_pose[0]
            dy = self.est_car_pose[1] - self.gt_car_pose[1]
            car_err = math.sqrt(dx**2 + dy**2)
            print(f"Vehicle Pos Error (EKF vs Gazebo): {car_err:.3f} meters")
        else:
            print("Vehicle Pos Error: Waiting for GT and Odom...")
            
        # 2. Cone Position Error (Matching)
        if self.gt_cones and self.est_cones:
            total_err = 0.0
            matched_cones = 0
            
            for est_id, est_pos in self.est_cones.items():
                # Find nearest ground truth cone
                min_dist = float('inf')
                for gt_id, gt_pos in self.gt_cones.items():
                    dist = math.sqrt((est_pos[0] - gt_pos[0])**2 + (est_pos[1] - gt_pos[1])**2)
                    if dist < min_dist:
                        min_dist = dist
                
                if min_dist < 2.0: # Consider it a match if within 2 meters
                    total_err += min_dist
                    matched_cones += 1
            
            if matched_cones > 0:
                avg_err = total_err / matched_cones
                precision = (matched_cones / len(self.est_cones)) * 100
                recall = (matched_cones / len(self.gt_cones)) * 100
                print(f"Cones Found: {len(self.est_cones)} / {len(self.gt_cones)} true cones")
                print(f"Cone Recall: {recall:.1f}%")
                print(f"Cone False Positive Rate: {100 - precision:.1f}%")
                print(f"Avg Cone Localization Error: {avg_err:.3f} meters")
            else:
                print(f"Cones Found: {len(self.est_cones)}. No valid matches (all >2m error).")
        else:
            print("Cone Mapping: Waiting for mapped cones...")
            
        print("="*40)

def main(args=None):
    rclpy.init(args=args)
    node = ValidationNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

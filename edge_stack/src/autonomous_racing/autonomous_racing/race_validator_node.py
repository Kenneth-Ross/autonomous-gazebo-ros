#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from visualization_msgs.msg import MarkerArray
from tf2_msgs.msg import TFMessage
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from std_msgs.msg import String, Float32, Int32
import math
import json
import time

class RaceValidatorNode(Node):
    def __init__(self):
        super().__init__('race_validator_node')
        
        self.declare_parameter('stall_timeout', 10.0)
        self.declare_parameter('track_width', 6.0)
        
        self.centerline = [] # list of (x,y)
        self.gt_car_pose = None
        self.est_car_pose = None
        self.current_vel = 0.0
        
        self.lap_progress = 0.0
        self.laps_completed = 0
        self.last_progress_time = time.time()
        self.max_progress_seen = 0.0
        self.status = "running"
        self.start_time = time.time()
        
        # Publishers
        self.failure_pub = self.create_publisher(String, '/racing/failure', 10)
        self.progress_pub = self.create_publisher(Float32, '/racing/lap_progress', 10)
        self.lap_pub = self.create_publisher(Int32, '/racing/lap_complete', 10)
        self.status_pub = self.create_publisher(String, '/racing/run_status', 10)
        
        # Subscriptions
        self.create_subscription(TFMessage, '/ground_truth/tf', self.gt_tf_cb, 10)
        self.create_subscription(MarkerArray, '/ground_truth/cones', self.gt_cones_cb, 10)
        self.create_subscription(Odometry, '/odom', self.odom_cb, 10)
        self.create_subscription(Twist, '/cmd_vel', self.cmd_vel_cb, 10)
        
        self.create_timer(0.1, self.validation_loop)
        
        self.get_logger().info("Race Validator Node started.")

    def gt_tf_cb(self, msg):
        for transform in msg.transforms:
            if transform.child_frame_id in ('ackermann_car', 'my_robot'):
                self.gt_car_pose = (transform.transform.translation.x, transform.transform.translation.y)

    def gt_cones_cb(self, msg):
        if len(self.centerline) > 0 or len(msg.markers) == 0:
            return
            
        # Assuming first half is inner, second half is outer
        markers = msg.markers
        num_pairs = len(markers) // 2
        
        inner = [(m.pose.position.x, m.pose.position.y) for m in markers[:num_pairs]]
        outer = [(m.pose.position.x, m.pose.position.y) for m in markers[num_pairs:2*num_pairs]]
        
        for p1, p2 in zip(inner, outer):
            self.centerline.append(((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0))
            
        self.get_logger().info(f"Validator extracted {len(self.centerline)} centerline points.")

    def odom_cb(self, msg):
        self.est_car_pose = (msg.pose.pose.position.x, msg.pose.pose.position.y)
        self.current_vel = msg.twist.twist.linear.x

    def cmd_vel_cb(self, msg):
        pass

    def get_closest_centerline_index(self):
        if not self.centerline or not self.gt_car_pose:
            return -1, float('inf')
            
        min_dist = float('inf')
        closest_idx = -1
        
        for i, pt in enumerate(self.centerline):
            d = math.sqrt((pt[0] - self.gt_car_pose[0])**2 + (pt[1] - self.gt_car_pose[1])**2)
            if d < min_dist:
                min_dist = d
                closest_idx = i
                
        return closest_idx, min_dist

    def validation_loop(self):
        if self.status != "running":
            return
            
        status_msg = String()
        status_msg.data = self.status
        self.status_pub.publish(status_msg)
        
        if not self.centerline or not self.gt_car_pose:
            return
            
        idx, dist_to_center = self.get_closest_centerline_index()
        progress = idx / len(self.centerline)
        
        # Lap completion logic
        if self.lap_progress > 0.9 and progress < 0.1:
            self.laps_completed += 1
            self.lap_pub.publish(Int32(data=self.laps_completed))
            self.get_logger().info(f"Lap {self.laps_completed} completed!")
            self.max_progress_seen = 0.0
            
        self.lap_progress = progress
        self.progress_pub.publish(Float32(data=self.lap_progress))
        
        if progress > self.max_progress_seen + 0.02:
            self.max_progress_seen = progress
            self.last_progress_time = time.time()
            
        # Failure checks
        stall_timeout = self.get_parameter('stall_timeout').value
        track_width = self.get_parameter('track_width').value
        
        failure_type = None
        if dist_to_center > (track_width / 2.0):
            failure_type = "track_departure"
        elif (time.time() - self.last_progress_time) > stall_timeout:
            failure_type = "stall_timeout"
            
        if failure_type:
            self.status = "failed"
            self.get_logger().warn(f"Race failed: {failure_type}")
            
            fail_msg = {
                "failure_type": failure_type,
                "failure_time": time.time() - self.start_time,
                "failure_pose": {"x": self.gt_car_pose[0], "y": self.gt_car_pose[1]},
                "failure_velocity": self.current_vel,
                "laps_completed": self.laps_completed,
                "lap_progress_at_failure": self.lap_progress,
                "duration_seconds": time.time() - self.start_time
            }
            msg = String()
            msg.data = json.dumps(fail_msg)
            self.failure_pub.publish(msg)
            
            status_msg.data = self.status
            self.status_pub.publish(status_msg)

def main(args=None):
    rclpy.init(args=args)
    node = RaceValidatorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

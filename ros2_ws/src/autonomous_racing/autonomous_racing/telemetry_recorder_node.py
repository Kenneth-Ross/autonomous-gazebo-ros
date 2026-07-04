#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist, TwistStamped
from std_msgs.msg import String
from tf2_msgs.msg import TFMessage
from visualization_msgs.msg import MarkerArray
import json
import time
import os
import math

class TelemetryRecorderNode(Node):
    def __init__(self):
        super().__init__('telemetry_recorder_node')
        
        self.declare_parameter('telemetry_dir', './telemetry')
        base_dir = self.get_parameter('telemetry_dir').value
        
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
            
        run_id = time.strftime("run_%Y%m%d_%H%M%S")
        self.run_dir = os.path.join(base_dir, run_id)
        os.makedirs(self.run_dir)
        
        self.pose_file = open(os.path.join(self.run_dir, 'pose_log.jsonl'), 'a')
        self.control_file = open(os.path.join(self.run_dir, 'control_log.jsonl'), 'a')
        self.summary_file = os.path.join(self.run_dir, 'run_summary.json')
        
        self.recording = True
        
        # Subscriptions
        self.create_subscription(Odometry, '/odom', self.odom_cb, 10)
        self.create_subscription(TwistStamped, '/car/control_request', self.control_request_cb, 10)
        self.create_subscription(String, '/racing/failure', self.failure_cb, 10)
        self.create_subscription(String, '/racing/run_status', self.status_cb, 10)
        
        self.start_time = time.time()
        self.get_logger().info(f"Telemetry Recorder Node started. Logging to {self.run_dir}")

    def get_yaw_from_pose(self, pose):
        q = pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    def odom_cb(self, msg):
        if not self.recording: return
        
        yaw = self.get_yaw_from_pose(msg.pose.pose)
        
        data = {
            "t": time.time() - self.start_time,
            "x": msg.pose.pose.position.x,
            "y": msg.pose.pose.position.y,
            "yaw": yaw,
            "vx": msg.twist.twist.linear.x,
            "vy": msg.twist.twist.linear.y,
            "wz": msg.twist.twist.angular.z
        }
        self.pose_file.write(json.dumps(data) + '\n')
        self.pose_file.flush()

    def control_request_cb(self, msg):
        if not self.recording: return
        
        data = {
            "t": time.time() - self.start_time,
            "cmd_vx": msg.twist.linear.x,
            "cmd_wz": msg.twist.angular.z
        }
        self.control_file.write(json.dumps(data) + '\n')
        self.control_file.flush()

    def failure_cb(self, msg):
        if not self.recording: return
        
        self.recording = False
        self.pose_file.close()
        self.control_file.close()
        
        fail_data = json.loads(msg.data)
        
        # Write summary
        with open(self.summary_file, 'w') as f:
            json.dump(fail_data, f, indent=2)
            
        self.get_logger().info(f"Run failed. Telemetry saved to {self.summary_file}")

    def status_cb(self, msg):
        if msg.data == "completed" and self.recording:
            self.recording = False
            self.pose_file.close()
            self.control_file.close()
            
            success_data = {
                "result": "completed",
                "duration_seconds": time.time() - self.start_time
            }
            with open(self.summary_file, 'w') as f:
                json.dump(success_data, f, indent=2)
            self.get_logger().info("Run completed successfully. Telemetry saved.")

def main(args=None):
    rclpy.init(args=args)
    node = TelemetryRecorderNode()
    rclpy.spin(node)
    
    if node.recording:
        node.pose_file.close()
        node.control_file.close()
        
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

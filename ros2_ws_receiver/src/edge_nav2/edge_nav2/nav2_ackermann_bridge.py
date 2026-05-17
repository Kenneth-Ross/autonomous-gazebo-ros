#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TwistStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import Float32
import math
import time

class Nav2AckermannBridge(Node):
    def __init__(self):
        super().__init__('nav2_ackermann_bridge')

        # --- Parameters ---
        self.declare_parameter('wheelbase', 1.511)
        self.declare_parameter('min_velocity', 0.1)

        self.L = self.get_parameter('wheelbase').value
        self.min_vel = self.get_parameter('min_velocity').value

        # --- State ---
        self.target_vel = 0.0
        self.target_omega = 0.0

        # --- Subscriptions ---
        self.create_subscription(Twist, '/nav_cmd_vel', self.nav_cmd_cb, 10)

        # --- Publishers ---
        # Brain sends high-level targets to the ECU
        self.control_pub = self.create_publisher(TwistStamped, '/car/control_request', 10)

        # --- Control Loop Timer (20Hz) ---
        self.create_timer(0.05, self.control_loop)

        self.get_logger().info('Nav2 Ackermann Bridge (v3 - High-Level Brain) started.')

    def nav_cmd_cb(self, msg):
        self.target_vel = msg.linear.x
        self.target_omega = msg.angular.z

    def control_loop(self):
        # 1. Steering Target (Bicycle Model)
        # Brain calculates the required steering angle for the ECU to achieve
        v_eff = max(abs(self.target_vel), self.min_vel)
        steering_angle = math.atan(self.L * self.target_omega / v_eff)

        # 2. Publish Unified Packet
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"
        
        # High-level targets for the ECU:
        # linear.x -> Target Velocity (m/s)
        # angular.z -> Target Steering Angle (radians)
        msg.twist.linear.x = float(self.target_vel)
        msg.twist.angular.z = float(steering_angle)
        
        self.control_pub.publish(msg)



def main(args=None):
    rclpy.init(args=args)
    node = Nav2AckermannBridge()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()

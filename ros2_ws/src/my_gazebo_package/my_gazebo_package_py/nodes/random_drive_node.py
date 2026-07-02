#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import random
import math

class RandomDriveNode(Node):
    def __init__(self):
        super().__init__('random_drive_node')
        self.publisher = self.create_publisher(Twist, '/cmd_vel', 10)
        self.timer = self.create_timer(2.0, self.timer_callback)
        self.get_logger().info('Random Drive Node started. Will change steering every 2s.')
        self.twist = Twist()
        self.twist.linear.x = 2.0  # Constant forward speed

    def timer_callback(self):
        # Random steering angle between -0.4 and 0.4 rad/s
        self.twist.angular.z = random.uniform(-0.4, 0.4)
        
        # Add occasional straight driving
        if random.random() < 0.3:
            self.twist.angular.z = 0.0
            
        self.get_logger().info(f'Publishing random cmd_vel: {self.twist.angular.z:.2f} rad/s')
        
    def spin(self):
        # Publish at 10Hz
        pub_timer = self.create_timer(0.1, lambda: self.publisher.publish(self.twist))
        rclpy.spin(self)

def main(args=None):
    rclpy.init(args=args)
    node = RandomDriveNode()
    try:
        node.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

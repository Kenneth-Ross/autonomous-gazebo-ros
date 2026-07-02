#!/usr/bin/python3
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
        # Base circular steering (e.g., turning left at 0.3 rad/s)
        base_steering = 0.3
        
        # Add random noise to the steering to make it wander slightly while circling
        # Noise between -0.15 and +0.15
        noise = random.uniform(-0.15, 0.15)
        
        self.twist.angular.z = base_steering + noise
        
        # Occasional tight turns or wide turns
        if random.random() < 0.2:
            self.twist.angular.z = random.uniform(0.4, 0.6) # Tight turn
        elif random.random() < 0.1:
            self.twist.angular.z = random.uniform(-0.1, 0.1) # Briefly go straight/right
            
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

#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Path, Odometry
import math

class PurePursuitNode(Node):
    def __init__(self):
        super().__init__('pure_pursuit_node')
        
        # Params
        self.declare_parameter('lookahead_distance', 3.0)
        self.declare_parameter('lookahead_gain', 0.5)
        self.declare_parameter('target_speed', 2.0)
        self.declare_parameter('min_lookahead', 1.5)
        self.declare_parameter('max_lookahead', 8.0)
        self.declare_parameter('wheelbase', 1.0)

        self.path = None
        self.current_pose = None
        self.current_velocity = 0.0

        # Subscriptions
        self.create_subscription(Path, '/racing/target_path', self.path_cb, 10)
        self.create_subscription(Odometry, '/odom', self.odom_cb, 10)

        # Publishers
        self.control_pub = self.create_publisher(TwistStamped, '/car/control_request', 10)

        # Control loop at 20 Hz
        self.create_timer(0.05, self.control_loop)
        
        self.get_logger().info("Pure Pursuit Node started.")

    def path_cb(self, msg):
        self.path = msg

    def odom_cb(self, msg):
        self.current_pose = msg.pose.pose
        self.current_velocity = msg.twist.twist.linear.x

    def get_yaw_from_pose(self, pose):
        q = pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    def get_distance(self, p1, p2):
        return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

    def find_goal_point(self, lookahead):
        if not self.path or not self.path.poses:
            return None
            
        # Find closest point on path
        min_dist = float('inf')
        closest_idx = 0
        for i, pose_stamped in enumerate(self.path.poses):
            d = self.get_distance(self.current_pose.position, pose_stamped.pose.position)
            if d < min_dist:
                min_dist = d
                closest_idx = i
                
        # From closest point, search forward for the point that is 'lookahead' away
        goal_point = None
        for i in range(closest_idx, len(self.path.poses)):
            d = self.get_distance(self.current_pose.position, self.path.poses[i].pose.position)
            if d >= lookahead:
                goal_point = self.path.poses[i].pose.position
                break
                
        # If we didn't find a point far enough, use the last point
        if not goal_point:
            goal_point = self.path.poses[-1].pose.position
            
        return goal_point

    def control_loop(self):
        if not self.current_pose or not self.path:
            return

        lookahead_base = self.get_parameter('lookahead_distance').value
        lookahead_gain = self.get_parameter('lookahead_gain').value
        min_lookahead = self.get_parameter('min_lookahead').value
        max_lookahead = self.get_parameter('max_lookahead').value
        target_speed = self.get_parameter('target_speed').value
        wheelbase = self.get_parameter('wheelbase').value

        lookahead = max(min_lookahead, min(max_lookahead, lookahead_base + lookahead_gain * abs(self.current_velocity)))
        
        goal_point = self.find_goal_point(lookahead)
        if not goal_point:
            return

        car_yaw = self.get_yaw_from_pose(self.current_pose)
        
        # Transform goal point to vehicle frame to get alpha
        dx = goal_point.x - self.current_pose.position.x
        dy = goal_point.y - self.current_pose.position.y
        
        # alpha is angle to goal in vehicle frame
        alpha = math.atan2(dy, dx) - car_yaw
        
        # Normalize alpha to [-pi, pi]
        alpha = math.atan2(math.sin(alpha), math.cos(alpha))

        steering = math.atan2(2.0 * wheelbase * math.sin(alpha), lookahead)

        cmd = TwistStamped()
        cmd.header.stamp = self.get_clock().now().to_msg()
        cmd.header.frame_id = "base_link"
        cmd.twist.linear.x = float(target_speed)
        cmd.twist.angular.z = float(steering)

        self.control_pub.publish(cmd)

def main(args=None):
    rclpy.init(args=args)
    node = PurePursuitNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

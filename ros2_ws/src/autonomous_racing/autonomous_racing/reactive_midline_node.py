#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from visualization_msgs.msg import MarkerArray
from nav_msgs.msg import Odometry, Path
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
import math

class ReactiveMidlineNode(Node):
    def __init__(self):
        super().__init__('reactive_midline_node')
        
        self.declare_parameter('fov_distance', 15.0)
        self.declare_parameter('fov_angle', 1.0) # radians (~60 deg half-angle)
        
        self.current_pose = None
        self.cones = []
        self.phase = "exploring"
        
        # Subscriptions
        self.create_subscription(MarkerArray, '/rtabmap/landmarks', self.landmarks_cb, 10)
        self.create_subscription(Odometry, '/odom', self.odom_cb, 10)
        self.create_subscription(String, '/racing/phase', self.phase_cb, 10)
        
        # Publishers
        self.path_pub = self.create_publisher(Path, '/racing/local_path', 10)
        
        self.create_timer(0.1, self.compute_midline)
        self.get_logger().info("Reactive Midline Node started.")

    def phase_cb(self, msg):
        self.phase = msg.data

    def odom_cb(self, msg):
        self.current_pose = msg.pose.pose

    def landmarks_cb(self, msg):
        if self.phase != "exploring":
            return
            
        # Keep track of all seen cones or just current? The prompt says "compute local midline from cones currently visible"
        # We can just store the latest marker array
        self.cones = []
        for marker in msg.markers:
            # We assume markers are in 'odom' or 'world' frame.
            self.cones.append((marker.pose.position.x, marker.pose.position.y))

    def get_yaw_from_pose(self, pose):
        q = pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    def transform_to_local(self, cx, cy, rx, ry, ryaw):
        # Translate
        dx = cx - rx
        dy = cy - ry
        # Rotate
        lx = dx * math.cos(-ryaw) - dy * math.sin(-ryaw)
        ly = dx * math.sin(-ryaw) + dy * math.cos(-ryaw)
        return lx, ly

    def compute_midline(self):
        if not self.current_pose or self.phase != "exploring":
            return
            
        rx = self.current_pose.position.x
        ry = self.current_pose.position.y
        ryaw = self.get_yaw_from_pose(self.current_pose)
        
        fov_dist = self.get_parameter('fov_distance').value
        fov_angle = self.get_parameter('fov_angle').value
        
        # Filter cones in FOV
        left_cones = []
        right_cones = []
        
        for cx, cy in self.cones:
            lx, ly = self.transform_to_local(cx, cy, rx, ry, ryaw)
            
            # Check if in front and within distance
            if lx > 0 and math.hypot(lx, ly) < fov_dist:
                angle = math.atan2(ly, lx)
                if abs(angle) < fov_angle:
                    # Sort into left/right based on local Y
                    if ly > 0:
                        left_cones.append((lx, ly))
                    else:
                        right_cones.append((lx, ly))
                        
        # Sort by distance (lx)
        left_cones.sort(key=lambda c: c[0])
        right_cones.sort(key=lambda c: c[0])
        
        path_msg = Path()
        path_msg.header.stamp = self.get_clock().now().to_msg()
        path_msg.header.frame_id = "base_link" # We are computing in local frame
        
        # If we don't have enough cones, just project a straight line ahead
        if len(left_cones) == 0 and len(right_cones) == 0:
            for d in range(1, 6):
                ps = PoseStamped()
                ps.pose.position.x = float(d * 2.0)
                ps.pose.position.y = 0.0
                path_msg.poses.append(ps)
        else:
            # Pair cones up by distance
            midpoints = []
            max_pairs = max(len(left_cones), len(right_cones))
            
            for i in range(max_pairs):
                lx, ly = left_cones[i] if i < len(left_cones) else (None, None)
                rx, ry = right_cones[i] if i < len(right_cones) else (None, None)
                
                if lx is not None and rx is not None:
                    mx = (lx + rx) / 2.0
                    my = (ly + ry) / 2.0
                    midpoints.append((mx, my))
                elif lx is not None:
                    # Only left cone visible, offset to the right by half track width (approx 3m)
                    midpoints.append((lx, ly - 3.0))
                elif rx is not None:
                    # Only right cone visible, offset to the left
                    midpoints.append((rx, ry + 3.0))
                    
            for mx, my in midpoints:
                ps = PoseStamped()
                ps.pose.position.x = float(mx)
                ps.pose.position.y = float(my)
                path_msg.poses.append(ps)
                
        self.path_pub.publish(path_msg)

def main(args=None):
    rclpy.init(args=args)
    node = ReactiveMidlineNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

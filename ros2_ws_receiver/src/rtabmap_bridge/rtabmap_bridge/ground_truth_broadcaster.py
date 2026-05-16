#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from tf2_msgs.msg import TFMessage
from geometry_msgs.msg import TransformStamped

class GroundTruthBroadcaster(Node):
    def __init__(self):
        super().__init__('ground_truth_broadcaster')
        
        self.declare_parameter('robot_name', 'ackermann_car')
        self.robot_name = self.get_parameter('robot_name').value
        
        # Subscribe to the ground truth TF coming from Gazebo
        self.subscription = self.create_subscription(
            TFMessage,
            '/ground_truth/tf',
            self.tf_callback,
            10)
            
        # Publisher for the local standard /tf topic
        self.tf_pub = self.create_publisher(TFMessage, '/tf', 10)
        
        self.get_logger().info(f"Ground Truth Broadcaster started. Mapping {self.robot_name} to ground_truth_base_link.")

    def tf_callback(self, msg):
        out_msg = TFMessage()
        for transform in msg.transforms:
            # We are interested in the model pose
            if transform.child_frame_id == self.robot_name or transform.child_frame_id == 'my_robot':
                # Create a new transform anchored to 'world'
                new_transform = TransformStamped()
                new_transform.header = transform.header
                new_transform.header.frame_id = 'world'
                new_transform.child_frame_id = 'ground_truth_base_link'
                new_transform.transform = transform.transform
                
                out_msg.transforms.append(new_transform)
        
        if out_msg.transforms:
            self.tf_pub.publish(out_msg)

def main(args=None):
    rclpy.init(args=args)
    node = GroundTruthBroadcaster()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

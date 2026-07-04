#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Int32
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.msg import Parameter, ParameterValue, ParameterType
from my_gazebo_package.srv import StartRun, ChangeTrack
from ros_gz_interfaces.srv import SetEntityPose
from geometry_msgs.msg import Pose
import json

class TestOrchestratorNode(Node):
    def __init__(self):
        super().__init__('test_orchestrator_node')
        
        # Clients
        self.track_client = self.create_client(ChangeTrack, '/change_track')
        # In gz harmonic, the service to set pose is often /world/default/set_pose
        self.pose_client = self.create_client(SetEntityPose, '/world/default/set_pose')
        
        self.pp_param_client = self.create_client(SetParameters, '/pure_pursuit_node/set_parameters')
        
        # Services
        self.create_service(StartRun, '/orchestrator/start_run', self.start_run_cb)
        
        # Subscriptions
        self.create_subscription(String, '/racing/failure', self.failure_cb, 10)
        
        self.get_logger().info("Test Orchestrator Node started. Waiting for /orchestrator/start_run calls.")

    def set_pp_params(self, speed, lookahead):
        req = SetParameters.Request()
        
        p_speed = Parameter()
        p_speed.name = "target_speed"
        p_speed.value.type = ParameterType.PARAMETER_DOUBLE
        p_speed.value.double_value = float(speed)
        
        p_look = Parameter()
        p_look.name = "lookahead_distance"
        p_look.value.type = ParameterType.PARAMETER_DOUBLE
        p_look.value.double_value = float(lookahead)
        
        req.parameters = [p_speed, p_look]
        self.pp_param_client.call_async(req)

    def set_car_pose(self, spawn_dict):
        # We need to know spawn_dict from track generator, but wait, track generator doesn't return spawn pose via service
        # Alternatively, we could just reset to origin and let the car find its way, or we update ChangeTrack.srv to return spawn pose.
        # For Phase 1 prototype, we will just reset to 0,0,0
        req = SetEntityPose.Request()
        req.entity.name = "my_robot"
        req.pose.position.x = float(0.0)
        req.pose.position.y = float(0.0)
        req.pose.position.z = float(0.5)
        # We would set orientation here based on yaw
        self.pose_client.call_async(req)

    async def start_run_cb(self, request, response):
        self.get_logger().info(f"Starting run: Track={request.track_name}, Speed={request.target_speed}, Lookahead={request.lookahead}")
        
        # 1. Change track
        if self.track_client.wait_for_service(timeout_sec=2.0):
            req = ChangeTrack.Request()
            req.track_name = request.track_name
            await self.track_client.call_async(req)
        
        # 2. Update params
        if self.pp_param_client.wait_for_service(timeout_sec=2.0):
            self.set_pp_params(request.target_speed, request.lookahead)
            
        # 3. Reset car pose
        if self.pose_client.wait_for_service(timeout_sec=2.0):
            self.set_car_pose(None)
            
        # Restart status will be handled by Validator / Telemetry implicitly when new data flows
        response.success = True
        response.message = "Run started successfully"
        return response

    def failure_cb(self, msg):
        self.get_logger().warn(f"Orchestrator received failure: {msg.data}")

def main(args=None):
    rclpy.init(args=args)
    node = TestOrchestratorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

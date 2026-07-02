#!/usr/bin/env python3.12

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy, QoSDurabilityPolicy
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup

from ros_gz_interfaces.srv import SpawnEntity, DeleteEntity
from ros_gz_interfaces.msg import Entity
from geometry_msgs.msg import Pose
from visualization_msgs.msg import Marker, MarkerArray

from my_gazebo_package.srv import ChangeTrack
from my_gazebo_package_py.track_layouts import TRACK_LAYOUTS, CONE_MODEL_URI
from my_gazebo_package_py.track_builder import generate_random_track, calculate_boundaries

class TrackGenerator(Node):

    def __init__(self):
        super().__init__('track_generator')
        self.get_logger().info('Track Generator Node has been started.')

        self.callback_group = ReentrantCallbackGroup()

        self.declare_parameter('initial_track', 'random')
        self.initial_track = self.get_parameter('initial_track').get_parameter_value().string_value

        self.spawn_client = self.create_client(SpawnEntity, '/world/default/create', callback_group=self.callback_group)
        self.delete_client = self.create_client(DeleteEntity, '/world/default/remove', callback_group=self.callback_group)

        self.track_change_service = self.create_service(ChangeTrack, 'change_track', self.change_track_callback, callback_group=self.callback_group)

        latched_qos = QoSProfile(
            depth=1,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST
        )
        self.gt_cone_pub = self.create_publisher(MarkerArray, '/ground_truth/cones', latched_qos)

        self.spawned_cone_names = []

        # Use a timer to trigger initial spawn once executor starts spinning
        self.initial_spawn_timer = self.create_timer(1.0, self.initial_spawn_callback, callback_group=self.callback_group)

    async def initial_spawn_callback(self):
        # Stop timer (one-shot)
        self.initial_spawn_timer.cancel()
        
        # Wait for services with timeout
        self.get_logger().info('Waiting for spawn service...')
        if not self.spawn_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error(f'Spawn service {self.spawn_client.srv_name} not available!')
            return
        
        self.get_logger().info('Waiting for delete service...')
        if not self.delete_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error(f'Delete service {self.delete_client.srv_name} not available!')
            return

        # Spawn initial track
        self.get_logger().info(f'Spawning initial track: {self.initial_track}')
        await self.spawn_track(self.initial_track)

    async def delete_entity_request(self, entity_name):
        request = DeleteEntity.Request()
        entity = Entity()
        entity.name = entity_name
        request.entity = entity
        
        self.get_logger().debug(f'Requesting deletion of: {entity_name}')
        future = self.delete_client.call_async(request)
        try:
            result = await future
            if result.success:
                self.get_logger().debug(f'Deleted entity: {entity_name}')
                return True
            else:
                self.get_logger().warn(f'Failed to delete entity: {entity_name}')
                return False
        except Exception as e:
            self.get_logger().error(f'Service call failed: {e}')
            return False

    async def delete_all_spawned_cones(self):
        # Delete cones one by one
        cone_names = list(self.spawned_cone_names)
        for cone_name in cone_names:
            if await self.delete_entity_request(cone_name):
                if cone_name in self.spawned_cone_names:
                    self.spawned_cone_names.remove(cone_name)

    async def spawn_entity_request(self, entity_name, x, y, z=0.0):
        request = SpawnEntity.Request()
        request.entity_factory.name = entity_name
        request.entity_factory.sdf = f"""
            <sdf version="1.8">
                <model name='{entity_name}'>
                    <link name='link'>
                        <collision name='collision'>
                            <geometry>
                                <cylinder>
                                    <radius>0.2</radius>
                                    <length>0.5</length>
                                </cylinder>
                            </geometry>
                        </collision>
                        <visual name='visual'>
                            <geometry>
                                <mesh>
                                    <scale>10 10 10</scale>
                                    <uri>https://fuel.gazebosim.org/1.0/openrobotics/models/construction cone/3/files/meshes/construction_cone.dae</uri>
                                </mesh>
                            </geometry>
                        </visual>
                    </link>
                </model>
            </sdf>
        """
        request.entity_factory.pose.position.x = float(x)
        request.entity_factory.pose.position.y = float(y)
        request.entity_factory.pose.position.z = float(z)
        
        future = self.spawn_client.call_async(request)
        try:
            result = await future
            if result.success:
                self.get_logger().debug(f'Spawned entity: {entity_name}')
                return True
            else:
                self.get_logger().error(f'Failed to spawn entity: {entity_name}')
                return False
        except Exception as e:
            self.get_logger().error(f'Service call failed: {e}')
            return False

    async def spawn_track(self, track_name):
        if track_name == 'random':
            inner_cones, outer_cones = generate_random_track()
        elif track_name in TRACK_LAYOUTS:
            path = TRACK_LAYOUTS[track_name]
            inner_cones, outer_cones = calculate_boundaries(path)
        else:
            self.get_logger().error(f'Unknown track layout: {track_name}')
            return False

        # Spawn inner cones
        for i, (x, y) in enumerate(inner_cones):
            cone_name = f'inner_cone_{i}'
            if await self.spawn_entity_request(cone_name, x, y):
                self.spawned_cone_names.append(cone_name)

        # Spawn outer cones
        for i, (x, y) in enumerate(outer_cones):
            cone_name = f'outer_cone_{i}'
            if await self.spawn_entity_request(cone_name, x, y):
                self.spawned_cone_names.append(cone_name)
                
        # Publish Ground Truth Cone Markers
        self.publish_gt_markers(inner_cones, outer_cones)

        self.get_logger().info(f'Spawned {len(inner_cones) + len(outer_cones)} cones for track {track_name}')
        return True

    def publish_gt_markers(self, inner_cones, outer_cones):
        marker_array = MarkerArray()
        
        all_cones = inner_cones + outer_cones
        for i, (x, y) in enumerate(all_cones):
            marker = Marker()
            marker.header.frame_id = 'world'
            marker.header.stamp = self.get_clock().now().to_msg()
            marker.ns = 'gt_cones'
            marker.id = i
            marker.type = Marker.CYLINDER
            marker.action = Marker.ADD
            marker.pose.position.x = float(x)
            marker.pose.position.y = float(y)
            marker.pose.position.z = 0.25
            marker.scale.x = 0.4
            marker.scale.y = 0.4
            marker.scale.z = 0.5
            marker.color.a = 1.0
            marker.color.r = 1.0
            marker.color.g = 0.5
            marker.color.b = 0.0
            marker_array.markers.append(marker)
            
        self.gt_cone_pub.publish(marker_array)

    async def change_track_callback(self, request, response):
        self.get_logger().info(f'Received request to change track to: {request.track_name}')

        # Delete all currently spawned cones
        await self.delete_all_spawned_cones()
        
        # Clear GT markers
        delete_array = MarkerArray()
        delete_marker = Marker()
        delete_marker.action = Marker.DELETEALL
        delete_array.markers.append(delete_marker)
        self.gt_cone_pub.publish(delete_array)

        # Spawn new track
        if await self.spawn_track(request.track_name):
            response.success = True
            self.get_logger().info(f'Successfully changed track to: {request.track_name}')
        else:
            response.success = False
            self.get_logger().error(f'Failed to change track to: {request.track_name}')
        return response


def main(args=None):
    rclpy.init(args=args)
    track_generator = TrackGenerator()
    executor = MultiThreadedExecutor()
    executor.add_node(track_generator)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        track_generator.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node, ComposableNodeContainer
from launch_ros.descriptions import ComposableNode
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration

from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PythonExpression

def generate_launch_description():
    pkg_share = get_package_share_directory('rtabmap_bridge')
    
    # Launch Arguments
    use_sim_time_arg = DeclareLaunchArgument('use_sim_time', default_value='true')
    network_interface_arg = DeclareLaunchArgument('network_interface', default_value='', description='Network interface to use for CycloneDDS (e.g., eth0, wlan0)')

    def launch_setup(context, *args, **kwargs):
        # Evaluate launch configurations to raw strings
        use_sim_time_str = context.launch_configurations.get('use_sim_time', 'true').lower()
        use_sim_time = (use_sim_time_str == 'true')
        
        # Dynamically resolve model path to support different user environments (e.g., host k-dev vs edge opi)
        home_dir = os.path.expanduser('~')
        model_paths = [
            os.path.join(home_dir, 'dev/ros2_gazebo/yolo11n_416_qat_int8_fp16out.rknn'),
            os.path.join(home_dir, 'dev/autonomous-gazebo-ros/yolo11n_416_qat_int8_fp16out.rknn')
        ]
        resolved_model_path = model_paths[0]
        for path in model_paths:
            if os.path.exists(path):
                resolved_model_path = path
                break
        
        iface = context.launch_configurations.get('network_interface', '')
        
        if iface:
            print(f"[INFO] [rtabmap_slam.launch.py]: Forcing CycloneDDS to interface: {iface} with Peer: 10.10.12.10")
            uri = f'''<CycloneDDS xmlns="https://cdds.io/config">
                <Domain id="any">
                    <General>
                        <MaxMessageSize>12MB</MaxMessageSize>
                        <FragmentSize>1344B</FragmentSize>
                        <AllowMulticast>true</AllowMulticast>
                    </General>
                    <Internal>
                        <SocketReceiveBufferSize min="50MB"/>
                        <SocketSendBufferSize min="50MB"/>
                    </Internal>
                    <Discovery><Peers><Peer address="10.10.12.10"/></Peers></Discovery>
                </Domain>
            </CycloneDDS>'''
        else:
            print("[INFO] [rtabmap_slam.launch.py]: CycloneDDS using default auto-detection with Peer: 10.10.12.10")
            uri = '''<CycloneDDS xmlns="https://cdds.io/config">
                <Domain id="any">
                    <General>
                        <MaxMessageSize>12MB</MaxMessageSize>
                        <FragmentSize>1344B</FragmentSize>
                        <AllowMulticast>true</AllowMulticast>
                    </General>
                    <Internal>
                        <SocketReceiveBufferSize min="50MB"/>
                        <SocketSendBufferSize min="50MB"/>
                    </Internal>
                    <Discovery><Peers><Peer address="10.10.12.10"/></Peers></Discovery>
                </Domain>
            </CycloneDDS>'''
        
        # Define Nodes inside the OpaqueFunction so they pick up the env
        
        # 1. FFmpeg Image Transport Decoder & Unpacker
        decoder_node = ComposableNode(
            package='sim_camera_decoder',
            plugin='SimCameraDecoder',
            name='ffmpeg_decoder',
            parameters=[{'use_sim_time': use_sim_time}],
            extra_arguments=[{'use_intra_process_comms': True}]
        )

        # 3. Foxglove Bridge (Quiet and Robust Configuration)
        foxglove_bridge = Node(
            package='foxglove_bridge',
            executable='foxglove_bridge',
            name='foxglove_bridge',
            parameters=[{
                'use_sim_time': use_sim_time,
                'port': 8765,
                'address': '0.0.0.0',
                # Block all services with a non-matching regex to prevent type-inference crashes in ROS 2 Jazzy
                'service_whitelist': ['(?!)'], 
                'capabilities': ["clientPublish", "parameters", "parametersSubscribe", "connectionGraph", "assets"],
                'include_hidden': False,
                'topic_whitelist': [
                    '^/tf$', '^/tf_static$', 
                    '^/map$', '^/odometry/filtered$',
                    '^/rtabmap/.*', 
                    '^/ground_truth/tf$',
                    '^/edge/camera/rgb/image_raw/compressed$',
                    '^/edge/camera/depth/image_raw/compressed$',
                    '^/yolo/detections$'
                ]
            }],
            output='screen'
        )

        # 4. Ground Truth Broadcaster
        gt_broadcaster = Node(
            package='rtabmap_bridge',
            executable='ground_truth_broadcaster',
            name='gt_broadcaster',
            parameters=[{
                'use_sim_time': use_sim_time,
                'robot_name': 'ackermann_car'
            }],
            output='screen'
        )

        # 5. Static Transforms
        static_tf_world_map = Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='world_to_map_tf',
            arguments=['--x', '0', '--y', '0', '--z', '0', '--yaw', '0', '--pitch', '0', '--roll', '0', '--frame-id', 'world', '--child-frame-id', 'map'],
            parameters=[{'use_sim_time': use_sim_time}]
        )
        
        static_tf_camera = Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='camera_static_tf',
            arguments=['--x', '0.85', '--y', '0', '--z', '0.46', '--yaw', '-1.570796', '--pitch', '0', '--roll', '-1.570796', '--frame-id', 'base_link', '--child-frame-id', 'camera_link_optical'],
            parameters=[{'use_sim_time': use_sim_time}]
        )

        # 6. EKF Node
        ekf_node = Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            output='screen',
            parameters=[os.path.join(pkg_share, 'config', 'ekf.yaml'), {'use_sim_time': use_sim_time}]
        )

        # 7. RTAB-Map SLAM Node
        rtabmap_node = ComposableNode(
            package='rtabmap_slam',
            plugin='rtabmap_slam::CoreWrapper',
            name='rtabmap',
            parameters=[{
                'use_sim_time': use_sim_time,
                'subscribe_depth': True,
                'subscribe_rgb': True,
                'subscribe_landmark_detections': True,
                'qos_image': 2,
                'qos_camera_info': 2,
                'frame_id': 'base_link',
                'map_frame_id': 'map',
                'odom_frame_id': 'odom',
                'publish_tf': True,
                'approx_sync': True,
                'approx_sync_max_interval': 0.1,
                'queue_size': 50,
                'sync_queue_size': 50,
                'Vis/MaxFeatures': '600',
                'Mem/IncrementalMemory': 'true',
                'RGBD/LinearUpdate': '0.1',
                'RGBD/AngularUpdate': '0.1',
                'DbSqlite3/InMemory': 'true',
                'Rtabmap/DetectionRate': '1.0',
                'Grid/FromDepth': 'true',
                'Grid/Sensor': '0',
                'Grid/MaxGroundHeight': '0.2',
                'Grid/MaxGroundAngle': '45',
                'Grid/RangeMax': '5.0',
                'Grid/DepthDecimation': '4',
                'subscribe_scan': False,
                'wait_for_transform': 0.5
            }],
            remappings=[
                ('rgb/image', '/edge/camera/rgb/image_raw'),
                ('depth/image', '/edge/camera/depth/image_raw'),
                ('rgb/camera_info', '/edge/camera/rgb/camera_info'),
                ('depth/camera_info', '/edge/camera/depth/camera_info'),
                ('odom', '/odometry/filtered'),
                ('landmark_detections', '/rtabmap/landmark_detections')
            ],
            extra_arguments=[{'use_intra_process_comms': True}]
        )

        # 8. RGB-D Odometry Node
        rgbd_odometry_node = ComposableNode(
            package='rtabmap_odom',
            plugin='rtabmap_odom::RGBDOdometry',
            name='rgbd_odometry',
            parameters=[{
                'use_sim_time': use_sim_time,
                'frame_id': 'base_link',
                'qos': 2,
                'qos_camera_info': 2,
                'odom_frame_id': 'rtabmap/odom',
                'publish_tf': False,
                'approx_sync': True,
                'approx_sync_max_interval': 0.1,
                'queue_size': 50
            }],
            remappings=[
                ('rgb/image', '/edge/camera/rgb/image_raw'),
                ('depth/image', '/edge/camera/depth/image_raw'),
                ('rgb/camera_info', '/edge/camera/rgb/camera_info'),
                ('depth/camera_info', '/edge/camera/depth/camera_info')
            ],
            extra_arguments=[{'use_intra_process_comms': True}]
        )
        
        vision_container = ComposableNodeContainer(
            name='vision_container',
            namespace='',
            package='rclcpp_components',
            executable='component_container_mt',
            composable_node_descriptions=[
                decoder_node,
                rtabmap_node,
                rgbd_odometry_node
            ],
            output='screen'
        )

        # 9. NPU Detector Node (runs on Orange Pi 5 NPU)
        npu_detector_node = Node(
            package='rtabmap_bridge',
            executable='cone_detector_npu',
            name='cone_detector_npu',
            parameters=[{
                'use_sim_time': use_sim_time,
                'model_path': resolved_model_path,
                'conf_threshold': 0.5,
                'nms_threshold': 0.4
            }],
            output='screen'
        )

        # 10. Cone Landmark Processor Node
        landmark_processor_node = Node(
            package='rtabmap_bridge',
            executable='cone_landmark_processor',
            name='cone_landmark_processor',
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen'
        )

        return [
            SetEnvironmentVariable(name='CYCLONEDDS_URI', value=uri),
            SetEnvironmentVariable(name='RMW_IMPLEMENTATION', value='rmw_cyclonedds_cpp'),
            vision_container,
            foxglove_bridge,
            gt_broadcaster,
            static_tf_world_map,
            static_tf_camera,
            ekf_node,
            npu_detector_node,
            landmark_processor_node
        ]

    return LaunchDescription([
        use_sim_time_arg,
        network_interface_arg,
        OpaqueFunction(function=launch_setup)
    ])

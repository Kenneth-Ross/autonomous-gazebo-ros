import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    pkg_share = get_package_share_directory('rtabmap_bridge')
    
    # Force CycloneDDS to use the specific ethernet port (enP4p65s0)
    force_cyclone_if = SetEnvironmentVariable(
        name='CYCLONEDDS_URI',
        value='<CycloneDDS><Domain><General><NetworkInterfaceAddress>enP4p65s0</NetworkInterfaceAddress></General></Domain></CycloneDDS>'
    )
    
    force_cyclone_rmw = SetEnvironmentVariable(
        name='RMW_IMPLEMENTATION',
        value='rmw_cyclonedds_cpp'
    )

    # Parameters
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    
    # 1. FFmpeg Image Transport Decoder
    # This node decodes the /ffmpeg stream back to a raw Super-Frame (1280x2400)
    decoder_node = Node(
        package='image_transport',
        executable='republish',
        name='ffmpeg_decoder',
        arguments=['ffmpeg', 'raw'],
        remappings=[
            ('in/ffmpeg', '/oakd/super_frame/image_raw/ffmpeg'),
            ('out', '/oakd/super_frame/image_raw')
        ],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )

    # 2. Virtual OAK-D Unpacker Node
    # Slices the Super-Frame into RGB and 16-bit Depth
    unpacker_node = Node(
        package='rtabmap_bridge',
        executable='unpacker_node',
        name='virtual_oakd_unpacker',
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )

    # 3. Foxglove Bridge (Whitelisted for Digital Twin)
    # Allows remote visualization without saturating the CPU/Network
    foxglove_bridge = Node(
        package='foxglove_bridge',
        executable='foxglove_bridge',
        name='foxglove_bridge',
        parameters=[{
            'use_sim_time': use_sim_time,
            'port': 8765,
            'address': '0.0.0.0',
            'topic_whitelist': [
                '^/tf$', '^/tf_static$', 
                '^/map$', '^/odometry/filtered$',
                '^/rtabmap/.*', 
                '^/ground_truth/tf$',
                '^/camera/rgb/image_raw/compressed$' # Optional compressed preview
            ]
        }],
        output='screen'
    )

    # 4. Ground Truth Broadcaster (Digital Twin)
    # Maps Gazebo model pose to 'ground_truth_base_link' anchored at 'world'
    gt_broadcaster = Node(
        package='rtabmap_bridge',
        executable='ground_truth_broadcaster',
        name='gt_broadcaster',
        parameters=[{
            'use_sim_time': use_sim_time,
            'robot_name': 'my_robot'
        }],
        output='screen'
    )

    # 5. Static Transforms
    # world -> map (anchors SLAM to GT origin)
    # base_link -> camera_link_optical (physical mounting)
    static_tf_world_map = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='world_to_map_tf',
        arguments=['0', '0', '0', '0', '0', '0', 'world', 'map'],
        parameters=[{'use_sim_time': use_sim_time}]
    )

    static_tf_camera = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='camera_static_tf',
        arguments=['0.85', '0', '0.46', '-1.570796', '0', '-1.570796', 'base_link', 'camera_link_optical'],
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # 6. EKF Node

    # Fuses Wheel Odom, IMU, and Visual Odom
    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        parameters=[os.path.join(pkg_share, 'config', 'ekf.yaml'), {'use_sim_time': use_sim_time}]
    )

    # 5. RTAB-Map Node
    rtabmap_node = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        name='rtabmap',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'subscribe_depth': True,
            'subscribe_rgb': True,
            'frame_id': 'base_link',
            'map_frame_id': 'map',
            'odom_frame_id': 'odom',
            'publish_tf': True,
            'approx_sync': True,
            'queue_size': 30,
            'Vis/MaxFeatures': '600',
            'Mem/IncrementalMemory': 'true',
            'RGBD/LinearUpdate': '0.1',
            'RGBD/AngularUpdate': '0.1',
            'DbSqlite3/InMemory': 'true',
            'Rtabmap/DetectionRate': '1.0'
        }],
        remappings=[
            ('rgb/image', '/camera/rgb/image_raw'),
            ('depth/image', '/camera/depth/image_raw'),
            ('rgb/camera_info', '/camera/rgb/camera_info'),
            ('depth/camera_info', '/camera/depth/camera_info'),
            ('odom', '/odometry/filtered')
        ],
        arguments=['-d']
    )

    # 6. RGB-D Odometry Node
    rgbd_odometry_node = Node(
        package='rtabmap_odom',
        executable='rgbd_odometry',
        name='rgbd_odometry',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'frame_id': 'base_link',
            'odom_frame_id': 'rtabmap/odom',
            'publish_tf': False, # EKF will publish odom -> base_link
            'approx_sync': True
        }],
        remappings=[
            ('rgb/image', '/camera/rgb/image_raw'),
            ('depth/image', '/camera/depth/image_raw'),
            ('rgb/camera_info', '/camera/rgb/camera_info'),
            ('depth/camera_info', '/camera/depth/camera_info')
        ]
    )

    return LaunchDescription([
        force_cyclone_if,
        force_cyclone_rmw,
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        decoder_node,
        unpacker_node,
        foxglove_bridge,
        gt_broadcaster,
        static_tf_world_map,
        static_tf_camera,
        ekf_node,
        rtabmap_node,
        rgbd_odometry_node
    ])

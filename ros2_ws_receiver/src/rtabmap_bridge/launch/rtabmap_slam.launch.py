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
    
    # EKF Node
    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        parameters=[os.path.join(pkg_share, 'config', 'ekf.yaml'), {'use_sim_time': use_sim_time}]
    )

    # RTAB-Map Bridge Node
    bridge_node = Node(
        package='rtabmap_bridge',
        executable='bridge_node',
        name='rtabmap_bridge',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'port': 5000
        }]
    )

    # RTAB-Map Node
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
        arguments=['-d'] # Delete database on start for clean slate
    )

    # RGB-D Odometry Node (if not using EKF as primary)
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
        ekf_node,
        bridge_node,
        rtabmap_node,
        rgbd_odometry_node
    ])

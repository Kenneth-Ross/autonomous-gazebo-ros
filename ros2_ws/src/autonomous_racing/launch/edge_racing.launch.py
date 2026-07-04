import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
def generate_launch_description():
    target_speed_arg = DeclareLaunchArgument(
        'target_speed',
        default_value='2.0',
        description='Target racing speed in m/s'
    )
    
    lookahead_arg = DeclareLaunchArgument(
        'lookahead',
        default_value='3.0',
        description='Pure pursuit lookahead distance'
    )

    return LaunchDescription([
        target_speed_arg,
        lookahead_arg,
        
        # 0. Perception Stack (RTAB-Map, YOLO, Foxglove, etc.)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory('rtabmap_bridge'), 'launch', 'rtabmap_slam.launch.py')
            )
        ),
        

        # 1. Reactive Midline Node (Exploration Path Planning)
        # Listens to /rtabmap/landmarks (or equivalent cone topic) and publishes /racing/local_path
        Node(
            package='autonomous_racing',
            executable='reactive_midline_node',
            name='reactive_midline_node',
            output='screen'
        ),
        
        # 2. Pure Pursuit Node (Path Tracking Control)
        # Listens to /racing/local_path and /odom, publishes /car/control_request
        Node(
            package='autonomous_racing',
            executable='pure_pursuit_node',
            name='pure_pursuit_node',
            output='screen',
            parameters=[{
                'target_speed': LaunchConfiguration('target_speed'),
                'lookahead_distance': LaunchConfiguration('lookahead')
            }]
        )
    ])

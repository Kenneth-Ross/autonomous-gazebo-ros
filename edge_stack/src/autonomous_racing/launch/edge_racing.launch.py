import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    target_speed_arg = DeclareLaunchArgument(
        'target_speed', default_value='2.0',
        description='Exploration speed cap in m/s')
    lookahead_arg = DeclareLaunchArgument(
        'lookahead', default_value='3.0',
        description='Pure pursuit lookahead distance')
    rtabmap_launch = os.path.join(
        get_package_share_directory('rtabmap_bridge'), 'launch',
        'rtabmap_slam.launch.py')
    return LaunchDescription([
        target_speed_arg,
        lookahead_arg,
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(rtabmap_launch)),
        Node(
            package='autonomous_racing_core',
            executable='cone_map_adapter_node',
            name='cone_map_adapter',
            output='screen'),
        Node(
            package='autonomous_racing_core',
            executable='racing_planner_node',
            name='racing_planner',
            output='screen',
            parameters=[{
                'exploration_speed': LaunchConfiguration('target_speed'),
            }]),
        Node(
            package='autonomous_racing_core',
            executable='racing_controller_node',
            name='racing_controller',
            output='screen',
            parameters=[{
                'lookahead_distance': LaunchConfiguration('lookahead'),
            }]),
        Node(
            package='autonomous_racing_core',
            executable='racing_supervisor_node',
            name='racing_supervisor',
            output='screen',
            parameters=[{'require_recorder_heartbeat': True}]),
    ])

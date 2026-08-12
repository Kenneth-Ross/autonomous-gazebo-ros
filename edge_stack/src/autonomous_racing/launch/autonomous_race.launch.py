import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.actions import TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    my_gazebo_share = get_package_share_directory('my_gazebo_package')
    sender_share = get_package_share_directory('gazebo_oakd_stream_sender')
    initial_track = DeclareLaunchArgument(
        'initial_track', default_value='catalunya',
        description='Initial SVG-derived Catalunya vector track')
    target_speed = DeclareLaunchArgument(
        'target_speed', default_value='2.0',
        description='Exploration speed cap in m/s')
    lookahead = DeclareLaunchArgument(
        'lookahead', default_value='3.0',
        description='Pure pursuit lookahead distance')
    run_edge = DeclareLaunchArgument(
        'run_edge', default_value='false',
        description='Enable simulation-to-edge camera stream')
    artifact_root = DeclareLaunchArgument(
        'artifact_root', default_value='telemetry',
        description='Root directory for server MCAP run artifacts')
    enable_camera_bridges = DeclareLaunchArgument(
        'enable_camera_bridges', default_value='true',
        description='Bridge Gazebo camera images into ROS topics')
    enable_sensor_bridges = DeclareLaunchArgument(
        'enable_sensor_bridges', default_value='true',
        description='Bridge Gazebo vehicle sensors and control topics into ROS')
    enable_autonomy_nodes = DeclareLaunchArgument(
        'enable_autonomy_nodes', default_value='true',
        description='Launch planner, controller, adapter, validator, and driver')
    return LaunchDescription([
        initial_track,
        target_speed,
        lookahead,
        run_edge,
        artifact_root,
        enable_camera_bridges,
        enable_sensor_bridges,
        enable_autonomy_nodes,
        Node(
            package='my_gazebo_package',
            executable='run_recorder_node.py',
            name='racing_run_recorder',
            output='screen',
            parameters=[{'artifact_root': LaunchConfiguration('artifact_root')}]),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(my_gazebo_share, 'launch', 'gazebo.launch.py')),
            launch_arguments={
                'initial_track': LaunchConfiguration('initial_track'),
                'enable_camera_bridges': LaunchConfiguration(
                    'enable_camera_bridges'),
                'enable_sensor_bridges': LaunchConfiguration(
                    'enable_sensor_bridges')}.items()),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(sender_share, 'launch',
                             'stream_to_remote.launch.py')),
            condition=IfCondition(LaunchConfiguration('run_edge'))),
        Node(
            package='my_gazebo_package',
            executable='driving_model_node.py',
            name='driving_model',
            output='screen',
            parameters=[{'auto_drive': True}],
            condition=IfCondition(LaunchConfiguration('enable_autonomy_nodes'))),
        Node(
            package='autonomous_racing_core',
            executable='cone_map_adapter_node',
            name='cone_map_adapter',
            output='screen',
            condition=IfCondition(LaunchConfiguration('enable_autonomy_nodes'))),
        Node(
            package='autonomous_racing_core',
            executable='racing_planner_node',
            name='racing_planner',
            output='screen',
            parameters=[{
                'exploration_speed': LaunchConfiguration('target_speed'),
            }],
            condition=IfCondition(LaunchConfiguration('enable_autonomy_nodes'))),
        Node(
            package='autonomous_racing_core',
            executable='racing_controller_node',
            name='racing_controller',
            output='screen',
            parameters=[{
                'lookahead_distance': LaunchConfiguration('lookahead'),
            }],
            condition=IfCondition(LaunchConfiguration('enable_autonomy_nodes'))),
        # Let core graph discovery settle before exposing supervisor services.
        TimerAction(period=5.0, actions=[Node(
            package='autonomous_racing_core',
            executable='racing_supervisor_node',
            name='racing_supervisor',
            output='screen',
            # Keep lifecycle RPCs on Fast DDS; high-rate Gazebo sensor traffic
            # remains on Cyclone DDS and cannot starve control-plane replies.
            additional_env={'RMW_IMPLEMENTATION': 'rmw_fastrtps_cpp'},
            parameters=[{'require_recorder_heartbeat': True}])]),
        Node(
            package='autonomous_racing',
            executable='race_validator_node',
            name='race_validator_node',
            output='screen',
            condition=IfCondition(LaunchConfiguration('enable_autonomy_nodes'))),
    ])

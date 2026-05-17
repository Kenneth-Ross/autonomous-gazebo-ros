import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    pkg_share = get_package_share_directory('edge_nav2')
    
    # Parameters
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    params_file = LaunchConfiguration('params_file', default=os.path.join(pkg_share, 'config', 'nav2_params.yaml'))

    # Nodes to launch
    nav2_nodes = [
        'controller_server',
        'planner_server',
        'recoveries_server',
        'bt_navigator',
        'waypoint_follower'
    ]

    # Lifecycle Manager
    lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_navigation',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'autostart': True,
            'node_names': nav2_nodes
        }]
    )

    # Planner Server
    planner_server = Node(
        package='nav2_planner',
        executable='planner_server',
        name='planner_server',
        output='screen',
        parameters=[params_file],
        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')]
    )

    # Controller Server (Remapped to /nav_cmd_vel)
    controller_server = Node(
        package='nav2_controller',
        executable='controller_server',
        output='screen',
        parameters=[params_file],
        remappings=[
            ('/tf', 'tf'), 
            ('/tf_static', 'tf_static'),
            ('cmd_vel', '/nav_cmd_vel')
        ]
    )

    # Recoveries Server
    recoveries_server = Node(
        package='nav2_recoveries',
        executable='recoveries_server',
        name='recoveries_server',
        output='screen',
        parameters=[params_file],
        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')]
    )

    # BT Navigator
    bt_navigator = Node(
        package='nav2_bt_navigator',
        executable='bt_navigator',
        name='bt_navigator',
        output='screen',
        parameters=[params_file],
        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')]
    )

    # Waypoint Follower
    waypoint_follower = Node(
        package='nav2_waypoint_follower',
        executable='waypoint_follower',
        name='waypoint_follower',
        output='screen',
        parameters=[params_file],
        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')]
    )

    # Custom Ackermann Bridge
    ackermann_bridge = Node(
        package='edge_nav2',
        executable='nav2_ackermann_bridge',
        name='nav2_ackermann_bridge',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'wheelbase': 1.511,
            'max_steering_angle': 0.6108
        }]
    )

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('params_file', default_value=os.path.join(pkg_share, 'config', 'nav2_params.yaml')),
        
        lifecycle_manager,
        planner_server,
        controller_server,
        recoveries_server,
        bt_navigator,
        waypoint_follower,
        ackermann_bridge
    ])

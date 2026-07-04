import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.conditions import UnlessCondition

def generate_launch_description():
    my_gazebo_pkg_share = get_package_share_directory('my_gazebo_package')
    gazebo_launch = os.path.join(my_gazebo_pkg_share, 'launch', 'gazebo.launch.py')
    
    # We can pass initial_track argument down to gazebo.launch.py
    initial_track_arg = DeclareLaunchArgument(
        'initial_track',
        default_value='random',
        description='Initial track layout'
    )
    
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
    
    run_edge_arg = DeclareLaunchArgument(
        'run_edge',
        default_value='false',
        description='Set to true if running pure pursuit and midline on Orange Pi'
    )

    return LaunchDescription([
        initial_track_arg,
        target_speed_arg,
        lookahead_arg,
        run_edge_arg,
        
        # Base simulation (Gazebo, car URDF, bridges, track_generator)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(gazebo_launch),
            launch_arguments={'initial_track': LaunchConfiguration('initial_track')}.items(),
        ),
        
        # Driving Model (PID control on velocity)
        Node(
            package='my_gazebo_package',
            executable='driving_model_node.py',
            name='driving_model',
            output='screen',
            parameters=[{'auto_drive': True}]
        ),
        
        # Phase 1 Autonomous Racing Nodes
        Node(
            package='autonomous_racing',
            executable='pure_pursuit_node',
            name='pure_pursuit_node',
            output='screen',
            condition=UnlessCondition(LaunchConfiguration('run_edge')),
            parameters=[{
                'target_speed': LaunchConfiguration('target_speed'),
                'lookahead_distance': LaunchConfiguration('lookahead')
            }]
        ),
        
        Node(
            package='autonomous_racing',
            executable='race_validator_node',
            name='race_validator_node',
            output='screen'
        ),
        
        Node(
            package='autonomous_racing',
            executable='telemetry_recorder_node',
            name='telemetry_recorder_node',
            output='screen'
        ),
        
        Node(
            package='autonomous_racing',
            executable='reactive_midline_node',
            name='reactive_midline_node',
            condition=UnlessCondition(LaunchConfiguration('run_edge')),
            output='screen'
        ),
        
        Node(
            package='autonomous_racing',
            executable='test_orchestrator_node',
            name='test_orchestrator_node',
            output='screen'
        )
    ])

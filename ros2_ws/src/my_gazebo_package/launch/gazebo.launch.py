import os
import xacro

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.actions import ExecuteProcess
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PythonExpression


def generate_launch_description():
    # CycloneDDS Config for internal communication
    pkg_sender_share = get_package_share_directory('gazebo_oakd_stream_sender')
    cyclonedds_config = os.path.join(pkg_sender_share, 'config', 'cyclonedds.xml')

    # Set Gazebo resource path
    gz_resource_path = os.path.join(
        get_package_share_directory('my_gazebo_package'), 'models')

    # Get the path to the Gazebo ROS launch file
    gz_sim_launch_file = os.path.join(
        get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')

    # Get the path to the world file
    world_file = os.path.join(
        get_package_share_directory('my_gazebo_package'), 'worlds', 'world.sdf')

    # Get the path to the robot URDF file
    urdf_file = os.path.join(
        get_package_share_directory('my_gazebo_package'), 'models', 'car.urdf.xacro')

    # Process the URDF file
    robot_description = xacro.process_file(urdf_file).toxml()

    # Declare launch arguments
    declare_initial_track_arg = DeclareLaunchArgument(
        'initial_track',
        default_value='random',
        description='Initial track layout to spawn (oval, figure_eight, hairpin, slalom, rectangle, random)'
    )

    declare_headless_arg = DeclareLaunchArgument(
        'headless',
        default_value='false',
        description='Run Gazebo in server-only mode (headless)'
    )

    initial_track = LaunchConfiguration('initial_track')
    headless = LaunchConfiguration('headless')

    # Gazebo args logic: -r for GUI, -s for Server-only
    gz_args = PythonExpression([
        "'-s ' if '", headless, "' == 'true' else '-r '",
        " + '", world_file, "'"
    ])

    return LaunchDescription([
        SetEnvironmentVariable(name='CYCLONEDDS_URI', value=cyclonedds_config),
        SetEnvironmentVariable(name='RMW_IMPLEMENTATION', value='rmw_cyclonedds_cpp'),
        declare_initial_track_arg,
        declare_headless_arg,
        SetEnvironmentVariable(name='GZ_SIM_RESOURCE_PATH', value=gz_resource_path),
        # Launch Gazebo
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(gz_sim_launch_file),
            launch_arguments={'gz_args': gz_args}.items(),
        ),

        # Spawn the robot
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_description}]
        ),

        TimerAction(
            period=5.0,
            actions=[
                Node(
                    package='ros_gz_sim',
                    executable='create',
                    name='urdf_spawner',
                    output='screen',
                    arguments=["-topic", "robot_description", "-entity", "my_robot", "-z", "0.5"]
                )
            ]
        ),
        
        # Bridge for clock
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='clock_bridge',
            arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
            output='screen'
        ),

        # Bridge for camera topics (Images and Info)
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='camera_bridge',
            arguments=[
                '/oakd/rgbd_camera/image@sensor_msgs/msg/Image[gz.msgs.Image',
                '/oakd/rgbd_camera/depth_image@sensor_msgs/msg/Image[gz.msgs.Image',
                '/oakd/rgbd_camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo',
            ],
            remappings=[
                ('/oakd/rgbd_camera/image', '/oakd/rgb/image_raw'),
                ('/oakd/rgbd_camera/depth_image', '/oakd/depth/image_raw'),
                ('/oakd/rgbd_camera/camera_info', '/oakd/rgb/camera_info'),
            ],
            output='screen'
        ),

        # Bridge for odom
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='odom_bridge',
            arguments=['/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry'],
            output='screen'
        ),

        # Bridge for IMU
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='imu_bridge',
            arguments=['/imu@sensor_msgs/msg/Imu[gz.msgs.IMU'],
            output='screen'
        ),

        # Bridge for joint_states
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='joint_states_bridge',
            arguments=['/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model'],
            output='screen'
        ),

        # Bridge for cmd_vel
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='cmd_vel_bridge',
            arguments=['/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist'],
            output='screen'
        ),

        # Bridge for spawn/delete services
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='entity_bridge',
            arguments=[
                '/world/default/create@ros_gz_interfaces/srv/SpawnEntity@gz.msgs.EntityFactory@gz.msgs.Boolean',
                '/world/default/remove@ros_gz_interfaces/srv/DeleteEntity@gz.msgs.Entity@gz.msgs.Boolean',
            ],
            output='screen'
        ),

        # Track Generator Node
        TimerAction(
            period=5.0,
            actions=[
                Node(
                    package='my_gazebo_package',
                    executable='track_generator_node.py',
                    name='track_generator',
                    output='screen',
                    parameters=[{'initial_track': initial_track}]
                ),
                Node(
                    package='my_gazebo_package',
                    executable='driving_model_node.py',
                    name='driving_model',
                    output='screen',
                    parameters=[{'auto_drive': False}]
                )
            ]
        )
    ])

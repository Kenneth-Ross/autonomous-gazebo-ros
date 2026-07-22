import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, SetEnvironmentVariable
from launch_ros.actions import ComposableNodeContainer, Node
from launch_ros.descriptions import ComposableNode
from rtabmap_bridge.launch_contract import (
    cyclone_uri, parse_bool, validate_flags, validate_network, validate_npu_model)


def launch_setup(context):
    cfg = context.launch_configurations
    enabled = {name: parse_bool(cfg[name]) for name in (
        'enable_foxglove', 'enable_slam', 'enable_npu', 'enable_landmarks',
        'enable_preview_compression')}
    validate_flags(enabled['enable_slam'], enabled['enable_npu'], enabled['enable_landmarks'])
    validate_npu_model(enabled['enable_npu'], cfg['npu_model_path'])
    interface, local, peer = cfg['network_interface'], cfg['local_address'], cfg['peer_address']
    validate_network(interface, local, peer)
    use_sim_time = parse_bool(cfg['use_sim_time'])
    components = [ComposableNode(
        package='sim_camera_decoder', plugin='SimCameraDecoder', name='camera_decoder',
        parameters=[{'use_sim_time': use_sim_time,
                     'publish_compressed': enabled['enable_preview_compression'],
                     'preview_rate_hz': float(cfg['preview_rate_hz']),
                     'slam_rate_hz': float(cfg['slam_rate_hz']),
                     'pairing_queue_depth': 8,
                     'oakd.rgb.image_raw.ffmpeg.decoder_av_options':
                         cfg['rgb_decoder_av_options']}],
        extra_arguments=[{'use_intra_process_comms': True}])]
    if enabled['enable_slam']:
        common = {'use_sim_time': use_sim_time, 'frame_id': 'base_link',
                  'qos_image': 2, 'qos_camera_info': 1, 'approx_sync': False,
                  'sync_queue_size': 2}
        remaps = [('rgb/image', '/edge/slam/rgb/image_raw'),
                  ('depth/image', '/edge/slam/depth/image_raw'),
                  ('rgb/camera_info', '/edge/slam/rgb/camera_info'),
                  ('depth/camera_info', '/edge/slam/depth/camera_info')]
        components.extend([
            ComposableNode(package='rtabmap_slam', plugin='rtabmap_slam::CoreWrapper',
                           name='rtabmap', namespace='rtabmap', parameters=[dict(common, subscribe_depth=True,
                           subscribe_rgb=True, subscribe_landmarks=enabled['enable_landmarks'],
                           map_frame_id='map', odom_frame_id='odom')], remappings=remaps +
                           [('landmark_detections', '/edge/landmark_detections')],
                           extra_arguments=[{'use_intra_process_comms': True}])])
    actions = [
        SetEnvironmentVariable('CYCLONEDDS_URI', cyclone_uri(interface, local, peer)),
        SetEnvironmentVariable('RMW_IMPLEMENTATION', 'rmw_cyclonedds_cpp'),
        Node(package='rtabmap_bridge', executable='multimedia_preflight', output='screen'),
        ComposableNodeContainer(name='vision_container', namespace='',
            package='rclcpp_components', executable='component_container_mt',
            composable_node_descriptions=components, output='screen')]
    if enabled['enable_foxglove']:
        actions.append(Node(package='foxglove_bridge', executable='foxglove_bridge',
            parameters=[{'port': 8765, 'address': '0.0.0.0',
            'service_whitelist': ['(?!)'], 'topic_whitelist': [
                '^/tf$', '^/tf_static$', '^/map$', '^/rtabmap/.*',
                '^/edge/camera/.*/compressed$', '^/yolo/.*']}], output='screen'))
    if enabled['enable_npu']:
        actions.append(Node(package='rtabmap_bridge', executable='cone_detector_npu',
            parameters=[{'use_sim_time': use_sim_time,
                         'model_path': cfg['npu_model_path']}], output='screen'))
    if enabled['enable_landmarks']:
        actions.append(Node(package='rtabmap_bridge', executable='cone_landmark_processor',
            parameters=[{'use_sim_time': use_sim_time,
                         'candidate_max_range_m': float(cfg['landmark_candidate_max_range_m']),
                         'max_range_m': float(cfg['landmark_max_range_m'])}], output='screen'))
    if enabled['enable_slam']:
        share = get_package_share_directory('rtabmap_bridge')
        actions.extend([
            Node(package='robot_localization', executable='ekf_node', name='ekf_filter_node',
                 parameters=[os.path.join(share, 'config', 'ekf.yaml'),
                             {'use_sim_time': use_sim_time}], output='screen'),
            Node(package='rtabmap_bridge', executable='sensor_covariance_injector',
                 parameters=[{'use_sim_time': use_sim_time}], output='screen')])
    return actions


def generate_launch_description():
    arguments = [DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('network_interface', default_value=''),
        DeclareLaunchArgument('local_address', default_value=''),
        DeclareLaunchArgument('peer_address', default_value='10.10.12.10'),
        DeclareLaunchArgument('preview_rate_hz', default_value='5.0'),
        DeclareLaunchArgument('slam_rate_hz', default_value='10.0'),
        DeclareLaunchArgument('landmark_candidate_max_range_m', default_value='20.0'),
        DeclareLaunchArgument('landmark_max_range_m', default_value='20.0'),
        DeclareLaunchArgument('rgb_decoder_av_options', default_value=''),
        DeclareLaunchArgument('npu_model_path', default_value='')]
    arguments += [DeclareLaunchArgument(name, default_value='false') for name in (
        'enable_foxglove', 'enable_slam', 'enable_npu', 'enable_landmarks',
        'enable_preview_compression')]
    return LaunchDescription(arguments + [OpaqueFunction(function=launch_setup)])

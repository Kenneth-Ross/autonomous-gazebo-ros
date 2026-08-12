from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_pursuit_only_publishes_candidate_topic():
    source = (ROOT / 'autonomous_racing' / 'pure_pursuit_node.py').read_text()
    assert "'/racing/control_candidate'" in source
    assert "'/car/control_request'" not in source


def test_gate_owns_final_command_topic_and_explicit_services():
    source = (ROOT / 'autonomous_racing' / 'command_gate_node.py').read_text()
    assert "'/car/control_request'" in source
    assert "'/racing/prepare'" in source
    assert "'/racing/start'" in source
    assert "'/racing/abort'" in source
    assert "'require_recorder_heartbeat': True" in (
        ROOT / 'launch' / 'autonomous_race.launch.py').read_text()


def test_racing_launches_use_production_core():
    for name in ('edge_racing.launch.py', 'autonomous_race.launch.py'):
        source = (ROOT / 'launch' / name).read_text()
        assert "package='autonomous_racing_core'" in source
        assert "executable='racing_planner_node'" in source
        assert "executable='racing_controller_node'" in source
        assert "executable='racing_supervisor_node'" in source
    core_source = (ROOT.parent / 'autonomous_racing_core' / 'src' /
                   'racing_controller_node.cpp').read_text()
    assert 'odom_timeout' in core_source
    assert 'odometry_stale' in core_source
    adapter_source = (ROOT.parent / 'autonomous_racing_core' / 'src' /
                      'cone_map_adapter_node.cpp').read_text()
    assert 'marker.id < 0' in adapter_source
    assert 'std::isfinite' in adapter_source
    source = (ROOT / 'launch' / 'autonomous_race.launch.py').read_text()
    assert "package='my_gazebo_package'" in source
    assert "executable='run_recorder_node.py'" in source
    assert "'artifact_root'" in source
    assert "'enable_camera_bridges'" in source
    assert "'enable_sensor_bridges'" in source
    assert "additional_env={'RMW_IMPLEMENTATION': 'rmw_fastrtps_cpp'}" in source
    assert 'telemetry_recorder_node' not in source
    assert 'jsonl' not in source


def test_typed_path_and_candidate_contracts():
    pursuit = (ROOT / 'autonomous_racing' / 'pure_pursuit_node.py').read_text()
    midline = (ROOT / 'autonomous_racing' / 'reactive_midline_node.py').read_text()
    gate = (ROOT / 'autonomous_racing' / 'command_gate_node.py').read_text()
    assert 'from autonomous_racing_msgs.msg import ControlCandidate, RacingPath' in pursuit
    assert 'create_subscription(\n            RacingPath' in pursuit
    assert 'from autonomous_racing_msgs.msg import RacingPath, RacingPathPoint' in midline
    assert 'create_publisher(\n            RacingPath' in midline
    assert 'for d in range(1, 6)' not in midline
    assert 'from autonomous_racing_msgs.msg import (' in gate
    assert 'RecorderHeartbeat' in gate
    assert 'SupervisorStatus' in gate
    assert 'from autonomous_racing_msgs.srv import AbortRun, PrepareRun, StartRun' in gate

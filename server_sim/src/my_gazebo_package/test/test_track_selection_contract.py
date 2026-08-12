from pathlib import Path

from my_gazebo_package_py.track_layouts import DEFAULT_TRACK, TRACK_LAYOUTS


PACKAGE = Path(__file__).parents[1]
REPOSITORY = PACKAGE.parents[2]


def test_default_track_is_high_resolution_svg_translation():
    assert DEFAULT_TRACK == 'catalunya'
    track = TRACK_LAYOUTS[DEFAULT_TRACK]
    assert track['source_type'] == 'svg_vector_translation'
    assert len(track['points']) >= 100
    assert track['points'][0] != track['points'][-1]


def test_server_and_autonomous_entry_points_use_default_track():
    generator = (
        PACKAGE / 'my_gazebo_package_py' / 'nodes' /
        'track_generator_node.py'
    ).read_text()
    assert "declare_parameter('initial_track', DEFAULT_TRACK)" in generator

    expected_sources = (
        PACKAGE / 'launch' / 'gazebo.launch.py',
        REPOSITORY / 'scripts' / 'launch_sim.sh',
        REPOSITORY / 'scripts' / 'validation' /
        'autonomous_gazebo_acceptance.sh',
        REPOSITORY / 'edge_stack' / 'src' / 'autonomous_racing' / 'launch' /
        'autonomous_race.launch.py',
    )
    for source in expected_sources:
        assert 'catalunya' in source.read_text(), source


def test_gazebo_sensor_bridge_controls_are_explicit():
    source = (PACKAGE / 'launch' / 'gazebo.launch.py').read_text()
    assert "'enable_camera_bridges'" in source
    assert "'enable_sensor_bridges'" in source
    assert 'condition=IfCondition(enable_camera_bridges)' in source
    assert 'condition=IfCondition(enable_sensor_bridges)' in source

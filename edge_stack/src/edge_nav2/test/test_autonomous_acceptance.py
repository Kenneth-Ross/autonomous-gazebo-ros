import math
from pathlib import Path

from edge_nav2.ackermann_kinematics import bounded_yaw_rate, steering_angle
import pytest
import yaml


PACKAGE_ROOT = Path(__file__).parents[1]


def load_nav2_parameters():
    with (PACKAGE_ROOT / 'config' / 'nav2_params.yaml').open() as stream:
        return yaml.safe_load(stream)


def test_bicycle_model_clamps_to_physical_steering_limit():
    angle = steering_angle(1.0, 0.5, 1.511, 0.1, 0.6108)
    assert math.atan(1.511 * 0.5) > 0.6108
    assert angle == pytest.approx(0.6108)


def test_bicycle_model_preserves_turn_direction_at_low_speed():
    assert steering_angle(-0.05, -0.5, 1.511, 0.1, 0.6108) < 0.0


def test_moving_yaw_rate_respects_physical_steering_limit():
    maximum = 1.0 * math.tan(0.6108) / 1.511
    assert bounded_yaw_rate(1.0, 10.0, 1.511, 0.6108) == pytest.approx(maximum)
    assert bounded_yaw_rate(-1.0, -10.0, 1.511, 0.6108) == pytest.approx(-maximum)


def test_nav2_ackermann_geometry_and_curvature_regulation_contract():
    params = load_nav2_parameters()
    controller = params['controller_server']['ros__parameters']
    follow_path = controller['FollowPath']
    planner = params['planner_server']['ros__parameters']['GridBased']
    assert controller['controller_frequency'] == pytest.approx(20.0)
    assert follow_path['plugin'].endswith('RegulatedPurePursuitController')
    assert follow_path['use_regulated_linear_velocity_scaling'] is True
    assert follow_path['use_rotate_to_heading'] is False
    assert follow_path['allow_reversing'] is False
    assert follow_path['regulated_linear_scaling_min_radius'] == pytest.approx(3.0)
    assert planner['plugin'] == 'nav2_smac_planner::SmacPlannerHybrid'
    assert planner['minimum_turning_radius'] == pytest.approx(1.5)


@pytest.mark.parametrize('costmap_name', ('global_costmap', 'local_costmap'))
def test_costmaps_share_vehicle_footprint_and_inflation(costmap_name):
    params = load_nav2_parameters()
    costmap = params[costmap_name][costmap_name]['ros__parameters']
    footprint = yaml.safe_load(costmap['footprint'])
    xs = [point[0] for point in footprint]
    ys = [point[1] for point in footprint]
    assert max(xs) - min(xs) == pytest.approx(2.02)
    assert max(ys) - min(ys) == pytest.approx(1.26)
    assert costmap['inflation_layer']['inflation_radius'] == pytest.approx(1.35)
    if costmap_name == 'local_costmap':
        assert costmap['width'] >= 8.0
        assert costmap['height'] >= 8.0


def test_jazzy_behavior_server_contract():
    params = load_nav2_parameters()
    behavior = params['behavior_server']['ros__parameters']
    assert behavior['behavior_plugins'] == ['backup', 'wait']
    assert behavior['backup']['plugin'] == 'nav2_behaviors::BackUp'
    assert behavior['wait']['plugin'] == 'nav2_behaviors::Wait'
    assert 'recovery_server' not in params


def test_ackermann_behavior_tree_cannot_spin():
    tree = PACKAGE_ROOT / 'behavior_trees' / 'navigate_to_pose_ackermann.xml'
    contents = tree.read_text()
    assert '<Spin' not in contents
    assert '<BackUp' in contents
    assert '<Wait' in contents

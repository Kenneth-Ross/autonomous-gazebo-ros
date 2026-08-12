from pathlib import Path
import xml.etree.ElementTree as ET

import pytest


MODEL = Path(__file__).parents[1] / 'models' / 'car.urdf.xacro'


def test_ackermann_plugin_matches_physical_axles_and_ecu_limit():
    root = ET.parse(MODEL).getroot()
    joints = {joint.attrib['name']: joint for joint in root.findall('joint')}
    front_x = float(
        joints['front_left_wheel_steering_joint'].find('origin').attrib['xyz']
        .split()[0])
    rear_macro = next(
        element for element in root
        if element.tag.endswith('wheel')
        and element.attrib.get('name') == 'rear_left_wheel')
    rear_x = float(rear_macro.find('origin').attrib['xyz'].split()[0])

    ackermann = next(
        plugin for gazebo in root.findall('gazebo')
        for plugin in gazebo.findall('plugin')
        if plugin.attrib.get('filename') == 'gz-sim-ackermann-steering-system')
    wheelbase = float(ackermann.findtext('wheel_base'))
    steering_limit = float(ackermann.findtext('steering_limit'))
    steering_gain = float(ackermann.findtext('steer_p_gain'))

    assert front_x - rear_x == pytest.approx(1.511421, abs=1e-6)
    assert wheelbase == pytest.approx(1.511)
    assert wheelbase == pytest.approx(front_x - rear_x, abs=0.001)
    assert steering_limit == pytest.approx(0.6108)
    assert steering_gain == pytest.approx(3.0)
    for name in (
        'front_left_wheel_steering_joint',
        'front_right_wheel_steering_joint',
    ):
        limit = joints[name].find('limit').attrib
        assert float(limit['lower']) == pytest.approx(-steering_limit)
        assert float(limit['upper']) == pytest.approx(steering_limit)

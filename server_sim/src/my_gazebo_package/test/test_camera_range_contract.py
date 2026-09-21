from pathlib import Path
import xml.etree.ElementTree as ET


MODEL = Path(__file__).parents[1] / 'models' / 'oakd_camera.urdf.xacro'


def test_rgbd_camera_has_independent_rgb_and_depth_clip_ranges():
    root = ET.parse(MODEL).getroot()
    sensor = root.find(".//sensor[@type='rgbd_camera']")
    assert sensor is not None

    camera = sensor.find('camera')
    assert camera is not None
    assert camera.findtext('clip/near') == '0.02'
    assert camera.findtext('clip/far') == '300.0'
    assert camera.findtext('depth_camera/clip/near') == '0.7'
    assert camera.findtext('depth_camera/clip/far') == '30.0'

    assert sensor.findtext('topic') == '/oakd/rgbd_camera'
    assert sensor.findtext('gz_frame_id') == 'camera_link_optical'
    assert camera.findtext('image/width') == '1280'
    assert camera.findtext('image/height') == '800'

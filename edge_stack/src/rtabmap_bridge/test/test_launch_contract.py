import pytest
from pathlib import Path
from rtabmap_bridge.launch_contract import (
    cyclone_uri, validate_flags, validate_network, validate_npu_model)


def test_invalid_flag_dependencies_are_rejected():
    with pytest.raises(ValueError): validate_flags(False, True, True)
    with pytest.raises(ValueError): validate_flags(True, False, True)
    validate_flags(False, False, False)


def test_dds_interface_address_and_peer_contract():
    inventory = [{'addr_info': [{'local': '10.10.12.11'}]}]
    validate_network('eth0', '10.10.12.11', '10.10.12.10', inventory)
    with pytest.raises(ValueError):
        validate_network('eth0', '10.10.12.99', '10.10.12.10', inventory)
    xml = cyclone_uri('eth0', '10.10.12.11', '10.10.12.10')
    assert 'name="eth0"' in xml and 'address="10.10.12.11"' in xml
    assert '<MaxMessageSize>1472B</MaxMessageSize>' in xml
    assert '<FragmentSize>1344B</FragmentSize>' in xml
    assert '<MaxMessageSize>12MB</MaxMessageSize>' not in xml


def test_launch_exposes_optional_rgb_decoder_options():
    launch = (Path(__file__).parents[1] / 'launch' / 'rtabmap_slam.launch.py').read_text()
    assert "DeclareLaunchArgument('rgb_decoder_av_options', default_value='')" in launch
    assert "'oakd.rgb.image_raw.ffmpeg.decoder_av_options'" in launch


def test_npu_requires_explicit_existing_model():
    with pytest.raises(ValueError):
        validate_npu_model(True, '')
    with pytest.raises(ValueError):
        validate_npu_model(True, '/missing/model.rknn', exists=lambda _: False)
    validate_npu_model(True, '/models/cones.rknn', exists=lambda _: True)
    validate_npu_model(False, '')

def test_slam_uses_sensor_data_qos_for_raw_images():
    launch = (Path(__file__).parents[1] / 'launch' / 'rtabmap_slam.launch.py').read_text()
    assert "'qos_image': 2" in launch
    assert "parameters=[dict(common, qos=2)]" in launch
    assert "'qos_camera_info': 1" in launch
    assert "'sync_queue_size': 2" in launch
    assert "'queue_size': 2" not in launch
    assert "'slam_rate_hz': float(cfg['slam_rate_hz'])" in launch
    assert "('rgb/image', '/edge/slam/rgb/image_raw')" in launch
    assert "('depth/image', '/edge/slam/depth/image_raw')" in launch
    landmark = (Path(__file__).parents[1] / 'rtabmap_bridge' / 'cone_landmark_processor.py').read_text()
    assert "'/edge/perception/depth/image_raw'" in landmark
    assert "'/edge/camera/depth/image_raw'" not in landmark
    assert "'/edge/camera/rgb/image_raw/compressed'" not in landmark
    assert "'/yolo/annotated/compressed'" not in landmark
    assert "ImageAnnotations, '/yolo/image_annotations'" in landmark
    assert "bbox_annotation.type = PointsAnnotation.LINE_LOOP" in landmark
    assert "annotations_msg.timestamp = depth_msg.header.stamp" in landmark
    assert 'text_annotation.text = f"{display_id}: {z_m:.1f}m"' in landmark
    assert "self.annotation_pub.publish(annotations_msg)" in landmark
    assert "self.depth_frames = OrderedDict()" in landmark
    assert "while len(self.depth_frames) > 8" in landmark
    assert "self.depth_frames.pop(self.stamp_key(msg.header), None)" in landmark
    assert "'/edge/landmark_detections'" in landmark
    assert "('landmarks', '/edge/landmark_detections')" in launch

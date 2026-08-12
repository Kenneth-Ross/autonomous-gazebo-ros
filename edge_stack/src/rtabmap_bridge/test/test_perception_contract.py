import numpy as np
import pytest
from rtabmap_bridge.perception_contract import (
    association_threshold,
    bounding_box_edges,
    cone_geometry,
    depth_percentile_meters,
    project_pixel_to_camera,
    retain_bounded_frame,
)


def test_depth_percentile_ignores_zero_and_nonfinite_values():
    roi = np.array([[0, 1000, 3000], [np.nan, 2000, 9000]], dtype=np.float32)
    assert depth_percentile_meters(roi) == pytest.approx(1.75)
    assert depth_percentile_meters(np.zeros((3, 3), dtype=np.uint16)) is None
    assert depth_percentile_meters(np.full((2, 2), np.nan)) is None


def test_cone_geometry_accepts_nominal_and_rejects_false_boxes():
    assert cone_geometry(40, 80, 5.0, 400.0, 400.0) == pytest.approx((0.5, 1.0))
    assert cone_geometry(4, 80, 5.0, 400.0, 400.0) is None
    assert cone_geometry(160, 80, 5.0, 400.0, 400.0) is None
    assert cone_geometry(40, 80, 0.0, 400.0, 400.0) is None


def test_pixel_projection_preserves_optical_frame_convention():
    assert project_pixel_to_camera(450, 250, 4.0, 400.0, 500.0, 400.0, 200.0) == pytest.approx((0.5, 0.4, 4.0))
    with pytest.raises(ValueError):
        project_pixel_to_camera(0, 0, 1.0, 0.0, 400.0, 0.0, 0.0)


def test_association_threshold_is_scaled_and_bounded():
    assert association_threshold(0.0) == pytest.approx(2.5)
    assert association_threshold(10.0) == pytest.approx(3.0)
    assert association_threshold(100.0) == pytest.approx(3.5)
    with pytest.raises(ValueError):
        association_threshold(-1.0)


def test_annotation_box_edges_are_deterministic():
    assert bounding_box_edges(100.0, 80.0, 40.0, 20.0) == pytest.approx((80.0, 70.0, 120.0, 90.0))
    with pytest.raises(ValueError):
        bounding_box_edges(0.0, 0.0, -1.0, 2.0)


def test_depth_queue_is_bounded_and_keeps_newest_frames():
    from collections import OrderedDict

    frames = OrderedDict()
    for stamp in range(10):
        retain_bounded_frame(frames, (stamp, 0), object())
    assert len(frames) == 8
    assert list(frames)[0] == (2, 0)
    assert list(frames)[-1] == (9, 0)
    with pytest.raises(ValueError):
        retain_bounded_frame(frames, (10, 0), object(), limit=0)

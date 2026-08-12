"""Deterministic depth and cone-geometry contract helpers."""

from __future__ import annotations

import math

import numpy as np


def depth_percentile_meters(roi, percentile: float = 25.0):
    """Return robust millimetre-depth ROI percentile in metres, or ``None``."""
    values = np.asarray(roi)
    if values.size == 0:
        return None
    valid = np.isfinite(values) & (values > 0)
    if not np.any(valid):
        return None
    raw = float(np.percentile(values[valid], percentile))
    if not math.isfinite(raw) or raw <= 0:
        return None
    return raw / 1000.0


def cone_geometry(size_x, size_y, depth_m, focal_x, focal_y):
    """Return physical ``(width, height)`` when projected box is cone-like."""
    values = (size_x, size_y, depth_m, focal_x, focal_y)
    if not all(math.isfinite(float(value)) for value in values):
        return None
    if depth_m <= 0 or focal_x <= 0 or focal_y <= 0:
        return None
    physical_width = (size_x * depth_m) / focal_x
    physical_height = (size_y * depth_m) / focal_y
    if not (0.05 < physical_width < 0.8 and 0.1 < physical_height < 1.2):
        return None
    if physical_width > physical_height * 1.5:
        return None
    return physical_width, physical_height


def project_pixel_to_camera(u, v, depth_m, focal_x, focal_y, center_x, center_y):
    """Project one depth pixel into the camera optical frame."""
    values = (u, v, depth_m, focal_x, focal_y, center_x, center_y)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("projection inputs must be finite")
    if depth_m <= 0 or focal_x <= 0 or focal_y <= 0:
        raise ValueError("depth and focal lengths must be positive")
    return (
        ((u - center_x) * depth_m) / focal_x,
        ((v - center_y) * depth_m) / focal_y,
        depth_m,
    )


def association_threshold(depth_m, base: float = 2.5, scale: float = 0.05,
                          maximum: float = 3.5):
    """Return bounded map-space association distance for one observation."""
    if not math.isfinite(float(depth_m)) or depth_m < 0:
        raise ValueError("depth must be finite and non-negative")
    return min(base + scale * depth_m, maximum)


def bounding_box_edges(center_x, center_y, size_x, size_y):
    """Return ``(left, top, right, bottom)`` image coordinates."""
    values = (center_x, center_y, size_x, size_y)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("bounding-box inputs must be finite")
    if size_x < 0 or size_y < 0:
        raise ValueError("bounding-box sizes must be non-negative")
    return (
        float(center_x - size_x / 2.0),
        float(center_y - size_y / 2.0),
        float(center_x + size_x / 2.0),
        float(center_y + size_y / 2.0),
    )


def retain_bounded_frame(frames, key, message, limit: int = 8):
    """Insert newest stamped frame and evict oldest entries over ``limit``."""
    if limit < 1:
        raise ValueError("frame limit must be positive")
    frames[key] = message
    frames.move_to_end(key)
    while len(frames) > limit:
        frames.popitem(last=False)

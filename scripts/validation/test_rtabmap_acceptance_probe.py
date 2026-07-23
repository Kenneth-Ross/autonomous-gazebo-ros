#!/usr/bin/env python3
import unittest

from rtabmap_acceptance_probe import evaluate


RTAB = (
    '[c] [INFO] [{stamp}] [rtabmap.rtabmap]: rtabmap ({node}): '
    'Rate=1.00s, Limit=0.000s, Conversion=0.0020s, RTAB-Map=0.2000s, '
    'Maps update=0.0010s pub=0.0040s delay=0.3000s (local map=4, WM={wm})'
)
CAMERA = (
    '[c] [INFO] [10.0] [camera_decoder]: rgb_received=100 depth_received=100 '
    'pairs_published=100 rgb_rate=30.0 depth_rate=30.0 pair_rate={rate} '
    'unmatched_dropped={drops} queue_size=1 queue_high_water={queue} malformed={malformed} '
    'pair_latency_p95_ms=80.0'
)


def healthy_lines(start=10.0):
    lines = [RTAB.format(stamp=start + i, node=i, wm=20 + i) for i in range(12)]
    lines += [CAMERA.format(rate='30.0', drops=2, queue=3, malformed=0)]
    lines += [
        'Landmark promotion: detections=100 invalid_depth=0 range_rejected=2 '
        'geometry_rejected=1 transform_rejected=0 candidates_created=1 '
        'candidates_matched=2 persistent_matched=90 promoted=1 active_candidates=0 landmarks=40'
    ]
    return lines


class RtabmapAcceptanceProbeTest(unittest.TestCase):
    def test_nominal_passes_healthy_window(self):
        result = evaluate(healthy_lines(), minimum_windows=10)
        self.assertEqual(result['failures'], [])
        self.assertEqual(result['landmarks_final'], 40)

    def test_rejects_stall_queue_growth_and_transform_failures(self):
        lines = healthy_lines()[:]
        lines += [CAMERA.format(rate='12.0', drops=8, queue=20, malformed=1)]
        lines += ['rtabmap: Did not receive data since 5 seconds!']
        lines += ['Landmark promotion: detections=5 invalid_depth=0 range_rejected=0 '
                  'geometry_rejected=0 transform_rejected=5 candidates_created=0 '
                  'candidates_matched=0 persistent_matched=0 promoted=0 '
                  'active_candidates=0 landmarks=40']
        result = evaluate(lines, minimum_windows=10)
        self.assertIn('camera pair rate below 29.0 Hz', result['failures'])
        self.assertIn('camera unmatched drops grew', result['failures'])
        self.assertIn('camera queue high-water exceeded 12', result['failures'])
        self.assertIn('malformed camera frames observed', result['failures'])
        self.assertIn('RTAB-Map input stall observed', result['failures'])
        self.assertIn('landmark transform rejections observed', result['failures'])

    def test_adversarial_recovery_requires_post_fault_health(self):
        result = evaluate(
            healthy_lines(), minimum_windows=10, require_recovery=True,
            recovery_marker_present=False)
        self.assertIn('recovery marker missing', result['failures'])


if __name__ == '__main__':
    unittest.main()

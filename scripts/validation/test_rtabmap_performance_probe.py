#!/usr/bin/env python3
import unittest

from rtabmap_performance_probe import parse_metrics, summarize


class RtabmapPerformanceProbeTest(unittest.TestCase):
    def test_parses_namespaced_metrics_and_computes_effective_rate(self):
        lines = [
            '[component] [INFO] [100.000] [rtabmap.rtabmap]: rtabmap (1): '
            'Rate=1.00s, Limit=0.000s, Conversion=0.1200s, RTAB-Map=0.0800s, '
            'Maps update=0.0100s pub=0.0010s delay=0.2500s (local map=1, WM=2)',
            '[component] [INFO] [101.250] [rtabmap.rtabmap]: rtabmap (2): '
            'Rate=1.00s, Limit=0.000s, Conversion=0.1800s, RTAB-Map=0.1000s, '
            'Maps update=0.0200s pub=0.0020s delay=0.3300s (local map=2, WM=3)',
        ]
        summary = summarize(parse_metrics(lines))
        self.assertEqual(summary['windows'], 2)
        self.assertAlmostEqual(summary['effective_rate_hz'], 0.8)
        self.assertEqual(summary['conversion_max_ms'], 180.0)
        self.assertEqual(summary['working_memory_final'], 3)

    def test_rejects_logs_without_metrics(self):
        with self.assertRaises(ValueError):
            summarize(parse_metrics(['unrelated log line']))


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""Evaluate one bounded RTAB-Map full-stack acceptance window."""

import argparse
import re

from rtabmap_performance_probe import parse_metrics, summarize


FIELD = re.compile(r'([a-z_]+)=([0-9]+(?:\.[0-9]+)?)')


def _fields(line):
    return {key: float(value) for key, value in FIELD.findall(line)}


def evaluate(lines, *, minimum_windows=10, minimum_rate_hz=0.5,
             maximum_conversion_p95_ms=10.0, maximum_delay_p95_ms=500.0,
             require_recovery=False, recovery_marker_present=True):
    lines = list(lines)
    failures = []
    metrics = parse_metrics(lines)
    performance = summarize(metrics) if metrics else {}
    camera = [_fields(line) for line in lines if 'camera_decoder' in line and 'pair_rate=' in line]
    promotions = [_fields(line) for line in lines if 'Landmark promotion:' in line]

    if len(metrics) < minimum_windows:
        failures.append(f'RTAB-Map windows below {minimum_windows}')
    elif performance['effective_rate_hz'] < minimum_rate_hz:
        failures.append(f'RTAB-Map rate below {minimum_rate_hz:.1f} Hz')
    if performance and performance['conversion_p95_ms'] > maximum_conversion_p95_ms:
        failures.append(f'conversion p95 exceeded {maximum_conversion_p95_ms:.1f} ms')
    if performance and performance['delay_p95_ms'] > maximum_delay_p95_ms:
        failures.append(f'delay p95 exceeded {maximum_delay_p95_ms:.1f} ms')

    if not camera:
        failures.append('camera metrics missing')
    else:
        if min(item.get('pair_rate', 0.0) for item in camera) < 29.0:
            failures.append('camera pair rate below 29.0 Hz')
        if camera[-1].get('unmatched_dropped', 0) > camera[0].get('unmatched_dropped', 0):
            failures.append('camera unmatched drops grew')
        if max(item.get('queue_high_water', 0) for item in camera) > 12:
            failures.append('camera queue high-water exceeded 12')
        if camera[-1].get('malformed', 0) > camera[0].get('malformed', 0):
            failures.append('malformed camera frames observed')

    if any('Did not receive data' in line for line in lines):
        failures.append('RTAB-Map input stall observed')
    if any(re.search(r'process has died|retcode -58|\bFATAL\b', line) for line in lines):
        failures.append('fatal process or transport failure observed')
    if promotions and sum(item.get('transform_rejected', 0) for item in promotions) > 0:
        failures.append('landmark transform rejections observed')
    if require_recovery and not recovery_marker_present:
        failures.append('recovery marker missing')

    return {
        **performance,
        'camera_samples': len(camera),
        'landmark_samples': len(promotions),
        'landmarks_final': int(promotions[-1].get('landmarks', 0)) if promotions else 0,
        'failures': failures,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('log')
    parser.add_argument('--minimum-windows', type=int, default=10)
    parser.add_argument('--minimum-rate-hz', type=float, default=0.5)
    parser.add_argument('--maximum-conversion-p95-ms', type=float, default=10.0)
    parser.add_argument('--maximum-delay-p95-ms', type=float, default=500.0)
    parser.add_argument('--require-recovery-marker', action='store_true')
    args = parser.parse_args()
    with open(args.log, encoding='utf-8', errors='replace') as stream:
        lines = list(stream)
    result = evaluate(
        lines,
        minimum_windows=args.minimum_windows,
        minimum_rate_hz=args.minimum_rate_hz,
        maximum_conversion_p95_ms=args.maximum_conversion_p95_ms,
        maximum_delay_p95_ms=args.maximum_delay_p95_ms,
        require_recovery=args.require_recovery_marker,
        recovery_marker_present=any('SLAM_RECOVERY_START' in line for line in lines),
    )
    print(' '.join(
        f'{key}={value:.3f}' if isinstance(value, float) else f'{key}={value}'
        for key, value in result.items() if key != 'failures'))
    if result['failures']:
        raise SystemExit('ERROR: ' + '; '.join(result['failures']))
    print('PASS: RTAB-Map acceptance thresholds met')


if __name__ == '__main__':
    main()

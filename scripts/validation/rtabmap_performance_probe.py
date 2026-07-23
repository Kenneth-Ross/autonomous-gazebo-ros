#!/usr/bin/env python3
"""Summarize RTAB-Map timing metrics emitted by CoreWrapper."""

import argparse
import math
import re


METRIC_PATTERN = re.compile(
    r'\[(?P<stamp>[0-9]+(?:\.[0-9]+)?)\].*rtabmap \([0-9]+\):.*'
    r'Conversion=(?P<conversion>[0-9.]+)s, RTAB-Map=(?P<rtabmap>[0-9.]+)s, '
    r'Maps update=(?P<maps>[0-9.]+)s pub=(?P<publish>[0-9.]+)s '
    r'delay=(?P<delay>[0-9.]+)s .*WM=(?P<working_memory>[0-9]+)\)'
)


def parse_metrics(lines):
    metrics = []
    for line in lines:
        match = METRIC_PATTERN.search(line)
        if match:
            values = match.groupdict()
            metrics.append({
                'stamp': float(values['stamp']),
                'conversion_ms': 1000.0 * float(values['conversion']),
                'rtabmap_ms': 1000.0 * float(values['rtabmap']),
                'maps_ms': 1000.0 * float(values['maps']),
                'publish_ms': 1000.0 * float(values['publish']),
                'delay_ms': 1000.0 * float(values['delay']),
                'working_memory': int(values['working_memory']),
            })
    return metrics


def percentile(values, fraction):
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def summarize(metrics):
    if not metrics:
        raise ValueError('no RTAB-Map timing metrics found')
    duration = metrics[-1]['stamp'] - metrics[0]['stamp']
    effective_rate = (len(metrics) - 1) / duration if duration > 0 else 0.0
    summary = {
        'windows': len(metrics),
        'effective_rate_hz': effective_rate,
        'working_memory_final': metrics[-1]['working_memory'],
    }
    for name in ('conversion', 'rtabmap', 'maps', 'publish', 'delay'):
        values = [metric[f'{name}_ms'] for metric in metrics]
        summary[f'{name}_mean_ms'] = sum(values) / len(values)
        summary[f'{name}_p95_ms'] = percentile(values, 0.95)
        summary[f'{name}_max_ms'] = max(values)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('log')
    parser.add_argument('--minimum-windows', type=int, default=10)
    parser.add_argument('--minimum-rate-hz', type=float)
    parser.add_argument('--maximum-conversion-p95-ms', type=float)
    args = parser.parse_args()

    with open(args.log, encoding='utf-8', errors='replace') as stream:
        summary = summarize(parse_metrics(stream))

    print(' '.join(
        f'{key}={value:.3f}' if isinstance(value, float) else f'{key}={value}'
        for key, value in summary.items()))

    failures = []
    if summary['windows'] < args.minimum_windows:
        failures.append(f"windows {summary['windows']} < {args.minimum_windows}")
    if args.minimum_rate_hz is not None and summary['effective_rate_hz'] < args.minimum_rate_hz:
        failures.append(
            f"effective rate {summary['effective_rate_hz']:.3f} < {args.minimum_rate_hz:.3f} Hz")
    if (args.maximum_conversion_p95_ms is not None and
            summary['conversion_p95_ms'] >= args.maximum_conversion_p95_ms):
        failures.append(
            f"conversion p95 {summary['conversion_p95_ms']:.3f} >= "
            f"{args.maximum_conversion_p95_ms:.3f} ms")
    if failures:
        raise SystemExit('ERROR: ' + '; '.join(failures))


if __name__ == '__main__':
    main()

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
DURATION="${1:-120}"
FULL_STACK_LOG="${2:-/tmp/edge_full_stack.log}"
EVIDENCE_DIR="${3:-$REPO_ROOT/validation_evidence}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="$EVIDENCE_DIR/rtabmap_edge_performance_$RUN_ID.log"
METRICS="$(mktemp)"

cleanup() {
    rm -f "$METRICS"
}
trap cleanup EXIT INT TERM

[[ "$DURATION" =~ ^[1-9][0-9]*$ ]] || { echo 'ERROR: duration must be positive'; exit 2; }
[[ -f "$FULL_STACK_LOG" ]] || { echo "ERROR: full-stack log missing: $FULL_STACK_LOG"; exit 2; }
mkdir -p "$EVIDENCE_DIR"
exec > >(tee -a "$OUTPUT") 2>&1

start_line=$(( $(wc -l < "$FULL_STACK_LOG") + 1 ))
echo "rtabmap edge performance utc=$RUN_ID duration_seconds=$DURATION commit=$(git -C "$REPO_ROOT" rev-parse HEAD)"
sleep "$DURATION"
tail -n +"$start_line" "$FULL_STACK_LOG" > "$METRICS"

"$SCRIPT_DIR/rtabmap_performance_probe.py" "$METRICS" --minimum-windows 10
grep 'camera_decoder.*pair_rate=' "$METRICS" | tail -5 || true
ps -eo pid,comm,rss,%cpu,nlwp --sort=-%cpu | head -15

if grep -Eq 'Did not receive data|process has died|retcode -58|FATAL' "$METRICS"; then
    echo 'ERROR: full-stack failure found during probe'
    exit 1
fi

echo 'PASS: RTAB-Map performance metrics captured'
echo "evidence=$OUTPUT"

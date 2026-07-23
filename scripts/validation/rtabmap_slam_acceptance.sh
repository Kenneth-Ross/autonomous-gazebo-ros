#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
MODE="${1:-nominal}"
FULL_STACK_LOG="${2:-/tmp/edge_full_stack.log}"
EVIDENCE_DIR="${3:-$REPO_ROOT/validation_evidence}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="$EVIDENCE_DIR/rtabmap_slam_${MODE}_$RUN_ID.log"
WINDOW="$(mktemp)"
TF_SAMPLE="$(mktemp)"
MAP_SAMPLE="$(mktemp)"
container_pid=''

resume_container() {
    if [[ -n "$container_pid" ]]; then
        kill -CONT "$container_pid" 2>/dev/null || true
    fi
}
cleanup() {
    resume_container
    rm -f "$WINDOW" "$TF_SAMPLE" "$MAP_SAMPLE"
}
trap cleanup EXIT INT TERM

[[ "$MODE" == nominal || "$MODE" == adversarial ]] || {
    echo 'usage: rtabmap_slam_acceptance.sh nominal|adversarial [full-stack-log] [evidence-dir]'
    exit 2
}
[[ -f "$FULL_STACK_LOG" ]] || { echo "ERROR: missing log: $FULL_STACK_LOG"; exit 2; }
mkdir -p "$EVIDENCE_DIR"
exec > >(tee -a "$OUTPUT") 2>&1

set +u
source /opt/ros/jazzy/setup.bash
source "$REPO_ROOT/edge_stack/install/setup.bash"
set -u

echo "rtabmap SLAM acceptance mode=$MODE utc=$RUN_ID commit=$(git -C "$REPO_ROOT" rev-parse HEAD)"
echo "log=$FULL_STACK_LOG"

if [[ "$MODE" == nominal ]]; then
    start_line=$(( $(wc -l < "$FULL_STACK_LOG") + 1 ))
    sleep 120
    tail -n +"$start_line" "$FULL_STACK_LOG" > "$WINDOW"
    "$SCRIPT_DIR/rtabmap_acceptance_probe.py" "$WINDOW" --minimum-windows 50
else
    container_pid="$(pgrep -o -f 'component_container_mt.*vision_container' || true)"
    [[ -n "$container_pid" ]] || { echo 'ERROR: vision_container process not found'; exit 2; }
    echo "SLAM_FAULT_START kind=vision_container_pause pid=$container_pid duration_seconds=3"
    kill -STOP "$container_pid"
    sleep 3
    kill -CONT "$container_pid"
    container_pid=''
    echo 'SLAM_RECOVERY_START'
    start_line=$(( $(wc -l < "$FULL_STACK_LOG") + 1 ))
    sleep 90
    {
        echo 'SLAM_RECOVERY_START'
        tail -n +"$start_line" "$FULL_STACK_LOG"
    } > "$WINDOW"
    "$SCRIPT_DIR/rtabmap_acceptance_probe.py" "$WINDOW" --minimum-windows 30 --require-recovery-marker
fi

echo '===== MAP TF ====='
set +e
timeout 8 ros2 run tf2_ros tf2_echo map base_link | tee "$TF_SAMPLE" | tail -20
set -e
grep -q 'Translation:' "$TF_SAMPLE" || { echo 'ERROR: map -> base_link unavailable'; exit 1; }
echo '===== MAP DATA ====='
set +e
timeout 8 ros2 topic hz /rtabmap/mapData --window 5 | tee "$MAP_SAMPLE"
set -e
grep -q 'average rate:' "$MAP_SAMPLE" || { echo 'ERROR: /rtabmap/mapData unavailable'; exit 1; }
echo "PASS: RTAB-Map SLAM $MODE acceptance"
echo "evidence=$OUTPUT"

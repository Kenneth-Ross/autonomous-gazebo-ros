#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
EDGE_WORKSPACE="${EDGE_WORKSPACE:-$REPO_ROOT/edge_stack}"
EVIDENCE_DIR="${1:-$REPO_ROOT/validation_evidence}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="$EVIDENCE_DIR/camera_edge_adversarial_$RUN_ID.log"
RECEIVER_LOG="$(mktemp)"
receiver_pid=''
cleanup() {
    stop_receiver
    rm -f "$RECEIVER_LOG"
}
stop_receiver() {
    if [[ -n "$receiver_pid" ]]; then
        kill -INT -- "-$receiver_pid" 2>/dev/null || true
        wait "$receiver_pid" 2>/dev/null || true
        receiver_pid=''
    fi
}
trap cleanup EXIT INT TERM
mkdir -p "$EVIDENCE_DIR"
exec > >(tee -a "$OUTPUT") 2>&1

[[ -f "$EDGE_WORKSPACE/install/setup.bash" ]] || { echo 'ERROR: edge workspace not built'; exit 2; }
set +u
source /opt/ros/jazzy/setup.bash
source "$EDGE_WORKSPACE/install/setup.bash"
set -u
if ros2 node list 2>/dev/null | grep -Fxq /camera_decoder; then
    echo 'ERROR: stop the existing edge receiver before adversarial sequence'
    exit 2
fi

start_receiver() {
    : > "$RECEIVER_LOG"
    setsid ros2 launch rtabmap_bridge rtabmap_slam.launch.py > "$RECEIVER_LOG" 2>&1 &
    receiver_pid=$!
}

latest_field() {
    local field="$1"
    grep 'camera_decoder.*pair_rate=' "$RECEIVER_LOG" | tail -1 | \
        sed -n "s/.*${field}=\\([^ ]*\\).*/\\1/p"
}

wait_for_pair_rate() {
    local deadline=$((SECONDS + 40)) rate
    while (( SECONDS < deadline )); do
        kill -0 "$receiver_pid" 2>/dev/null || { tail -40 "$RECEIVER_LOG"; echo 'ERROR: receiver exited'; return 1; }
        rate="$(latest_field pair_rate)"
        if [[ -n "$rate" ]] && awk -v rate="$rate" 'BEGIN {exit !(rate >= 29.0)}'; then
            echo "pair_rate=$rate"
            return 0
        fi
        sleep 1
    done
    tail -40 "$RECEIVER_LOG"
    echo 'ERROR: receiver did not recover 29 FPS pairing'
    return 1
}

assert_clean_transport() {
    if grep -Eq 'retcode -58|send_packet failed|depth Zstd decode failed' "$RECEIVER_LOG"; then
        tail -40 "$RECEIVER_LOG"
        echo 'ERROR: transport failure found'
        return 1
    fi
}

echo "camera edge adversarial utc=$RUN_ID commit=$(git -C "$REPO_ROOT" rev-parse HEAD)"
echo '===== baseline receiver ====='
start_receiver
wait_for_pair_rate
assert_clean_transport

echo '===== receiver stop/restart ====='
stop_receiver
sleep 2
start_receiver
wait_for_pair_rate
assert_clean_transport

echo '===== slow best-effort consumer ====='
python3 "$SCRIPT_DIR/adversarial_edge_probe.py" slow-consumer --duration 15 --delay 0.25
wait_for_pair_rate
assert_clean_transport

echo '===== malformed Zstd frame ====='
before="$(latest_field malformed)"
python3 "$SCRIPT_DIR/adversarial_edge_probe.py" corrupt-depth --count 3
sleep 6
after="$(latest_field malformed)"
[[ -n "$before" && -n "$after" && "$after" -gt "$before" ]] || {
    tail -40 "$RECEIVER_LOG"
    echo "ERROR: malformed counter did not grow before=${before:-missing} after=${after:-missing}"
    exit 1
}
echo "malformed_rejected=$((after-before))"
wait_for_pair_rate
assert_clean_transport

echo 'PASS: receiver restart, slow consumer, malformed depth, and recovery'
echo "evidence=$OUTPUT"

#!/usr/bin/env bash
set -eo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
EVIDENCE_DIR=${1:-"$REPO_ROOT/validation_evidence"}
RUN_ID=${2:-"lifecycle_$(date -u +%Y%m%dT%H%M%SZ)"}
RECORD_ROOT="$EVIDENCE_DIR/autonomous_racing_records_$RUN_ID"
EVIDENCE_FILE="$EVIDENCE_DIR/autonomous_racing_lifecycle_$RUN_ID.log"
LAUNCH_LOG="$EVIDENCE_DIR/autonomous_racing_lifecycle_launch_$RUN_ID.log"
PREPARE_LOG="$EVIDENCE_DIR/autonomous_racing_lifecycle_prepare_$RUN_ID.log"
RECORDER_PREPARE_LOG="$EVIDENCE_DIR/autonomous_racing_lifecycle_recorder_prepare_$RUN_ID.log"
HEARTBEAT_LOG="$EVIDENCE_DIR/autonomous_racing_lifecycle_heartbeat_$RUN_ID.log"
RECORDER_START_LOG="$EVIDENCE_DIR/autonomous_racing_lifecycle_recorder_start_$RUN_ID.log"
START_LOG="$EVIDENCE_DIR/autonomous_racing_lifecycle_start_$RUN_ID.log"
ABORT_LOG="$EVIDENCE_DIR/autonomous_racing_lifecycle_abort_$RUN_ID.log"
RECORDER_ABORT_LOG="$EVIDENCE_DIR/autonomous_racing_lifecycle_recorder_abort_$RUN_ID.log"
LAUNCH_PID=
RECORDER_ABORT_SENT=0

mkdir -p "$EVIDENCE_DIR" "$RECORD_ROOT"
source /opt/ros/jazzy/setup.bash
source "$REPO_ROOT/edge_stack/install/setup.bash"
source "$REPO_ROOT/server_sim/install/setup.bash"
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-87}
export GZ_IP=${GZ_IP:-127.0.0.1}

cleanup() {
    if [[ "$RECORDER_ABORT_SENT" -eq 0 ]] &&
        [[ -n "$LAUNCH_PID" ]] && kill -0 "$LAUNCH_PID" 2>/dev/null &&
        ros2 service list 2>/dev/null | grep -Fxq /racing/recorder/abort; then
        timeout 5s ros2 service call /racing/recorder/abort \
            autonomous_racing_msgs/srv/AbortRun "{reason: lifecycle_cleanup}" \
            >/dev/null 2>&1 || true
    fi
    if [[ -n "$LAUNCH_PID" ]] && kill -0 "$LAUNCH_PID" 2>/dev/null; then
        kill -INT -- "-$LAUNCH_PID" 2>/dev/null || true
        wait "$LAUNCH_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

{
    echo "autonomous racing lifecycle utc=$(date -u +%Y%m%dT%H%M%SZ)"
    echo "run_id=$RUN_ID"
    echo "record_root=$RECORD_ROOT"
    echo "launch_log=$LAUNCH_LOG"
    echo "commit=$(git -C "$REPO_ROOT" rev-parse HEAD)"
} | tee "$EVIDENCE_FILE"

setsid ros2 launch autonomous_racing autonomous_race.launch.py \
    headless:=true run_edge:=false initial_track:=catalunya \
    enable_camera_bridges:=true \
    enable_sensor_bridges:=true \
    enable_autonomy_nodes:=true \
    artifact_root:="$RECORD_ROOT" >"$LAUNCH_LOG" 2>&1 &
LAUNCH_PID=$!

wait_for_service() {
    local service=$1
    local deadline=$((SECONDS + 60))
    while (( SECONDS < deadline )); do
        if ros2 service list 2>/dev/null | grep -Fxq "$service"; then
            return 0
        fi
        sleep 1
    done
    echo "FAIL: service unavailable: $service" | tee -a "$EVIDENCE_FILE"
    return 1
}

wait_for_service /racing/prepare
wait_for_service /racing/start
wait_for_service /racing/abort
wait_for_service /racing/recorder/prepare
wait_for_service /racing/recorder/start
wait_for_service /racing/recorder/abort

if ! timeout 45s ros2 service call /racing/prepare \
    autonomous_racing_msgs/srv/PrepareRun \
    "{run_id_hint: $RUN_ID, track_name: catalunya, seed: 1}" \
    >"$PREPARE_LOG" 2>&1; then
    cat "$PREPARE_LOG" | tee -a "$EVIDENCE_FILE"
    echo 'FAIL: supervisor prepare call failed' | tee -a "$EVIDENCE_FILE"
    exit 1
fi
if ! grep -q 'success=True' "$PREPARE_LOG"; then
    cat "$PREPARE_LOG" | tee -a "$EVIDENCE_FILE"
    echo 'FAIL: supervisor prepare did not succeed' | tee -a "$EVIDENCE_FILE"
    exit 1
fi

if ! timeout 45s ros2 service call /racing/recorder/prepare \
    autonomous_racing_msgs/srv/PrepareRun \
    "{run_id_hint: $RUN_ID, track_name: catalunya, seed: 1}" \
    >"$RECORDER_PREPARE_LOG" 2>&1; then
    cat "$RECORDER_PREPARE_LOG" | tee -a "$EVIDENCE_FILE"
    echo 'FAIL: recorder prepare call failed' | tee -a "$EVIDENCE_FILE"
    exit 1
fi
if ! grep -q 'success=True' "$RECORDER_PREPARE_LOG"; then
    cat "$RECORDER_PREPARE_LOG" | tee -a "$EVIDENCE_FILE"
    echo 'FAIL: recorder prepare did not succeed' | tee -a "$EVIDENCE_FILE"
    exit 1
fi

if ! timeout 8s ros2 topic echo --once /racing/recorder/heartbeat \
    autonomous_racing_msgs/msg/RecorderHeartbeat >"$HEARTBEAT_LOG" 2>&1; then
    cat "$HEARTBEAT_LOG" | tee -a "$EVIDENCE_FILE"
    echo 'FAIL: recorder heartbeat unavailable' | tee -a "$EVIDENCE_FILE"
    exit 1
fi
if ! grep -q "run_id: $RUN_ID" "$HEARTBEAT_LOG" ||
    ! grep -q 'bag_healthy: true' "$HEARTBEAT_LOG"; then
    cat "$HEARTBEAT_LOG" | tee -a "$EVIDENCE_FILE"
    echo 'FAIL: recorder heartbeat not healthy for requested run' | tee -a "$EVIDENCE_FILE"
    exit 1
fi

if ! timeout 45s ros2 service call /racing/recorder/start \
    autonomous_racing_msgs/srv/StartRun "{start: true}" \
    >"$RECORDER_START_LOG" 2>&1; then
    cat "$RECORDER_START_LOG" | tee -a "$EVIDENCE_FILE"
    echo 'FAIL: recorder start call failed' | tee -a "$EVIDENCE_FILE"
    exit 1
fi
if ! grep -q 'success=True' "$RECORDER_START_LOG"; then
    cat "$RECORDER_START_LOG" | tee -a "$EVIDENCE_FILE"
    echo 'FAIL: recorder start did not succeed' | tee -a "$EVIDENCE_FILE"
    exit 1
fi

if ! timeout 45s ros2 service call /racing/start \
    autonomous_racing_msgs/srv/StartRun "{start: true}" \
    >"$START_LOG" 2>&1; then
    cat "$START_LOG" | tee -a "$EVIDENCE_FILE"
    echo 'FAIL: supervisor start call failed' | tee -a "$EVIDENCE_FILE"
    exit 1
fi
if ! grep -q 'success=True' "$START_LOG"; then
    cat "$START_LOG" | tee -a "$EVIDENCE_FILE"
    echo 'FAIL: supervisor start did not succeed' | tee -a "$EVIDENCE_FILE"
    exit 1
fi

sleep 1
if ! timeout 45s ros2 service call /racing/abort \
    autonomous_racing_msgs/srv/AbortRun "{reason: lifecycle_smoke}" \
    >"$ABORT_LOG" 2>&1; then
    cat "$ABORT_LOG" | tee -a "$EVIDENCE_FILE"
    echo 'FAIL: supervisor abort call failed' | tee -a "$EVIDENCE_FILE"
    exit 1
fi
if ! grep -q 'success=True' "$ABORT_LOG"; then
    cat "$ABORT_LOG" | tee -a "$EVIDENCE_FILE"
    echo 'FAIL: supervisor abort did not succeed' | tee -a "$EVIDENCE_FILE"
    exit 1
fi

if ! timeout 45s ros2 service call /racing/recorder/abort \
    autonomous_racing_msgs/srv/AbortRun "{reason: lifecycle_smoke}" \
    >"$RECORDER_ABORT_LOG" 2>&1; then
    cat "$RECORDER_ABORT_LOG" | tee -a "$EVIDENCE_FILE"
    echo 'FAIL: recorder abort call failed' | tee -a "$EVIDENCE_FILE"
    exit 1
fi
if ! grep -q 'success=True' "$RECORDER_ABORT_LOG"; then
    cat "$RECORDER_ABORT_LOG" | tee -a "$EVIDENCE_FILE"
    echo 'FAIL: recorder abort did not succeed' | tee -a "$EVIDENCE_FILE"
    exit 1
fi
RECORDER_ABORT_SENT=1

RUN_DIR=$(find "$RECORD_ROOT" -maxdepth 1 -type d -name "run_*_$RUN_ID" -print -quit)
if [[ -z "$RUN_DIR" ]]; then
    echo 'FAIL: run artifact directory missing' | tee -a "$EVIDENCE_FILE"
    exit 1
fi
SUMMARY="$RUN_DIR/run_summary.json"
if [[ ! -f "$SUMMARY" || ! -f "$RUN_DIR/recorder.log" ]]; then
    echo 'FAIL: summary or recorder log missing' | tee -a "$EVIDENCE_FILE"
    exit 1
fi
/usr/bin/python3 - "$SUMMARY" <<'PY' | tee -a "$EVIDENCE_FILE"
import json
import sys
from pathlib import Path
summary_path = Path(sys.argv[1])
payload = json.loads(summary_path.read_text())
assert payload['terminal_state'] == 'ABORTED', payload
assert payload['recorder_returncode'] == 0, payload
assert payload['bag_integrity']['valid'] is True, payload
print('RESULT terminal_state=ABORTED recorder_returncode=0 bag_integrity=valid')
PY
if grep -q 'Output folder .* already exists' "$RUN_DIR/recorder.log"; then
    echo 'FAIL: recorder output directory collision' | tee -a "$EVIDENCE_FILE"
    exit 1
fi
if ! grep -q 'Recording stopped' "$RUN_DIR/recorder.log"; then
    echo 'FAIL: rosbag recorder did not stop cleanly' | tee -a "$EVIDENCE_FILE"
    exit 1
fi

cat "$PREPARE_LOG" "$RECORDER_PREPARE_LOG" "$HEARTBEAT_LOG" \
    "$RECORDER_START_LOG" "$START_LOG" "$ABORT_LOG" "$RECORDER_ABORT_LOG" >> "$EVIDENCE_FILE"
echo "PASS: retained evidence $EVIDENCE_FILE artifact=$RUN_DIR" | tee -a "$EVIDENCE_FILE"

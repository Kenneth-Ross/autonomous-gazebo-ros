#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
SERVER_WORKSPACE="${SERVER_WORKSPACE:-$REPO_ROOT/server_sim}"
OUTAGE_SECONDS="${1:-8}"
EVIDENCE_DIR="${2:-$REPO_ROOT/validation_evidence}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="$EVIDENCE_DIR/camera_server_sender_restart_$RUN_ID.log"
SENDER_LOG="$EVIDENCE_DIR/camera_server_sender_replacement_$RUN_ID.log"
replacement_pid=''
failed=true
cleanup() {
    if $failed && [[ -n "$replacement_pid" ]]; then
        kill -TERM -- "-$replacement_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM
[[ "$OUTAGE_SECONDS" =~ ^[1-9][0-9]*$ ]] || { echo 'ERROR: outage seconds must be positive'; exit 2; }
[[ -f "$SERVER_WORKSPACE/install/setup.bash" ]] || { echo 'ERROR: server workspace not built'; exit 2; }
mkdir -p "$EVIDENCE_DIR"
exec > >(tee -a "$OUTPUT") 2>&1
set +u
source /opt/ros/jazzy/setup.bash
source "$SERVER_WORKSPACE/install/setup.bash"
set -u
mapfile -t sender_pids < <(pgrep -f '/sim_camera_encoder_node( |$)' || true)
[[ ${#sender_pids[@]} -eq 1 ]] || {
    echo "ERROR: expected exactly one encoder process, found ${#sender_pids[@]}"; exit 2;
}
old_pid="${sender_pids[0]}"
echo "server sender-restart utc=$RUN_ID commit=$(git -C "$REPO_ROOT" rev-parse HEAD) old_pid=$old_pid"
kill -TERM "$old_pid"
deadline=$((SECONDS + 15))
while kill -0 "$old_pid" 2>/dev/null && (( SECONDS < deadline )); do sleep 1; done
kill -0 "$old_pid" 2>/dev/null && { echo 'ERROR: old sender did not stop'; exit 1; }
echo "sender_stopped outage_seconds=$OUTAGE_SECONDS"
sleep "$OUTAGE_SECONDS"
setsid ros2 launch gazebo_oakd_stream_sender stream_to_remote.launch.py > "$SENDER_LOG" 2>&1 &
replacement_pid=$!
sleep 10
kill -0 "$replacement_pid" 2>/dev/null || { tail -40 "$SENDER_LOG"; echo 'ERROR: replacement sender exited'; exit 1; }
new_pid="$(pgrep -P "$replacement_pid" -f '/sim_camera_encoder_node( |$)' | head -1 || true)"
[[ -n "$new_pid" ]] || { tail -40 "$SENDER_LOG"; echo 'ERROR: replacement encoder process missing'; exit 1; }
failed=false
echo "PASS: sender restarted launcher_pid=$replacement_pid encoder_pid=$new_pid"
echo "sender_log=$SENDER_LOG"
echo "evidence=$OUTPUT"

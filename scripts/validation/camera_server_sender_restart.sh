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
replacement_launcher=''
completed=false
cleanup() {
    if ! $completed && [[ -n "$replacement_launcher" ]]; then
        kill -TERM "$replacement_launcher" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM
[[ "$OUTAGE_SECONDS" =~ ^[1-9][0-9]*$ ]] || { echo 'ERROR: outage seconds must be positive'; exit 2; }
[[ -f "$SERVER_WORKSPACE/install/setup.bash" ]] || { echo 'ERROR: server workspace not built'; exit 2; }
mkdir -p "$EVIDENCE_DIR"; exec > >(tee -a "$OUTPUT") 2>&1
set +u; source /opt/ros/jazzy/setup.bash; source "$SERVER_WORKSPACE/install/setup.bash"; set -u
publisher_count() { ros2 topic info "$1" 2>/dev/null | sed -n 's/Publisher count: //p' | head -1; }
wait_publishers() {
    local expected="$1" seconds="$2" rgb depth
    local deadline=$((SECONDS + seconds))
    while (( SECONDS < deadline )); do
        rgb="$(publisher_count /oakd/rgb/image_raw/ffmpeg)"; depth="$(publisher_count /oakd/depth/image_raw/zstd)"
        if [[ "$rgb" == "$expected" && "$depth" == "$expected" ]]; then return 0; fi
        sleep 1
    done
    echo "ERROR: expected publisher counts $expected, got rgb=${rgb:-missing} depth=${depth:-missing}"; return 1
}
mapfile -t encoders < <(pgrep -f '/sim_camera_encoder_node( |$)' || true)
[[ ${#encoders[@]} -eq 1 ]] || { echo "ERROR: expected one encoder process, found ${#encoders[@]}"; exit 2; }
encoder_pid="${encoders[0]}"; launcher_pid="$(ps -o ppid= -p "$encoder_pid" | tr -d ' ')"
launcher_args="$(ps -o args= -p "$launcher_pid")"
[[ "$launcher_args" == *'ros2 launch gazebo_oakd_stream_sender stream_to_remote.launch.py'* ]] || {
    echo "ERROR: encoder parent $launcher_pid is not owned sender launcher"; exit 2;
}
[[ "$(publisher_count /oakd/rgb/image_raw/ffmpeg)" == 1 && "$(publisher_count /oakd/depth/image_raw/zstd)" == 1 ]] || {
    echo 'ERROR: sender baseline must have exactly one publisher per stream'; exit 2;
}
echo "server sender-restart utc=$RUN_ID launcher_pid=$launcher_pid encoder_pid=$encoder_pid"
kill -TERM "$launcher_pid"
deadline=$((SECONDS + 15))
while { kill -0 "$launcher_pid" 2>/dev/null || kill -0 "$encoder_pid" 2>/dev/null; } && (( SECONDS < deadline )); do sleep 1; done
if kill -0 "$launcher_pid" 2>/dev/null || kill -0 "$encoder_pid" 2>/dev/null; then
    echo 'ERROR: owned sender process tree did not stop'; exit 1
fi
wait_publishers 0 30
echo "sender_stopped outage_seconds=$OUTAGE_SECONDS"; sleep "$OUTAGE_SECONDS"
setsid ros2 launch gazebo_oakd_stream_sender stream_to_remote.launch.py > "$SENDER_LOG" 2>&1 &
replacement_launcher=$!
wait_publishers 1 40
mapfile -t new_encoders < <(pgrep -P "$replacement_launcher" -f '/sim_camera_encoder_node( |$)' || true)
[[ ${#new_encoders[@]} -eq 1 ]] || { tail -40 "$SENDER_LOG"; echo 'ERROR: replacement process tree invalid'; exit 1; }
completed=true
echo "PASS: clean DDS zero-to-one sender restart launcher_pid=$replacement_launcher encoder_pid=${new_encoders[0]}"
echo "sender_log=$SENDER_LOG"; echo "evidence=$OUTPUT"

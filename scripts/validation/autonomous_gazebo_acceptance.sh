#!/usr/bin/env bash
set -eo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
MODE=${1:-nominal}
EVIDENCE_DIR=${2:-"$REPO_ROOT/validation_evidence"}
if [[ "$MODE" != nominal && "$MODE" != adversarial ]]; then
    echo 'usage: autonomous_gazebo_acceptance.sh nominal|adversarial [evidence-dir]' >&2
    exit 2
fi
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_FILE="$EVIDENCE_DIR/autonomous_gazebo_${MODE}_${RUN_ID}.log"
LAUNCH_LOG="$EVIDENCE_DIR/autonomous_gazebo_${MODE}_launch_${RUN_ID}.log"
LAUNCH_PID=

mkdir -p "$EVIDENCE_DIR"
source /opt/ros/jazzy/setup.bash
source "$REPO_ROOT/server_sim/install/setup.bash"
set -u
export GZ_IP=127.0.0.1
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-87}

cleanup() {
    if [[ -n "$LAUNCH_PID" ]] && kill -0 "$LAUNCH_PID" 2>/dev/null; then
        kill -INT -- "-$LAUNCH_PID" 2>/dev/null || true
        wait "$LAUNCH_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

{
    echo "autonomous Gazebo acceptance mode=$MODE utc=$RUN_ID"
    echo "commit=$(git -C "$REPO_ROOT" rev-parse HEAD)"
    echo "ros_domain_id=$ROS_DOMAIN_ID"
    echo "launch_log=$LAUNCH_LOG"
} | tee "$EVIDENCE_FILE"

setsid ros2 launch my_gazebo_package gazebo.launch.py \
    headless:=true enable_driving_model:=true initial_track:=catalunya \
    >"$LAUNCH_LOG" 2>&1 &
LAUNCH_PID=$!

set +e
/usr/bin/python3 "$REPO_ROOT/scripts/validation/autonomous_gazebo_probe.py" "$MODE" \
    2>&1 | tee -a "$EVIDENCE_FILE"
PROBE_STATUS=${PIPESTATUS[0]}
set -e

if [[ $PROBE_STATUS -ne 0 ]]; then
    echo "FAIL: Gazebo probe exited $PROBE_STATUS" | tee -a "$EVIDENCE_FILE"
    exit "$PROBE_STATUS"
fi
if grep -Eq 'Entity creation unsuccessful|process has died.*exit code [^(-2)]|Traceback' "$LAUNCH_LOG"; then
    echo 'FAIL: launch log contains a spawn, process, or Python failure' \
        | tee -a "$EVIDENCE_FILE"
    exit 1
fi

echo "PASS: retained evidence $EVIDENCE_FILE" | tee -a "$EVIDENCE_FILE"

#!/usr/bin/env bash
set -eo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
EVIDENCE_DIR=${1:-"$REPO_ROOT/validation_evidence"}
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_FILE="$EVIDENCE_DIR/nav2_u_turn_${RUN_ID}.log"
LAUNCH_LOG="$EVIDENCE_DIR/nav2_u_turn_launch_${RUN_ID}.log"
LAUNCH_PID=

mkdir -p "$EVIDENCE_DIR"
source /opt/ros/jazzy/setup.bash
export PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH
source "$REPO_ROOT/edge_stack/install/setup.bash"
set -u
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-88}

cleanup() {
    if [[ -n "$LAUNCH_PID" ]] && kill -0 "$LAUNCH_PID" 2>/dev/null; then
        kill -INT -- "-$LAUNCH_PID" 2>/dev/null || true
        wait "$LAUNCH_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

{
    echo "Nav2 U-turn acceptance utc=$RUN_ID"
    echo "commit=$(git -C "$REPO_ROOT" rev-parse HEAD)"
    echo "ros_domain_id=$ROS_DOMAIN_ID"
    echo "launch_log=$LAUNCH_LOG"
} | tee "$EVIDENCE_FILE"

setsid ros2 launch edge_nav2 nav2_edge.launch.py use_sim_time:=false \
    >"$LAUNCH_LOG" 2>&1 &
LAUNCH_PID=$!

set +e
/usr/bin/python3 "$REPO_ROOT/scripts/validation/nav2_mission_probe.py" \
    2>&1 | tee -a "$EVIDENCE_FILE"
PROBE_STATUS=${PIPESTATUS[0]}
set -e

if [[ $PROBE_STATUS -ne 0 ]]; then
    echo "FAIL: Nav2 mission probe exited $PROBE_STATUS" | tee -a "$EVIDENCE_FILE"
    exit "$PROBE_STATUS"
fi
if grep -Eq 'FATAL|Failed to bring up|Exception when loading BT|Traceback' "$LAUNCH_LOG"; then
    echo 'FAIL: Nav2 launch log contains lifecycle, plugin, or Python failure' \
        | tee -a "$EVIDENCE_FILE"
    exit 1
fi

echo "PASS: retained evidence $EVIDENCE_FILE" | tee -a "$EVIDENCE_FILE"

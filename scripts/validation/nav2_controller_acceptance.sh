#!/usr/bin/env bash
set -eo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
EVIDENCE_DIR=${1:-"$REPO_ROOT/validation_evidence"}
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_FILE="$EVIDENCE_DIR/nav2_controller_${RUN_ID}.log"
LAUNCH_LOG="$EVIDENCE_DIR/nav2_controller_launch_${RUN_ID}.log"
LAUNCH_PID=

mkdir -p "$EVIDENCE_DIR"
source /opt/ros/jazzy/setup.bash
export PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH
source "$REPO_ROOT/edge_stack/install/setup.bash"
set -u
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-89}

cleanup() {
    if [[ -n "$LAUNCH_PID" ]] && kill -0 "$LAUNCH_PID" 2>/dev/null; then
        kill -INT -- "-$LAUNCH_PID" 2>/dev/null || true
        wait "$LAUNCH_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

{
    echo "Nav2 controller acceptance utc=$RUN_ID"
    echo "commit=$(git -C "$REPO_ROOT" rev-parse HEAD)"
    echo "ros_domain_id=$ROS_DOMAIN_ID"
    echo "launch_log=$LAUNCH_LOG"
} | tee "$EVIDENCE_FILE"

start_nav2() {
    local mode=$1
    LAUNCH_LOG="$EVIDENCE_DIR/nav2_controller_${mode}_launch_${RUN_ID}.log"
    setsid ros2 launch edge_nav2 nav2_edge.launch.py use_sim_time:=false \
        >"$LAUNCH_LOG" 2>&1 &
    LAUNCH_PID=$!
}

stop_nav2() {
    if [[ -n "$LAUNCH_PID" ]] && kill -0 "$LAUNCH_PID" 2>/dev/null; then
        kill -INT -- "-$LAUNCH_PID" 2>/dev/null || true
        wait "$LAUNCH_PID" 2>/dev/null || true
    fi
    LAUNCH_PID=
}

run_probe() {
    local mode=$1
    set +e
    /usr/bin/python3 "$REPO_ROOT/scripts/validation/nav2_controller_probe.py" "$mode" \
        2>&1 | tee -a "$EVIDENCE_FILE"
    local status=${PIPESTATUS[0]}
    set -e
    return "$status"
}

start_nav2 u_turn
run_probe u_turn
if grep -Eq 'FATAL|Failed to bring up|Traceback|Segmentation fault' "$LAUNCH_LOG"; then
    echo 'FAIL: U-turn Nav2 launch log contains lifecycle, plugin, or process failure' \
        | tee -a "$EVIDENCE_FILE"
    exit 1
fi
stop_nav2

start_nav2 s_turn
run_probe s_turn
if grep -Eq 'FATAL|Failed to bring up|Traceback|Segmentation fault' "$LAUNCH_LOG"; then
    echo 'FAIL: S-turn Nav2 launch log contains lifecycle, plugin, or process failure' \
        | tee -a "$EVIDENCE_FILE"
    exit 1
fi

echo "PASS: retained evidence $EVIDENCE_FILE" | tee -a "$EVIDENCE_FILE"

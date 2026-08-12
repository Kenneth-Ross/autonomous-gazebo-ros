#!/usr/bin/env bash
set -eo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
EVIDENCE_DIR=${1:-"$REPO_ROOT/validation_evidence"}
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_FILE="$EVIDENCE_DIR/nav2_wall_clearance_${RUN_ID}.log"
LAUNCH_LOG="$EVIDENCE_DIR/nav2_wall_clearance_launch_${RUN_ID}.log"
LAUNCH_PID=
PARAMS_FILE=

mkdir -p "$EVIDENCE_DIR"
source /opt/ros/jazzy/setup.bash
export PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH
source "$REPO_ROOT/edge_stack/install/setup.bash"
set -u
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-107}

stop_group() {
    local pid=${1:-}
    [[ -n "$pid" ]] || return 0
    if kill -0 "$pid" 2>/dev/null; then
        kill -INT -- "-$pid" 2>/dev/null || true
        for _ in {1..40}; do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.25
        done
        if kill -0 "$pid" 2>/dev/null; then
            kill -TERM -- "-$pid" 2>/dev/null || true
            kill -KILL -- "-$pid" 2>/dev/null || true
        fi
        wait "$pid" 2>/dev/null || true
    fi
}

cleanup() {
    stop_group "$LAUNCH_PID"
    if [[ -n "$PARAMS_FILE" ]]; then
        rm -f "$PARAMS_FILE"
        PARAMS_FILE=
    fi
}
trap cleanup EXIT INT TERM

{
    echo "Nav2 wall-clearance acceptance utc=$RUN_ID"
    echo "commit=$(git -C "$REPO_ROOT" rev-parse HEAD)"
    echo "ros_domain_id=$ROS_DOMAIN_ID"
    echo "launch_log=$LAUNCH_LOG"
} | tee "$EVIDENCE_FILE"

PARAMS_FILE=$(mktemp /tmp/nav2_wall_params.XXXXXX.yaml)
cp "$REPO_ROOT/edge_stack/install/share/edge_nav2/config/nav2_params.yaml" "$PARAMS_FILE"
sed -i 's/use_sim_time: True/use_sim_time: False/g' "$PARAMS_FILE"
setsid ros2 launch edge_nav2 nav2_edge.launch.py \
    use_sim_time:=false params_file:="$PARAMS_FILE" \
    >"$LAUNCH_LOG" 2>&1 &
LAUNCH_PID=$!

set +e
/usr/bin/python3 "$REPO_ROOT/scripts/validation/nav2_wall_clearance_probe.py" \
    2>&1 | tee -a "$EVIDENCE_FILE"
PROBE_STATUS=${PIPESTATUS[0]}
set -e
if [[ $PROBE_STATUS -ne 0 ]]; then
    echo "FAIL: wall-clearance probe exited $PROBE_STATUS" | tee -a "$EVIDENCE_FILE"
    exit "$PROBE_STATUS"
fi
if grep -Eq 'FATAL|Failed to bring up|Traceback|process has died|RCLError' \
    "$LAUNCH_LOG"; then
    echo 'FAIL: Nav2 launch log contains lifecycle or process failure' \
        | tee -a "$EVIDENCE_FILE"
    exit 1
fi

echo "PASS: retained evidence $EVIDENCE_FILE" | tee -a "$EVIDENCE_FILE"

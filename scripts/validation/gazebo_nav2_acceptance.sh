#!/usr/bin/env bash
set -eo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
EVIDENCE_DIR=${1:-"$REPO_ROOT/validation_evidence"}
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_FILE="$EVIDENCE_DIR/gazebo_nav2_${RUN_ID}.log"
SIM_PID=
NAV_PID=
PARAMS_FILE=

mkdir -p "$EVIDENCE_DIR"
source /opt/ros/jazzy/setup.bash
export PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH
source "$REPO_ROOT/server_sim/install/setup.bash"
source "$REPO_ROOT/edge_stack/install/setup.bash"
set -u
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-90}
export GZ_IP=127.0.0.1

stop_gazebo_processes() {
    local world_path="$REPO_ROOT/server_sim/install/my_gazebo_package/share/my_gazebo_package/worlds/world.sdf"
    while read -r pid; do
        [[ -n "$pid" ]] || continue
        kill -TERM "$pid" 2>/dev/null || true
    done < <(ps -eo pid=,args= | rg "gz sim" | rg -F "$world_path" | sed -E "s/^ *([0-9]+).*/\1/")
    sleep 1
    while read -r pid; do
        [[ -n "$pid" ]] || continue
        kill -KILL "$pid" 2>/dev/null || true
    done < <(ps -eo pid=,args= | rg "gz sim" | rg -F "$world_path" | sed -E "s/^ *([0-9]+).*/\1/")
}

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
            for _ in {1..20}; do
                kill -0 "$pid" 2>/dev/null || break
                sleep 0.25
            done
        fi
        if kill -0 "$pid" 2>/dev/null; then
            kill -KILL -- "-$pid" 2>/dev/null || true
        fi
        wait "$pid" 2>/dev/null || true
    fi
}

cleanup() {
    stop_group "$NAV_PID"
    stop_group "$SIM_PID"
    stop_gazebo_processes
    if [[ -n "$PARAMS_FILE" ]]; then
        rm -f "$PARAMS_FILE"
        PARAMS_FILE=
    fi
}
trap cleanup EXIT INT TERM

{
    echo "Gazebo Nav2 physical acceptance utc=$RUN_ID"
    echo "commit=$(git -C "$REPO_ROOT" rev-parse HEAD)"
    echo "ros_domain_id=$ROS_DOMAIN_ID"
    echo "track=catalunya"
} | tee "$EVIDENCE_FILE"

run_mode() {
    local mode=$1
    local sim_log="$EVIDENCE_DIR/gazebo_nav2_${mode}_sim_${RUN_ID}.log"
    local nav_log="$EVIDENCE_DIR/gazebo_nav2_${mode}_nav_${RUN_ID}.log"
    setsid ros2 launch my_gazebo_package gazebo.launch.py \
        headless:=true enable_driving_model:=true initial_track:=catalunya \
        >"$sim_log" 2>&1 &
    SIM_PID=$!
    PARAMS_FILE=$(mktemp /tmp/gazebo_nav2_params.XXXXXX.yaml)
    cp "$REPO_ROOT/edge_stack/install/share/edge_nav2/config/nav2_params.yaml" \
        "$PARAMS_FILE"
    sed -i 's/desired_linear_vel: 3.0/desired_linear_vel: 1.0/' "$PARAMS_FILE"
    setsid ros2 launch edge_nav2 nav2_edge.launch.py use_sim_time:=true \
        params_file:="$PARAMS_FILE" >"$nav_log" 2>&1 &
    NAV_PID=$!

    set +e
    /usr/bin/python3 "$REPO_ROOT/scripts/validation/gazebo_nav2_mission_probe.py" "$mode" \
        --ros-args -p use_sim_time:=true 2>&1 | tee -a "$EVIDENCE_FILE"
    local status=${PIPESTATUS[0]}
    set -e
    if [[ $status -ne 0 ]]; then
        echo "FAIL: Gazebo Nav2 $mode probe exited $status" | tee -a "$EVIDENCE_FILE"
        return "$status"
    fi

    if grep -Eq 'FATAL|Failed to bring up|Traceback|Segmentation fault|process has died' \
        "$sim_log" "$nav_log"; then
        echo "FAIL: Gazebo/Nav2 $mode launch log contains fatal/process failure" \
            | tee -a "$EVIDENCE_FILE"
        return 1
    fi

    stop_group "$NAV_PID"
    NAV_PID=
    rm -f "$PARAMS_FILE"
    PARAMS_FILE=
    stop_group "$SIM_PID"
    stop_gazebo_processes
    SIM_PID=
}

run_mode u_turn
run_mode s_turn

echo "PASS: retained evidence $EVIDENCE_FILE" | tee -a "$EVIDENCE_FILE"

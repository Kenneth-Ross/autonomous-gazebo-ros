#!/usr/bin/env bash
# Host control/storage/actuator acceptance. No Orange Pi commands run here.
set -eo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
EVIDENCE_DIR=${1:-"$REPO_ROOT/validation_evidence"}
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)-$$

for workspace in edge_stack server_sim; do
    if [[ ! -f "$REPO_ROOT/$workspace/install/local_setup.bash" ]]; then
        echo "ERROR: build $workspace before running host E2E acceptance" >&2
        exit 2
    fi
done
source /opt/ros/jazzy/setup.bash
source "$REPO_ROOT/edge_stack/install/local_setup.bash"
source "$REPO_ROOT/server_sim/install/local_setup.bash"
set -u
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
mkdir -p "$EVIDENCE_DIR"

for package_path in edge_stack/autonomous_racing_core server_sim/my_gazebo_package; do
    workspace=${package_path%/*}
    package=${package_path#*/}
    evidence="$EVIDENCE_DIR/${package}_host_e2e_$RUN_ID.log"
    ctest --test-dir "$REPO_ROOT/$workspace/build/$package" \
        -L e2e --no-tests=error --output-on-failure 2>&1 | tee "$evidence"
done
printf 'PASS: host E2E evidence retained under %s (run %s)\n' "$EVIDENCE_DIR" "$RUN_ID"

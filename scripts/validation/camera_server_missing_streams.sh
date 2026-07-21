#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
SERVER_WORKSPACE="${SERVER_WORKSPACE:-$REPO_ROOT/server_sim}"
HOLD="${1:-10}"
EVIDENCE_DIR="${2:-$REPO_ROOT/validation_evidence}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="$EVIDENCE_DIR/camera_server_missing_streams_$RUN_ID.log"
restore() { ros2 param set /sim_camera_encoder publish_rgb true >/dev/null 2>&1 || true; ros2 param set /sim_camera_encoder publish_depth true >/dev/null 2>&1 || true; }
trap restore EXIT INT TERM
[[ "$HOLD" =~ ^[1-9][0-9]*$ ]] || { echo 'ERROR: hold must be positive'; exit 2; }
mkdir -p "$EVIDENCE_DIR"; exec > >(tee -a "$OUTPUT") 2>&1
set +u; source /opt/ros/jazzy/setup.bash; source "$SERVER_WORKSPACE/install/setup.bash"; set -u
ros2 param get /sim_camera_encoder publish_rgb >/dev/null
ros2 param get /sim_camera_encoder publish_depth >/dev/null
echo "server missing-stream test utc=$RUN_ID hold_seconds=$HOLD"
echo 'disable_rgb'; ros2 param set /sim_camera_encoder publish_rgb false; sleep "$HOLD"
echo 'restore_rgb'; ros2 param set /sim_camera_encoder publish_rgb true; sleep 12
echo 'disable_depth'; ros2 param set /sim_camera_encoder publish_depth false; sleep "$HOLD"
echo 'restore_depth'; ros2 param set /sim_camera_encoder publish_depth true; sleep 12
restore; trap - EXIT INT TERM
echo 'PASS: RGB and depth fault sequence completed'; echo "evidence=$OUTPUT"

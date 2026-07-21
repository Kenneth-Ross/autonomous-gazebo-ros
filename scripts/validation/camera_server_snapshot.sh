#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
SERVER_WORKSPACE="${SERVER_WORKSPACE:-$REPO_ROOT/server_sim}"
EVIDENCE_DIR="${1:-$REPO_ROOT/validation_evidence}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="$EVIDENCE_DIR/camera_server_snapshot_$RUN_ID.log"

mkdir -p "$EVIDENCE_DIR"
exec > >(tee -a "$OUTPUT") 2>&1

set +u
source /opt/ros/jazzy/setup.bash
source "$SERVER_WORKSPACE/install/setup.bash"
set -u

echo "camera server snapshot"
echo "utc=$RUN_ID commit=$(git -C "$REPO_ROOT" rev-parse HEAD)"

echo
echo "===== multimedia packages ====="
for package in ffmpeg_image_transport ffmpeg_encoder_decoder zstd_image_transport
do
    ros2 pkg prefix "$package"
done

echo
echo "===== installed CycloneDDS contract ====="
sender_prefix="$(ros2 pkg prefix gazebo_oakd_stream_sender)"
sed -n '1,120p' \
    "$sender_prefix/share/gazebo_oakd_stream_sender/config/cyclonedds.xml"

echo
echo "===== network ====="
ip -brief address
ip route

echo
echo "===== camera topics ====="
ros2 topic list | grep -E '^/oakd/(rgb|depth)/image_raw' | sort

echo
echo "===== encoder process ====="
ps -eo pid,comm,rss,nlwp,%cpu,args --sort=-%cpu | \
    grep sim_camera_encoder_node | grep -v grep || true

echo
echo "PASS: server snapshot completed"
echo "evidence=$OUTPUT"

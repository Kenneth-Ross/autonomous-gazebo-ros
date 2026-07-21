#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
EDGE_WORKSPACE="${EDGE_WORKSPACE:-$REPO_ROOT/edge_stack}"
SAMPLES="${1:-30}"
EVIDENCE_DIR="${2:-$REPO_ROOT/validation_evidence}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="$EVIDENCE_DIR/camera_depth_integrity_$RUN_ID.log"
[[ "$SAMPLES" =~ ^[1-9][0-9]*$ ]] || { echo 'ERROR: samples must be positive'; exit 2; }
[[ -f "$EDGE_WORKSPACE/install/setup.bash" ]] || { echo 'ERROR: edge workspace not built'; exit 2; }
mkdir -p "$EVIDENCE_DIR"
exec > >(tee -a "$OUTPUT") 2>&1
set +u
source /opt/ros/jazzy/setup.bash
source "$EDGE_WORKSPACE/install/setup.bash"
set -u
echo "camera depth integrity utc=$RUN_ID samples=$SAMPLES commit=$(git -C "$REPO_ROOT" rev-parse HEAD)"
python3 "$SCRIPT_DIR/depth_integrity_probe.py" "$SAMPLES"
echo "evidence=$OUTPUT"

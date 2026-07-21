#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
EDGE_WORKSPACE="${EDGE_WORKSPACE:-$REPO_ROOT/edge_stack}"
DURATION="${1:-30}"
EVIDENCE_DIR="${2:-$REPO_ROOT/validation_evidence}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="$EVIDENCE_DIR/camera_edge_nominal_$RUN_ID.log"

mkdir -p "$EVIDENCE_DIR"
exec > >(tee -a "$OUTPUT") 2>&1

if [[ ! "$DURATION" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: duration must be a positive integer" >&2
    exit 2
fi
if [[ ! -f /opt/ros/jazzy/setup.bash ]]; then
    echo "ERROR: ROS 2 Jazzy not found" >&2
    exit 2
fi
if [[ ! -f "$EDGE_WORKSPACE/install/local_setup.bash" ]]; then
    echo "ERROR: edge workspace not built: $EDGE_WORKSPACE" >&2
    exit 2
fi

set +u
source /opt/ros/jazzy/setup.bash
source "$EDGE_WORKSPACE/install/local_setup.bash"
set -u

run_timed() {
    local label="$1"
    shift
    local output code
    echo
    echo "===== $label ====="
    set +e
    output="$(timeout --signal=INT "$DURATION" "$@" 2>&1)"
    code=$?
    set -e
    printf "%s\n" "$output"
    [[ $code -eq 0 || $code -eq 124 || $code -eq 130 ]] || return "$code"
    if [[ "$label" == *"rate"* ]]; then
        grep -Fq "average rate:" <<< "$output" || {
            echo "ERROR: $label produced no rate" >&2
            return 1
        }
    fi
}

echo "camera edge nominal probe"
echo "utc=$RUN_ID duration_seconds=$DURATION commit=$(git -C "$REPO_ROOT" rev-parse HEAD)"
echo "workspace=$EDGE_WORKSPACE"

echo
echo "===== preflight ====="
ros2 run rtabmap_bridge multimedia_preflight

echo
echo "===== required topics ====="
topics="$(ros2 topic list | sort)"
printf '%s\n' "$topics"
for topic in \
    /oakd/rgb/image_raw/ffmpeg \
    /oakd/depth/image_raw/zstd \
    /edge/camera/rgb/image_raw \
    /edge/camera/depth/image_raw \
    /edge/camera/rgb/camera_info \
    /edge/camera/depth/camera_info
do
    grep -Fxq "$topic" <<< "$topics" || {
        echo "ERROR: missing topic $topic" >&2
        exit 1
    }
done
if grep -Fq super_frame <<< "$topics"; then
    echo "ERROR: legacy super_frame topic present" >&2
    exit 1
fi

for topic in \
    /oakd/rgb/image_raw/ffmpeg \
    /oakd/depth/image_raw/zstd \
    /edge/camera/rgb/image_raw \
    /edge/camera/depth/image_raw \
    /edge/camera/rgb/camera_info
do
    echo
    echo "===== qos $topic ====="
    ros2 topic info -v "$topic"
done

for stream in rgb depth
do
    topic="/edge/camera/$stream/image_raw"
    for field in header encoding width height
    do
        echo
        echo "===== $stream $field ====="
        field_output="$(ros2 topic echo "$topic" --once --timeout 10 \
            --qos-profile sensor_data --field "$field")"
        printf "%s\n" "$field_output"
        [[ -n "${field_output//[[:space:]]/}" ]] || {
            echo "ERROR: $topic produced no $field" >&2
            exit 1
        }
    done
done

run_timed "rgb raw rate" ros2 topic hz --wall-time /edge/camera/rgb/image_raw
run_timed "depth raw rate" ros2 topic hz --wall-time /edge/camera/depth/image_raw

# Run bandwidth probes sequentially: each probe adds a DDS reader and can perturb flow.
run_timed "rgb wire bandwidth" ros2 topic bw /oakd/rgb/image_raw/ffmpeg
run_timed "depth wire bandwidth" ros2 topic bw /oakd/depth/image_raw/zstd

echo
echo "===== resource snapshot ====="
ps -eo pid,comm,rss,nlwp,%cpu --sort=-%cpu | \
    grep -E 'component_cont|camera_decoder|multimedia_pre' || true

echo
echo "PASS: probe sequence completed; acceptance thresholds require log review"
echo "evidence=$OUTPUT"

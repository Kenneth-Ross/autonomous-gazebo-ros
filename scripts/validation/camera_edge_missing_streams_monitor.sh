#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
EDGE_WORKSPACE="${EDGE_WORKSPACE:-$REPO_ROOT/edge_stack}"
LOG="${1:-/tmp/edge_receiver.log}"
EVIDENCE_DIR="${2:-$REPO_ROOT/validation_evidence}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"; OUTPUT="$EVIDENCE_DIR/camera_edge_missing_streams_$RUN_ID.log"
[[ -f "$LOG" ]] || { echo 'ERROR: receiver log missing'; exit 2; }
[[ -f "$EDGE_WORKSPACE/install/setup.bash" ]] || { echo 'ERROR: edge workspace not built'; exit 2; }
START=$(( $(wc -l < "$LOG") + 1 )); mkdir -p "$EVIDENCE_DIR"; exec > >(tee -a "$OUTPUT") 2>&1
set +u; source /opt/ros/jazzy/setup.bash; source "$EDGE_WORKSPACE/install/setup.bash"; set -u
publisher_count() { ros2 topic info "$1" 2>/dev/null | sed -n 's/Publisher count: //p' | head -1; }
rgb_publishers="$(publisher_count /oakd/rgb/image_raw/ffmpeg)"
depth_publishers="$(publisher_count /oakd/depth/image_raw/zstd)"
[[ "$rgb_publishers" == 1 && "$depth_publishers" == 1 ]] || {
  echo "ERROR: expected one publisher per stream, got rgb=${rgb_publishers:-missing} depth=${depth_publishers:-missing}"; exit 2;
}
line() { tail -n +"$START" "$LOG" | grep 'camera_decoder.*pair_rate=' | tail -1 || true; }
field() { sed -n "s/.*$1=\\([^ ]*\\).*/\\1/p" <<< "$2"; }
wait_state() {
  local state="$1" deadline=$((SECONDS + 75)) row rgb depth pair
  while (( SECONDS < deadline )); do
    row="$(line)"; rgb="$(field rgb_rate "$row")"; depth="$(field depth_rate "$row")"; pair="$(field pair_rate "$row")"
    if [[ -n "$pair" ]]; then
      case "$state" in
        healthy) awk -v p="$pair" 'BEGIN{exit !(p>=29)}' && { echo "healthy=$pair"; return; } ;;
        no_rgb) awk -v r="$rgb" -v d="$depth" -v p="$pair" 'BEGIN{exit !(r<=1&&d>=29&&p<=1)}' && { echo "missing_rgb rgb=$rgb depth=$depth pair=$pair"; return; } ;;
        no_depth) awk -v r="$rgb" -v d="$depth" -v p="$pair" 'BEGIN{exit !(d<=1&&r>=29&&p<=1)}' && { echo "missing_depth rgb=$rgb depth=$depth pair=$pair"; return; } ;;
      esac
    fi; sleep 1
  done; echo "ERROR: state $state not observed"; exit 1
}
echo "edge missing-stream monitor utc=$RUN_ID"
wait_state healthy; echo 'READY: run camera_server_missing_streams.sh'
wait_state no_rgb; wait_state healthy; wait_state no_depth; wait_state healthy
metrics="$(tail -n +"$START" "$LOG")"
max_queue="$(sed -n 's/.*queue_size=\([^ ]*\).*/\1/p' <<< "$metrics" | awk 'NR==1||$1>m{m=$1} END{if(NR)print m}')"
[[ -n "$max_queue" && "$max_queue" -le 16 ]] || { echo 'ERROR: queue bound'; exit 1; }
grep -Eq 'retcode -58|send_packet failed' <<< "$metrics" && { echo 'ERROR: transport error'; exit 1; }
echo "PASS: both missing streams bounded and recovered max_queue=$max_queue"; echo "evidence=$OUTPUT"

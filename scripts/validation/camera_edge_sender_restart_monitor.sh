#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
EDGE_WORKSPACE="${EDGE_WORKSPACE:-$REPO_ROOT/edge_stack}"
RECEIVER_LOG="${1:-/tmp/edge_receiver.log}"
EVIDENCE_DIR="${2:-$REPO_ROOT/validation_evidence}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="$EVIDENCE_DIR/camera_edge_sender_restart_$RUN_ID.log"
[[ -f "$RECEIVER_LOG" ]] || { echo "ERROR: receiver log missing: $RECEIVER_LOG"; exit 2; }
[[ -f "$EDGE_WORKSPACE/install/setup.bash" ]] || { echo 'ERROR: edge workspace not built'; exit 2; }
START_LINE=$(( $(wc -l < "$RECEIVER_LOG") + 1 ))
mkdir -p "$EVIDENCE_DIR"
exec > >(tee -a "$OUTPUT") 2>&1
set +u
source /opt/ros/jazzy/setup.bash
source "$EDGE_WORKSPACE/install/setup.bash"
set -u
latest_field() {
    local field="$1"
    tail -n +"$START_LINE" "$RECEIVER_LOG" | grep 'camera_decoder.*pair_rate=' | tail -1 | \
        sed -n "s/.*${field}=\\([^ ]*\\).*/\\1/p" || true
}
wait_rate() {
    local mode="$1" seconds="$2"
    local deadline=$((SECONDS + seconds))
    local rate row last_row='' consecutive=0
    while (( SECONDS < deadline )); do
        row="$(tail -n +"$START_LINE" "$RECEIVER_LOG" | grep 'camera_decoder.*pair_rate=' | tail -1 || true)"
        if [[ -n "$row" && "$row" != "$last_row" ]]; then
            last_row="$row"
            rate="$(sed -n 's/.*pair_rate=\([^ ]*\).*/\1/p' <<< "$row")"
            if [[ "$mode" == healthy ]] && awk -v value="$rate" 'BEGIN {exit !(value >= 29.0)}'; then
                consecutive=$((consecutive + 1))
                if (( consecutive >= 2 )); then echo "healthy_pair_rate=$rate fresh_windows=2"; return 0; fi
            elif [[ "$mode" == outage ]] && awk -v value="$rate" 'BEGIN {exit !(value <= 1.0)}'; then
                echo "outage_pair_rate=$rate"; return 0
            else
                consecutive=0
            fi
        fi
        sleep 1
    done
    echo "ERROR: $mode rate not observed within ${seconds}s"
    return 1
}
echo "edge sender-restart monitor utc=$RUN_ID commit=$(git -C "$REPO_ROOT" rev-parse HEAD)"
wait_rate healthy 40
echo 'READY: run camera_server_sender_restart.sh on simulation server'
wait_rate outage 60
wait_rate healthy 90
metrics="$(tail -n +"$START_LINE" "$RECEIVER_LOG")"
if grep -Eq 'retcode -58|send_packet failed' <<< "$metrics"; then
    echo 'ERROR: DDS/FFmpeg transport failure found'; exit 1
fi
max_queue="$(sed -n 's/.*queue_size=\([^ ]*\).*/\1/p' <<< "$metrics" | awk 'NR==1 || $1>max {max=$1} END {if (NR) print max}')"
[[ -n "$max_queue" && "$max_queue" -le 16 ]] || { echo "ERROR: queue bound failed max=${max_queue:-missing}"; exit 1; }
echo "PASS: sender outage detected, DDS rediscovered, pair rate recovered, max_queue=$max_queue"
echo "evidence=$OUTPUT"

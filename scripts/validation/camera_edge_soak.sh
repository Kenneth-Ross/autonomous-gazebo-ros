#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
EDGE_WORKSPACE="${EDGE_WORKSPACE:-$REPO_ROOT/edge_stack}"
DURATION="${1:-1800}"
RECEIVER_LOG="${2:-/tmp/edge_receiver.log}"
EVIDENCE_DIR="${3:-$REPO_ROOT/validation_evidence}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="$EVIDENCE_DIR/camera_edge_soak_$RUN_ID.log"
RESOURCES="$(mktemp)"
METRICS="$(mktemp)"
cleanup() {
    rm -f "$RESOURCES" "$METRICS"
}
trap cleanup EXIT INT TERM
mkdir -p "$EVIDENCE_DIR"
exec > >(tee -a "$OUTPUT") 2>&1

[[ "$DURATION" =~ ^[1-9][0-9]*$ ]] || { echo 'ERROR: duration must be positive'; exit 2; }
[[ -f "$RECEIVER_LOG" ]] || { echo "ERROR: receiver log missing: $RECEIVER_LOG"; exit 2; }
[[ -f "$EDGE_WORKSPACE/install/setup.bash" ]] || { echo 'ERROR: edge workspace not built'; exit 2; }
set +u
source /opt/ros/jazzy/setup.bash
source "$EDGE_WORKSPACE/install/setup.bash"
set -u

start_line=$(( $(wc -l < "$RECEIVER_LOG") + 1 ))
echo "camera edge soak utc=$RUN_ID duration_seconds=$DURATION commit=$(git -C "$REPO_ROOT" rev-parse HEAD)"
start_epoch=$(date +%s)
end_epoch=$((start_epoch + DURATION))
while (( $(date +%s) < end_epoch )); do
    elapsed=$(( $(date +%s) - start_epoch ))
    ps -eo rss=,nlwp=,%cpu=,args= | awk -v t="$elapsed" \
        '/component_container_mt/ && !/awk/ {print t, $1, $2, $3; exit}' >> "$RESOURCES"
    sleep 5
done
tail -n +"$start_line" "$RECEIVER_LOG" > "$METRICS"

if grep -Eq 'retcode -58|send_packet failed|depth Zstd decode failed' "$METRICS"; then
    echo 'ERROR: transport error found during soak'
    exit 1
fi
summary=$(awk '
/camera_decoder.*pair_rate=/ {
  pair=drop=queue=malformed=-1
  for (i=1;i<=NF;i++) {
    split($i,a,"=")
    if (a[1]=="pair_rate") pair=a[2]+0
    if (a[1]=="unmatched_dropped") drop=a[2]+0
    if (a[1]=="queue_size") queue=a[2]+0
    if (a[1]=="malformed") malformed=a[2]+0
  }
  if (n==0) {first_drop=drop; first_bad=malformed}
  n++; sum+=pair; if (queue>max_queue) max_queue=queue
  last_drop=drop; last_bad=malformed
}
END {
  if (!n) exit 2
  printf "metric_windows=%d pair_rate_mean=%.3f max_queue=%d drop_growth=%d malformed_growth=%d", n, sum/n, max_queue, last_drop-first_drop, last_bad-first_bad
  if (sum/n < 29.5 || max_queue > 16 || last_drop > first_drop || last_bad > first_bad) exit 1
}' "$METRICS") || { echo "ERROR: decoder metrics failed ${summary:-missing}"; exit 1; }
echo "$summary"

resource_summary=$(awk -v warmup=60 '
$1>=warmup && base==0 {base=$2; base_threads=$3}
{last=$2; if ($3>max_threads) max_threads=$3}
END {
  if (NR==0) exit 2
  if (!base) {base=$2; base_threads=$3}
  growth=base ? 100*(last-base)/base : 999
  printf "rss_warmup_kb=%d rss_final_kb=%d rss_growth_percent=%.3f max_threads=%d", base, last, growth, max_threads
  if (growth > 5.0 || max_threads > base_threads+2) exit 1
}' "$RESOURCES") || { echo "ERROR: resource growth failed ${resource_summary:-missing}"; exit 1; }
echo "$resource_summary"
p95=$(sed -n 's/.*latency_p95_ms=\([0-9.]*\).*/\1/p' "$METRICS" | awk 'NR==1 || $1>max {max=$1} END {if (NR) printf "%.3f", max}')
[[ -n "$p95" && "$p95" != '-1.000' ]] || { echo 'ERROR: p95 latency missing'; exit 1; }
awk -v p95="$p95" 'BEGIN {exit !(p95 < 150.0)}' || { echo "ERROR: p95 latency ${p95}ms >= 150ms"; exit 1; }
echo "latency_window_max_p95_ms=$p95"
echo "PASS: soak thresholds met"
echo "evidence=$OUTPUT"

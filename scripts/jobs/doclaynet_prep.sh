#!/usr/bin/env bash
# Pod-side job: sample DocLayNet pages (CPU, network only) and publish them over the runpodctl relay.
# Started by scripts/runpod_launch.sh through rp, so the dead-man's-switch is already armed.
# Grep-able markers: STAGE, hb, WARN, ERROR, STAGE failed, PREP, RP_REPORT_BEGIN/END, RP_ARTIFACT_CODE.
set -Eeuo pipefail
W=${W:-/workspace}; RUN=$W/run; OUT=$W/out; mkdir -p "$RUN" "$OUT"
exec > >(tee -a "$RUN/job.log") 2>&1
START=$(date +%s); : > "$RUN/stage"; : > "$RUN/status"

stage() { echo "$1" > "$RUN/stage"; echo "STAGE $1"; }
fail()  { echo "STAGE failed ($1; was: $(cat "$RUN/stage"))"; echo failed > "$RUN/status"; }
trap 'fail "line $LINENO"' ERR

heartbeat() { while sleep 60; do
  quiet=$(( $(date +%s) - $(stat -c %Y "$RUN/job.log") ))
  disk=$(df --output=pcent "$W" | tail -1 | tr -dc 0-9); ram=$(free | awk '/Mem:/{printf "%d", $3*100/$2}')
  echo "hb t+$(( $(date +%s) - START ))s stage=$(cat "$RUN/stage") disk=${disk}% ram=${ram}% quiet=${quiet}s out_mb=$(du -sm "$OUT" | cut -f1)"
  [ "$quiet" -gt 600 ] && echo "WARN no output for ${quiet}s"
  [ "$disk" -gt 90 ] && echo "WARN disk ${disk}%"
  [ "$ram" -gt 90 ] && echo "WARN ram ${ram}%"
done; }
heartbeat & HB=$!

publish() {  # always runs: results go out on success and on failure
  kill "$HB" 2>/dev/null || true
  echo RP_REPORT_BEGIN; grep -h '^PREP ' "$RUN/job.log" | sed 's/^PREP //' || true; echo RP_REPORT_END
  tar -cf "$W/artifact.tar" -C "$W" out run/job.log 2>/dev/null || tar -cf "$W/artifact.tar" -C "$W" run/job.log
  echo "ARTIFACT bytes=$(stat -c %s "$W/artifact.tar") sha256=$(sha256sum "$W/artifact.tar" | cut -d' ' -f1)"
  runpodctl send --code rpdln "$W/artifact.tar" > "$RUN/send.log" 2>&1 &
  local pid=$! code=""
  for _ in $(seq 30); do code=$(grep -oE 'rpdln[-0-9]+' "$RUN/send.log" | head -1 || true); [ -n "$code" ] && break; sleep 1; done
  echo "RP_ARTIFACT_CODE=$code"
  timeout 1800 tail --pid="$pid" -f /dev/null || echo "WARN artifact not received within 30 min"
}
trap publish EXIT

stage "boot python=$(python3 --version 2>&1) cpus=$(nproc) ram_gb=$(free -g | awk '/Mem:/{print $2}') disk_free_gb=$(df -BG --output=avail "$W" | tail -1 | tr -dc 0-9)"
stage install
timeout 600 pip install -q pyarrow pillow

# Each split gets its own timeout (about 3x the expected time); a timeout is logged and the rest still publishes.
prep() {  # prep <split> <shards> <pages>
  stage "$1"
  timeout 1500 python scripts/prepare_doclaynet.py --out "$OUT" --split "$1" --use "$2" --n "$3" --seed 0 --cache "$W/shards" \
    || echo "ERROR $1 failed or timed out (exit $?)"
}
cd "$W"
prep test 6 500
prep validation 4 200
prep train 12 500
stage pack
echo done > "$RUN/status"

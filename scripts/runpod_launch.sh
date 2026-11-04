#!/usr/bin/env bash
# Drive one RunPod job through the runpod-jobs `rp` wrapper, under a total spend cap with a ledger.
#
#   scripts/runpod_launch.sh [--dry-run] <name> <entry-script> <dest-dir> <file>...
#
# Ships <file>... to the pod inline in the start command (nothing is fetched before the dead-man's-switch
# is armed), runs <entry-script> there, pulls the artifact over the relay into <dest-dir>, terminates the
# pod and appends to the ledger. Configure by env: RP_COMPUTE_TYPE (CPU|GPU), RP_POD_IMAGE, RP_GPU_TYPE,
# RP_MAX_HOURLY_USD, RP_MAX_LIFETIME_SECS, RP_VCPU_COUNT, RP_CONTAINER_DISK_GB; TOTAL_CAP_USD (default 5);
# JOB_ENV ("A=1 B=2") is set for the entry script.
# Run it detached:  setsid nohup scripts/runpod_launch.sh ... > output/runpod/<name>.out 2>&1 &
# The API key is read by reference from ~/.runpod/config.toml (single-quoted apikey) and never printed.
set -euo pipefail

DRY=0; [ "${1:-}" = "--dry-run" ] && { DRY=1; shift; }
[ "$#" -ge 4 ] || { sed -n '2,12p' "$0" >&2; exit 2; }
NAME=$1; ENTRY=$2; DEST=$3; shift 3
FILES=("$@")

LEDGER=${LEDGER:-output/runpod/spend.jsonl}; CAP=${TOTAL_CAP_USD:-5}
HOURLY=${RP_MAX_HOURLY_USD:?set RP_MAX_HOURLY_USD}; LIFE=${RP_MAX_LIFETIME_SECS:?set RP_MAX_LIFETIME_SECS}
mkdir -p "$(dirname "$LEDGER")" "$DEST"; touch "$LEDGER"

spent=$(python3 -c "import json,sys; print(sum(json.loads(l)['usd'] for l in open('$LEDGER') if l.strip()))")
worst=$(python3 -c "print(round($HOURLY * $LIFE / 3600, 4))")
echo "ledger: spent=\$$spent worst-case-this-job=\$$worst cap=\$$CAP"
python3 -c "import sys; sys.exit(0 if $spent + $worst <= $CAP else 1)" || { echo "REFUSED: $spent + $worst exceeds the \$$CAP cap" >&2; exit 3; }
[ "$DRY" = 1 ] && { echo "dry run ok: would launch '$NAME' ($ENTRY) with ${#FILES[@]} files"; exit 0; }

export RUNPOD_API_KEY="$(awk -F"'" '/^apikey/{print $2}' ~/.runpod/config.toml)"
[ -n "$RUNPOD_API_KEY" ] || { echo "no apikey in ~/.runpod/config.toml" >&2; exit 4; }
export PATH="$HOME/.claude/skills/runpod-jobs/scripts:$PATH"
export RP_POD_NAME="syn-$NAME" RP_INTERRUPTIBLE=false RP_STATE_FILE="$PWD/output/runpod/.rp-state-$NAME"
export RP_JOB_CMD="mkdir -p /workspace && cd /workspace && echo $(tar czf - "${FILES[@]}" | base64 -w0) | base64 -d | tar xz && ${JOB_ENV:-} bash $ENTRY"

pod=""; hb_pid=""; t_start=$(date +%s)
cleanup() {
  [ -n "$hb_pid" ] && kill "$hb_pid" 2>/dev/null || true
  rp down || true
  runpodctl pod list 2>/dev/null | grep -q "syn-$NAME" && echo "WARNING: syn-$NAME still listed; terminate it in the console" || echo "verified: no syn-$NAME pod"
  hours=$(python3 -c "print(round(($(date +%s) - $t_start) / 3600, 4))")
  python3 - <<PY >> "$LEDGER"
import json
rate = float("${rate:-$HOURLY}")
print(json.dumps({"job": "$NAME", "pod": "${pod}", "hours": $hours, "usd_per_hr": rate, "usd": round($hours * rate, 4), "image": "${RP_POD_IMAGE:-}"}))
PY
}
trap cleanup EXIT INT TERM

pod=$(rp up | tail -1); echo "pod $pod"
rate=$(rp status | awk '{print $NF}'); echo "rate \$$rate/hr (cap \$$HOURLY)"

# Early signal: a stuck pull or bad bootstrap should show up in minutes, not at the lifetime ceiling.
seen=""
for _ in $(seq 48); do
  seen=$(rp logs --tail 200 2>/dev/null | grep -o 'STAGE [^"]*' | tail -1 || true)
  [ -n "$seen" ] && break; echo "boot: no STAGE line yet"; sleep 10
done
[ -n "$seen" ] || { echo "FATAL: no STAGE line after 8 min; tearing down" >&2; exit 5; }
echo "boot ok: $seen"

( while sleep 120; do echo "status: $(rp logs --tail 400 2>/dev/null | grep -o '\(STAGE\|hb\|WARN\|ERROR\|DOWNLOAD\)[^"]*' | tail -1)"; done ) & hb_pid=$!
rp relay-get "$DEST"
echo "DRIVER_DONE artifact in $DEST"

#!/usr/bin/env bash
# Pod-side GPU job: generate synthetic pages, train YOLOX-Tiny for a few steps, evaluate on synthetic and real pages,
# and report speed and memory so a full run can be sized. Started by scripts/runpod_launch.sh through rp.
# Env: SYN_SHA and RTOD_SHA (required, pinned commits), STEPS (100), BATCH (16), SIZE (640), DOCS (70),
# TEST_N (0): also score on this many real DocLayNet test pages (the SYN-7 sample is 500).
# Markers: STAGE, hb, WARN, ERROR, STAGE failed, MEASURE, TRAIN, REPORT, RP_REPORT_BEGIN/END, RP_ARTIFACT_CODE.
set -Eeuo pipefail
: "${SYN_SHA:?}" "${RTOD_SHA:?}"; STEPS=${STEPS:-100}; BATCH=${BATCH:-16}; SIZE=${SIZE:-640}; DOCS=${DOCS:-70}; TEST_N=${TEST_N:-0}
W=${W:-/workspace}; RUN=$W/run; mkdir -p "$RUN"
exec > >(tee -a "$RUN/job.log") 2>&1
START=$(date +%s); : > "$RUN/stage"

stage() { echo "$1" > "$RUN/stage"; echo "STAGE $1"; }
fail()  { echo "STAGE failed ($1; was: $(cat "$RUN/stage"))"; }
trap 'fail "line $LINENO"' ERR

heartbeat() { while sleep 60; do
  quiet=$(( $(date +%s) - $(stat -c %Y "$RUN/job.log") ))
  disk=$(df --output=pcent "$W" | tail -1 | tr -dc 0-9); ram=$(free | awk '/Mem:/{printf "%d", $3*100/$2}')
  gpu=$(nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits 2>/dev/null | tr -d ' ' || echo na)
  echo "hb t+$(( $(date +%s) - START ))s stage=$(cat "$RUN/stage") gpu(util%,memMiB)=$gpu disk=${disk}% ram=${ram}% quiet=${quiet}s"
  [ "$quiet" -gt 600 ] && echo "WARN no output for ${quiet}s"
  [ "$disk" -gt 90 ] && echo "WARN disk ${disk}%"
  [ "$ram" -gt 90 ] && echo "WARN ram ${ram}%"
done; }
heartbeat & HB=$!

publish() {  # always runs: results go out on success and on failure
  kill "$HB" 2>/dev/null || true
  echo RP_REPORT_BEGIN; cat "$RUN/train/report.json" 2>/dev/null || echo '{"report":"missing"}'; echo RP_REPORT_END
  tar -cf "$W/artifact.tar" -C "$W" run 2>/dev/null
  echo "ARTIFACT bytes=$(stat -c %s "$W/artifact.tar") sha256=$(sha256sum "$W/artifact.tar" | cut -d' ' -f1)"
  runpodctl send --code rpgpu "$W/artifact.tar" > "$RUN/send.log" 2>&1 &
  local pid=$! code=""
  for _ in $(seq 30); do code=$(grep -oE 'rpgpu[-0-9]+' "$RUN/send.log" | head -1 || true); [ -n "$code" ] && break; sleep 1; done
  echo "RP_ARTIFACT_CODE=$code"
  timeout 1800 tail --pid="$pid" -f /dev/null || echo "WARN artifact not received within 30 min"
}
trap publish EXIT

stage "boot $(nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>&1 | head -1) cpus=$(nproc) ram_gb=$(free -g | awk '/Mem:/{print $2}')"
command -v nvidia-smi >/dev/null || { echo "ERROR no nvidia-smi: not a GPU pod"; exit 3; }

stage install
# torch from the PyTorch index alone (CUDA 12.4 wheels, as the rtod project validated), everything else from PyPI alone.
# Long timeouts and retries: a slow community host timed out reading the nvidia wheels (2026-11-04). Progress stays on so a slow install is visible.
PIP="pip install --default-timeout 120 --retries 8 --progress-bar off"
timeout 1500 $PIP torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124
timeout 600 $PIP -q pyarrow pycocotools "rtod[torch,coco] @ git+https://github.com/leejianrong/real-time-object-detection@${RTOD_SHA}"
timeout 300 git clone -q https://github.com/leejianrong/synthetic-pdf-bench "$W/repo"
git -C "$W/repo" checkout -q "$SYN_SHA"
timeout 600 $PIP -q "$W/repo"

stage preflight  # a real CUDA op, not just is_available()
python - <<'PY'
import torch
assert torch.cuda.is_available(), "torch sees no CUDA device"
x = torch.randn(512, 512, device="cuda"); y = (x @ x).sum().item()
print(f"preflight ok torch={torch.__version__} cuda={torch.version.cuda} device={torch.cuda.get_device_name(0)} y={y:.1f}")
PY

stage generate
cd "$W/repo"
R=(); for f in data/recipes/canonical/*.json; do R+=(--recipe "$f"); done
t0=$(date +%s)
timeout 900 python -m synthetic_pdf_bench.cli.generate --output-root "$W/syn" --count "$DOCS" "${R[@]}" --variants random standard \
  --workers "$(nproc)" --splits train=0.85 val=0.15 --split-by recipe > "$RUN/generate.log" 2>&1
timeout 300 python -m synthetic_pdf_bench.cli.generate export-coco "$W/syn"
echo "MEASURE generate docs=$DOCS secs=$(( $(date +%s) - t0 )) workers=$(nproc) pages=$(grep -c '"file_name"' "$W/syn/coco_train.json")+$(grep -c '"file_name"' "$W/syn/coco_val.json")"

stage real-val
timeout 600 python scripts/prepare_doclaynet.py --out "$W/real" --split validation --use 2 --n 50 --seed 0 --cache "$W/shards"

ALSO=(--also-eval "$W/real:$W/real/coco_validation.json")
if [ "$TEST_N" -gt 0 ]; then
  stage real-test
  timeout 1500 python scripts/prepare_doclaynet.py --out "$W/real" --split test --use 6 --n "$TEST_N" --seed 0 --cache "$W/shards"
  ALSO+=(--also-eval "$W/real:$W/real/coco_test.json")
fi

stage train
timeout $(( STEPS * 10 + 900 )) python scripts/train_layout.py --root "$W/syn" --train-json "$W/syn/coco_train.json" --val-json "$W/syn/coco_val.json" \
  "${ALSO[@]}" --out "$RUN/train" --steps "$STEPS" --batch "$BATCH" --size "$SIZE" --workers 8 --max-val-images 50
stage done

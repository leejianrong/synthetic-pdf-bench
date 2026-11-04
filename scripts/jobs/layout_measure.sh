#!/usr/bin/env bash
# Pod-side GPU job: generate synthetic pages, train YOLOX-Tiny for a few steps, evaluate on synthetic and real pages,
# and report speed and memory so a full run can be sized. Started by scripts/runpod_launch.sh through rp.
# Env: SYN_SHA and RTOD_SHA (required, pinned commits), STEPS (100), BATCH (16), SIZE (640), DOCS (70),
# TEST_N (0): also score on this many real DocLayNet test pages (the SYN-7 sample is 500).
# SYN-7 arms: REAL_N (0) real train pages, ARMS (comma list, empty = one synthetic run) from `synthetic,real,finetune,mix`, STEPS for
# synthetic, REAL_STEPS (3000) for real and finetune, MIX_STEPS (4000). `finetune` starts from the `synthetic` checkpoint.
# SYN-27: SCALE ("2000:3000,5000:6000,10000:10000" = real pages:steps) and SEEDS ("0,1") train real-only on seeded nested subsets of one
# real sample (the largest size), once per seed, and score each on synthetic val, real val and real test.
# Markers: STAGE, hb, WARN, ERROR, STAGE failed, MEASURE, TRAIN, REPORT, RP_REPORT_BEGIN/END, RP_ARTIFACT_CODE.
set -Eeuo pipefail
: "${SYN_SHA:?}" "${RTOD_SHA:?}"; STEPS=${STEPS:-100}; BATCH=${BATCH:-16}; SIZE=${SIZE:-640}; DOCS=${DOCS:-70}; TEST_N=${TEST_N:-0}
REAL_N=${REAL_N:-0}; ARMS=${ARMS:-}; SCALE=${SCALE:-}; SEEDS=${SEEDS:-0}; REAL_STEPS=${REAL_STEPS:-3000}; MIX_STEPS=${MIX_STEPS:-4000}
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
  echo RP_REPORT_BEGIN
  for f in "$RUN"/*/report.json; do echo "ARM_REPORT $f"; cat "$f"; echo; done 2>/dev/null || true
  echo RP_REPORT_END
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
timeout 900 python -m synthetic_pdf_bench.cli.generate --output-root "$W/syn" --count "$DOCS" "${R[@]}" --variants random standard structured \
  --workers "$(nproc)" --splits train=0.85 val=0.15 --split-by recipe > "$RUN/generate.log" 2>&1
timeout 300 python -m synthetic_pdf_bench.cli.generate export-coco "$W/syn"
echo "MEASURE generate docs=$DOCS secs=$(( $(date +%s) - t0 )) workers=$(nproc) pages=$(grep -c '"file_name"' "$W/syn/coco_train.json")+$(grep -c '"file_name"' "$W/syn/coco_val.json")"

stage real-val
timeout 600 python scripts/prepare_doclaynet.py --out "$W/real" --split validation --use 2 --n 50 --seed 0 --cache "$W/shards"

if [ "$TEST_N" -gt 0 ]; then
  stage real-test
  timeout 1500 python scripts/prepare_doclaynet.py --out "$W/real" --split test --use 6 --n "$TEST_N" --seed 0 --cache "$W/shards"
fi
if [ -n "$SCALE" ]; then REAL_N=$(tr ',' '\n' <<< "$SCALE" | cut -d: -f1 | sort -n | tail -1); fi
if [ "$REAL_N" -gt 0 ]; then
  stage real-train
  timeout 2400 python scripts/prepare_doclaynet.py --out "$W/real" --split train --use 24 --n "$REAL_N" --seed 0 --cache "$W/shards"
fi

# arm NAME STEPS ROOT TRAIN_JSON VAL_JSON [train_layout args...]: train, then score on synthetic val and the real pages.
arm() {
  local name=$1 steps=$2 root=$3 tj=$4 vj=$5; shift 5
  stage "arm-$name"
  local ev=(--also-eval "$W/syn:$W/syn/coco_val.json" --also-eval "$W/real:$W/real/coco_validation.json")
  if [ "$TEST_N" -gt 0 ]; then ev+=(--also-eval "$W/real:$W/real/coco_test.json"); fi
  timeout $(( steps * 10 + 900 )) python scripts/train_layout.py --root "$root" --train-json "$tj" --val-json "$vj" "${ev[@]}" \
    --out "$RUN/$name" --steps "$steps" --batch "$BATCH" --size "$SIZE" --workers 8 --max-val-images 50 "$@"
  echo "ARM $name $(python -c "import json; r = json.load(open('$RUN/$name/report.json')); print({k: round(v['map50_95'], 4) for k, v in r['also'].items()})")"
}

subset() {  # subset N: coco_train_N.json holds N seeded random pages of coco_train.json
  python - "$W/real/coco_train.json" "$1" <<'PY'
import json, random, sys
src, n = sys.argv[1], int(sys.argv[2])
coco = json.load(open(src))
keep = {i["id"] for i in random.Random(0).sample(coco["images"], min(n, len(coco["images"])))}
coco["images"] = [i for i in coco["images"] if i["id"] in keep]
coco["annotations"] = [a for a in coco["annotations"] if a["image_id"] in keep]
json.dump(coco, open(src.replace(".json", f"_{n}.json"), "w"))
print(f"SUBSET {n} images={len(coco['images'])} boxes={len(coco['annotations'])}")
PY
}

SYN=("$W/syn" "$W/syn/coco_train.json" "$W/syn/coco_val.json")
REAL=("$W/real" "$W/real/coco_train.json" "$W/real/coco_validation.json")
if [ -z "$ARMS$SCALE" ]; then arm train "$STEPS" "${SYN[@]}"; fi
for a in ${ARMS//,/ }; do
  case $a in
    synthetic) arm synthetic "$STEPS" "${SYN[@]}" ;;
    real) arm real "$REAL_STEPS" "${REAL[@]}" --augment ;;
    finetune) arm finetune "$REAL_STEPS" "${REAL[@]}" --augment --weights "$RUN/synthetic/checkpoint.pt" --lr 0.002 ;;
    mix) arm mix "$MIX_STEPS" "${REAL[@]}" --augment --also-train "$W/syn:$W/syn/coco_train.json:0.5" ;;
    *) echo "ERROR unknown arm $a"; exit 2 ;;
  esac
done
for spec in ${SCALE//,/ }; do
  n=${spec%%:*}; steps=${spec##*:}; subset "$n"
  for seed in ${SEEDS//,/ }; do arm "real-$n-s$seed" "$steps" "$W/real" "$W/real/coco_train_$n.json" "$W/real/coco_validation.json" --augment --seed "$seed"; done
done
stage done

#!/usr/bin/env bash
# Pod-side CPU job (SYN-4): generate a synthetic dataset, run each parser over it with `synthetic-pdf-bench benchmark`, publish the scores.
# Env: SYN_SHA (required), DOCS (30), PARSERS (comma list of scripts/parsers/<name>.py), DOC_TIMEOUT (300 s per document).
# Markers: STAGE, hb, WARN, ERROR, STAGE failed, MEASURE, PARSER_REPORT, RP_REPORT_BEGIN/END, RP_ARTIFACT_CODE.
set -Eeuo pipefail
: "${SYN_SHA:?}"; DOCS=${DOCS:-30}; PARSERS=${PARSERS:-pymupdf_text,pypdf_text,docling_md}; DOC_TIMEOUT=${DOC_TIMEOUT:-300}
W=${W:-/workspace}; RUN=$W/run; mkdir -p "$RUN"
exec > >(tee -a "$RUN/job.log") 2>&1
START=$(date +%s); : > "$RUN/stage"

stage() { echo "$1" > "$RUN/stage"; echo "STAGE $1"; }
fail()  { echo "STAGE failed ($1; was: $(cat "$RUN/stage"))"; }
trap 'fail "line $LINENO"' ERR

heartbeat() { while sleep 60; do
  quiet=$(( $(date +%s) - $(stat -c %Y "$RUN/job.log") ))
  disk=$(df --output=pcent "$W" | tail -1 | tr -dc 0-9); ram=$(free | awk '/Mem:/{printf "%d", $3*100/$2}')
  echo "hb t+$(( $(date +%s) - START ))s stage=$(cat "$RUN/stage") disk=${disk}% ram=${ram}% quiet=${quiet}s"
  [ "$quiet" -gt 900 ] && echo "WARN no output for ${quiet}s"
  [ "$disk" -gt 90 ] && echo "WARN disk ${disk}%"
  [ "$ram" -gt 90 ] && echo "WARN ram ${ram}%"
done; }
heartbeat & HB=$!

publish() {  # always runs: results go out on success and on failure
  kill "$HB" 2>/dev/null || true
  echo RP_REPORT_BEGIN
  for f in "$RUN"/*/benchmark.json; do echo "PARSER_REPORT $f"; cat "$f"; echo; done 2>/dev/null || true
  grep -h '^MEASURE ' "$RUN/job.log" || true
  echo RP_REPORT_END
  tar -cf "$W/artifact.tar" --exclude=predictions -C "$W" run 2>/dev/null || tar -cf "$W/artifact.tar" -C "$W" run/job.log
  echo "ARTIFACT bytes=$(stat -c %s "$W/artifact.tar") sha256=$(sha256sum "$W/artifact.tar" | cut -d' ' -f1)"
  runpodctl send --code rppar "$W/artifact.tar" > "$RUN/send.log" 2>&1 &
  local pid=$! code=""
  for _ in $(seq 30); do code=$(grep -oE 'rppar[-0-9]+' "$RUN/send.log" | head -1 || true); [ -n "$code" ] && break; sleep 1; done
  echo "RP_ARTIFACT_CODE=$code"
  timeout 1800 tail --pid="$pid" -f /dev/null || echo "WARN artifact not received within 30 min"
}
trap publish EXIT

stage "boot python=$(python3 --version 2>&1) cpus=$(nproc) ram_gb=$(free -g | awk '/Mem:/{print $2}')"
stage install
PIP="pip install --default-timeout 120 --retries 8 --progress-bar off"
timeout 1500 $PIP torch torchvision --index-url https://download.pytorch.org/whl/cpu  # CPU wheels: no CUDA download
timeout 1200 $PIP -q docling pypdf
timeout 300 git clone -q https://github.com/leejianrong/synthetic-pdf-bench "$W/repo"
git -C "$W/repo" checkout -q "$SYN_SHA"
timeout 600 $PIP -q "$W/repo"

stage generate
cd "$W/repo"
R=(); for f in data/recipes/canonical/*.json; do R+=(--recipe "$f"); done
timeout 900 python -m synthetic_pdf_bench.cli.generate --output-root "$W/syn" --count "$DOCS" "${R[@]}" --variants standard structured \
  --workers "$(nproc)" > "$RUN/generate.log" 2>&1

for name in dummy ${PARSERS//,/ }; do
  stage "parser-$name"
  mkdir -p "$RUN/$name"; t0=$(date +%s)
  if [ "$name" = dummy ]; then cmd=dummy; else cmd="python scripts/parsers/$name.py {pdf} {out}"; fi
  timeout 5400 python -m synthetic_pdf_bench.cli.generate benchmark "$W/syn" --parser "$cmd" --output "$RUN/$name" --timeout "$DOC_TIMEOUT" > "$RUN/$name/bench.log" 2>&1 \
    || echo "ERROR parser $name failed or timed out (exit $?)"
  echo "MEASURE parser=$name docs=$DOCS secs=$(( $(date +%s) - t0 )) cpus=$(nproc)"
done
stage done

#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --cases DIRECTORY --out NEW_DIRECTORY [--fixture-mode MODE] [--omit-request-id ID] [--deadline SECONDS]" >&2
  exit 2
}

CASES=""
OUT=""
EXTRA=()
while (($#)); do
  case "$1" in
    --cases) [[ $# -ge 2 ]] || usage; CASES="$2"; shift 2 ;;
    --out) [[ $# -ge 2 ]] || usage; OUT="$2"; shift 2 ;;
    --fixture-mode|--omit-request-id|--deadline)
      [[ $# -ge 2 ]] || usage; EXTRA+=("$1" "$2"); shift 2 ;;
    *) usage ;;
  esac
done
[[ -n "$CASES" && -n "$OUT" ]] || usage

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CASES_ABS="$(cd "$CASES" && pwd -P)"
if [[ -e "$OUT" ]]; then
  [[ -d "$OUT" && -z "$(find "$OUT" -mindepth 1 -maxdepth 1 -print -quit)" ]] || {
    echo "output directory must be new or empty" >&2
    exit 2
  }
  OUT_ABS="$(cd "$OUT" && pwd -P)"
else
  mkdir -p "$OUT"
  OUT_ABS="$(cd "$OUT" && pwd -P)"
fi
IMAGE="$(tr -d '[:space:]' < "$SCRIPT_DIR/zap-image.txt")"
[[ "$IMAGE" == *@sha256:* ]] || { echo "zap-image.txt must pin a digest" >&2; exit 2; }
TESTED_COMMIT_SHA="${REGRESSION_TESTED_COMMIT_SHA:-}"
if [[ -z "$TESTED_COMMIT_SHA" ]]; then
  TESTED_COMMIT_SHA="$(git -C "$SCRIPT_DIR" rev-parse HEAD 2>/dev/null || true)"
fi
TESTED_COMMIT_SHA="${TESTED_COMMIT_SHA:-local}"
RUNNER_ARGS=(--cases /workspace/cases --out /zap/wrk/output)
if ((${#EXTRA[@]})); then
  RUNNER_ARGS+=("${EXTRA[@]}")
fi

docker run --rm --network none --hostname localhost \
  --user "$(id -u):$(id -g)" \
  --env "HOME=/tmp/zap-regression-home" \
  --env "ZAP_IMAGE_DIGEST=${IMAGE#*@}" \
  --env "TESTED_COMMIT_SHA=$TESTED_COMMIT_SHA" \
  --env "PULL_REQUEST_HEAD_SHA=${REGRESSION_PR_HEAD_SHA:-}" \
  --mount "type=bind,src=$SCRIPT_DIR,dst=/workspace/security,readonly" \
  --mount "type=bind,src=$CASES_ABS,dst=/workspace/cases,readonly" \
  --mount "type=bind,src=$OUT_ABS,dst=/zap/wrk/output" \
  "$IMAGE" \
  python3 /workspace/security/run_zap_suite.py "${RUNNER_ARGS[@]}"

#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --cases DIRECTORY --out NEW_DIRECTORY --product-source DIRECTORY [--variant MODE] [--fault-mode MODE] [--omit-request-id ID] [--deadline SECONDS] [--retain-native-message]" >&2
  exit 2
}

CASES=""
OUT=""
SOURCE=""
EXTRA=()
while (($#)); do
  case "$1" in
    --cases) [[ $# -ge 2 ]] || usage; CASES="$2"; shift 2 ;;
    --out) [[ $# -ge 2 ]] || usage; OUT="$2"; shift 2 ;;
    --product-source) [[ $# -ge 2 ]] || usage; SOURCE="$2"; shift 2 ;;
    --variant|--fault-mode|--omit-request-id|--deadline)
      [[ $# -ge 2 ]] || usage; EXTRA+=("$1" "$2"); shift 2 ;;
    --retain-native-message) EXTRA+=("$1"); shift ;;
    *) usage ;;
  esac
done
[[ -n "$CASES" && -n "$OUT" && -n "$SOURCE" ]] || usage

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
TESTED_COMMIT_SHA="${REGRESSION_TESTED_COMMIT_SHA:-}"
if [[ -z "$TESTED_COMMIT_SHA" ]]; then
  TESTED_COMMIT_SHA="$(git -C "$SCRIPT_DIR" rev-parse HEAD 2>/dev/null || true)"
fi
export TESTED_COMMIT_SHA="${TESTED_COMMIT_SHA:-local}"
export PULL_REQUEST_HEAD_SHA="${REGRESSION_PR_HEAD_SHA:-}"

exec python3 "$SCRIPT_DIR/run_zap_product_suite.py" \
  --cases "$CASES" --out "$OUT" --product-source "$SOURCE" "${EXTRA[@]}"

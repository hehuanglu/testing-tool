#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 4 && "$1" == "--mode" && "$3" == "--out" ]] || {
  echo "usage: $0 --mode good|bad --out NEW_DIRECTORY" >&2; exit 2;
}
MODE="$2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SECURITY_DIR="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
OUT="$4"; mkdir "$OUT"; OUT_ABS="$(cd "$OUT" && pwd -P)"
IMAGE="$(tr -d '[:space:]' < "$SECURITY_DIR/zap-image.txt")"
EXPECTED="secret-canary-good-token"
SUPPLIED="$EXPECTED"
[[ "$MODE" == "good" ]] || SUPPLIED="secret-canary-expired-token"
docker run --rm --network none --hostname localhost --user "$(id -u):$(id -g)" \
  --env HOME=/tmp/zap-bearer-home \
  --env EXPECTED_BEARER_TOKEN="$EXPECTED" --env BEARER_TOKEN="$SUPPLIED" \
  --mount "type=bind,src=$SCRIPT_DIR,dst=/workspace/experiment,readonly" \
  --mount "type=bind,src=$OUT_ABS,dst=/zap/wrk/output" \
  "$IMAGE" python3 /workspace/experiment/run.py --mode "$MODE" --out /zap/wrk/output/result

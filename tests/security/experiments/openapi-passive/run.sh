#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 4 && "$1" == "--mode" && "$3" == "--out" ]] || {
  echo "usage: $0 --mode good|missing-route --out NEW_DIRECTORY" >&2; exit 2;
}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SECURITY_DIR="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
OUT="$4"; mkdir "$OUT"; OUT_ABS="$(cd "$OUT" && pwd -P)"
IMAGE="$(tr -d '[:space:]' < "$SECURITY_DIR/zap-image.txt")"
docker run --rm --network none --hostname localhost --user "$(id -u):$(id -g)" \
  --env HOME=/tmp/zap-openapi-home \
  --mount "type=bind,src=$SCRIPT_DIR,dst=/workspace/experiment,readonly" \
  --mount "type=bind,src=$OUT_ABS,dst=/zap/wrk/output" \
  "$IMAGE" python3 /workspace/experiment/run.py --mode "$2" --out /zap/wrk/output/result

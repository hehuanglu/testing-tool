#!/usr/bin/env bash
set -euo pipefail
trial="$1"
trial_path="$OUTPUT/$SCENARIO/$trial"
mkdir -p "$OUTPUT/$SCENARIO"
nohup python "$RUNNER" --implementation af --scenario "$SCENARIO" --out "$OUTPUT" \
  --phase fixture --trial "$trial" </dev/null >"$OUTPUT/$SCENARIO/$trial-fixture.log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT
for ((attempt = 0; attempt < 100; attempt++)); do
  if [[ -f "$trial_path/ready.json" ]]; then
    break
  fi
  kill -0 "$pid"
  sleep 0.1
done
python "$RUNNER" --implementation af --scenario "$SCENARIO" --out "$OUTPUT" \
  --phase ready-action --trial "$trial"
trap - EXIT

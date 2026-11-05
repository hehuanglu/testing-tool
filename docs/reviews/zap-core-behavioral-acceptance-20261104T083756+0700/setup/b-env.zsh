export EPISODE='/Users/hahoangloc/Working/testing tool/docs/reviews/zap-core-behavioral-acceptance-20261104T083756+0700'
export ZAP_PYTHON='/Users/hahoangloc/Working/testing tool/zap-product-assessment/.venv/bin/python'
export ASSESSMENT_ROOT='/Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment'
export PYTHONPATH="$ASSESSMENT_ROOT/src:$ASSESSMENT_ROOT/tests"
field() { "$ZAP_PYTHON" -B -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$EPISODE/manifest.json" "$1"; }
export STATE="$(field stateDir)" REGISTRY="$(field registryDir)" AID="$(field assessmentId)"
export BEFORE='2026-11-04T23:59:59Z' AFTER='2026-11-05T00:00:00Z'
cap() { "$ZAP_PYTHON" -B "$EPISODE/setup/capture.py" "$@"; }
cli() { local label="$1" cmd="$2"; shift 2; cap "$label" "$ZAP_PYTHON" -B -m zap_assessment.product_cli scope "$cmd" --state-dir "$STATE" "$@"; }
gen() { jq -er .generationId "$STATE/current.json"; }
toolb() { local label="$1"; shift; cap "$label" "$ZAP_PYTHON" -B "$EPISODE/setup/b-observe.py" "$@"; }
record() { "$ZAP_PYTHON" -B "$EPISODE/setup/b-decision.py" "$@"; }
merge_b() { local label="$1" packet="$2"; cli "$label" state-merge --expected-generation "$(gen)" --commit-id "$label" --packet "$packet" --result "$EPISODE/setup/$label-result.json"; }
commit_b() { local label="$1" inputs="$2"; cli "$label" state-commit --expected-generation "$(jq -er .generationId "$inputs")" --commit-id "$label" --run "$(jq -er .runRef "$inputs")" --operator "$(jq -er .operatorRef "$inputs")"; }

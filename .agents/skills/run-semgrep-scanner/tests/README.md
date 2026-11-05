# Representative fixtures, not product assessments

## Regression scope

Fixtures use synthetic placeholders, never actual credentials. Broad logger/receiver/DTO/return/lifecycle/criteria inventory detectors intentionally may match fixed password text, Map/Set.delete, services, response DTOs, DB configuration returns, login MinLength, and prior guards. Positives are candidate shapes rather than vulnerabilities. Aliases/custom wrappers/inherited fields outside shapes are blind spots, not safe-control evidence. Avoid blanket exclusions for literals/config/response/service code.

The `config-nginx-csp-scope-review-v2` detector inventories server/header/include declarations following a six-configuration probe. CSP-present servers still need effective-scope/inheritance review; multi-server, child add_header, always, and missing includes remain responsibilities. Historical IDs/results remain unchanged.

## Helper checks

These standard-library commands need no engine/network:

```sh
python3 -m unittest discover -s "$SKILL_DIR/tests" -p 'test_*.py' -v
python3 "$SKILL_DIR/scripts/check_report_links.py" "$SKILL_DIR/examples/reporting/RUN.example.json" "$SKILL_DIR/examples/reporting/ALERTS.example.json"
```

Synthetic records exercise native/manual/mixed/multiple-round, unreadable/partial/zero-scanned, IDs/references/counts/source-state, privacy, and non-overwrite behavior. They check bookkeeping, rather than evidence/verdict truth. Source/rule/path/ignore changes require actual review; disappearing matches do not establish fixes.

## Engine fixtures

[run_fixtures.py](run_fixtures.py) stages synthetic fixtures under private `cases/`, extracts actual annotation-selected bundled rules, scans each file, and compares **all** `(check_id, path, start.line)` positions plus negative positions/errors/scanned files. It does not download dependencies/runtime. Inspect its help and actual engine help first. Use `--work-dir <new-private-dir>` and, where required, a verified `--prefix-json '["sandbox-exec","-f","/absolute/verified-network-deny.sb"]'`. A configured prefix alone does not establish network denial. Private outputs are not product handoffs.

`compose.prod.yaml` and `outside-language.py` are path/language limitations with empty scanned lists, rather than semantic negative passes. The original five representative fixtures expected eight positives and seven negative positions; use the runner for the expanded regression set rather than treating old counts as current totals.

The initial representatives cover local SQL versus bound values, HTML sink versus text rendering, synthetic literal/fallback JWT secrets versus getters/member/unrelated keys, ID lookups including prior guards, and privileged true/false plus alternate Compose basenames. Guard-before-lookup still matches; unmatched slugs do not establish authorization.

Resolve SKILL_DIR from the loaded skill. Prepare private settings/logs, disabled metrics/version checks, local configurations, and required verified isolation under [operations](../references/semgrep-operations.md). Do not use remote --validate or install parsers/engines just to pass checks. Extract actual bundled rule blocks into temporary configurations without altering matchers; do not maintain duplicate test libraries.

Semgrep 1.176.0 may ignore tests/fixtures by default and exit 0 with no scanned files. Stage only synthetic content to private `cases/<track>/`, preserving basenames/content and recording mappings back to tests/fixtures. This does not change product ignores/rule.paths or establish full-project equivalence.

Example after selecting actual TRACK/RULE_CONFIG and adding any verified guard prefix:

```sh
mkdir "$SCAN_WORK/$TRACK"
semgrep scan --oss-only --config "$RULE_CONFIG" \
  --metrics=off --disable-version-check --strict --no-rewrite-rule-ids \
  --verbose --time --json-output "$SCAN_WORK/$TRACK/native.json" \
  "$SCAN_WORK/cases/$TRACK" \
  > "$SCAN_WORK/$TRACK/stdout.log" 2> "$SCAN_WORK/$TRACK/stderr.log"
SCAN_EXIT=$?
```

Read actual exits/errors/skips/timeouts/results. ruleid/ok annotations apply to the next code line for the specified rule. Compare complete positions, rather than counts alone. The getter config.getOrThrow("JWT_SIGNING_KEY") remains a negative regression against accidental nested-string matches, with literal ||/?? fallback positives.

Alternate Compose files outside rule paths remain inventory gaps even when paths.skipped is empty; report actual selection/log observations without invented counters. Native --test with adjacent same-basename rule/fixtures is optional when exact direct scanning already verifies behavior. New matcher fixes need meaningful regressions; message/metadata-only changes do not automatically require every rule's semantic suite. [Validation](../references/validation.md) records historical results and limitations.

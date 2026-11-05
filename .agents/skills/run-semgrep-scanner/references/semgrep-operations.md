# Operate local Semgrep

## Preparation

Resolve `SKILL_DIR` from the loaded SKILL.md. Discover `PRODUCT_DIR`, source roots, and `RULES_FILE`; do not assume another product's layout. Use an installed binary and verify actual help/version. Missing CLI means unexecuted work, rather than an implied scan. Git/Python are needed only for operations using them.

Create private settings/log/raw storage outside source targets and Git. Adapt these macOS/Linux examples to the platform and replace paths before execution:

```sh
SKILL_DIR='/absolute/path/to/run-semgrep-scanner'
PRODUCT_DIR='/absolute/path/to/product'
SOURCE_DIR='/absolute/path/to/product/source-in-scope'
RULES_FILE="$SKILL_DIR/rules/be-public-static.yml"
umask 077
SCAN_WORK=$(mktemp -d "${TMPDIR:-/tmp}/semgrep-work.XXXXXXXX")
export SEMGREP_SETTINGS_FILE="$SCAN_WORK/settings.yml"
export SEMGREP_VERSION_CACHE_PATH="$SCAN_WORK/version-cache"
export SEMGREP_LOG_FILE="$SCAN_WORK/semgrep.log"
export SEMGREP_SEND_METRICS=off
export SEMGREP_ENABLE_VERSION_CHECK=0
export SEMGREP_APP_TOKEN=''
semgrep --version
semgrep scan --help
```

These are process-local settings; preserve existing login settings. Do not dump environments containing credentials. Help/version is not a scan or readiness certification.

## Privacy and network

Use inspected local rule files. Do not use `--config auto`, Registry IDs, URLs, `semgrep ci`, login, publish, or URL output. Disabled metrics/version checks, isolated settings, and empty tokens reduce automatic connections but **do not block networking**. Mandatory offline work requires verified isolation; report a blocker if unavailable rather than weakening the requirement.

On macOS, when available, use verified `sandbox-exec` prefixes for help/version, lint, tests, and scans. Verify denial with a non-product loopback probe that succeeds without the guard and fails with it:

```sh
printf '(version 1)\n(allow default)\n(deny network*)\n' > "$SCAN_WORK/network-deny.sb"
sandbox-exec -f "$SCAN_WORK/network-deny.sb" semgrep --version
```

Use suitable verified existing isolation on Linux/Windows when required. Do not assume a Semgrep flag blocks networking, provision Docker/VMs, or change system firewalls independently. Missing sandbox-exec limits that isolation method, rather than Semgrep source analysis itself.

## Purposeful rounds

Under the [sequential workflow](sequential-track-workflow.md), collect/read/review the current track before executing another. Multiple configurations/roots may serve one track; cross-track combination requires the user's request. Private round output differs from stable per-track handoff files.

After verifying rules/targets, use a new output directory per round. Add a verified guard prefix when required:

```sh
mkdir "$SCAN_WORK/round-01"
cd "$PRODUCT_DIR"
semgrep scan --oss-only \
  --config "$RULES_FILE" \
  --metrics=off --disable-version-check --strict --no-rewrite-rule-ids \
  --verbose --time \
  --json-output "$SCAN_WORK/round-01/native.json" \
  "$SOURCE_DIR" \
  > "$SCAN_WORK/round-01/stdout.log" 2> "$SCAN_WORK/round-01/stderr.log"
SCAN_EXIT=$?
```

Capture the process exit immediately, rather than a parser/pipe/cat exit. Findings may coexist with exit 0; `--error` changes exit-1 meaning. Interpret exit with actual help/command, JSON, and stderr. Nonzero does not automatically mean a product finding; zero does not mean clean.

Repeat local configs/roots or add justified includes/excludes within scope. There is no mandatory `.env*`/test exclusion: use scope/privacy needs without printing secrets. Explain relevant binary/generated/vendor exclusions.

`--include` does not override all Git/Semgrep ignores or rule `paths`. `--no-git-ignore` affects Git filtering only. Diagnose version-specific filtering before narrow rescans or private copies with explicit path mappings; preserve repository ignores. Copies/path changes may alter rule applicability and are not automatically equivalent to full projects.

Use supported `--dataflow-traces` when needed, without claiming complete cross-file/caller coverage. Choose timeouts/thresholds/jobs for actual resources and rounds, rather than fixed unlimited or 30-minute defaults.

## Read actual results

### Optional round collector

[record_round.py](../scripts/record_round.py) executes argv without a shell and records timing/exit/native JSON. After help, rule/target selection, and the RUN checkpoint, prepare a private [specification](../examples/reporting/round-spec.example.json), replacing placeholders. Use a fresh output directory outside all targets. Include `{native_json}` exactly once as the `--json-output` value; prepend a verified guard if applicable. The helper does not provision or verify isolation.

```sh
python3 "$SKILL_DIR/scripts/record_round.py" --spec "$SCAN_WORK/round-spec.json" --output-dir "$SCAN_WORK/round-02"
```

Record actual cwd/targets/privacy/rules/exclusions. `redact_values` identifies sensitive literals, including paths/positional arguments. The helper additionally redacts common secret-shaped assignments/flags, but heuristics cannot guarantee all secrets; never pass real credentials on argv. Spec/native/stdout/stderr remain private and may contain sensitive source. Do not print them by default. `round.json` omits matched lines, interpolated native messages, error text, and environment dumps while retaining private-raw indexes/references.

Helper success means collection, not scan success; use `round.exit_code`. Record observed version/engine/results/errors/scanned/skipped entries and count provenance. Requested engine differs from actual. Without a verified version-specific log adapter, log-only/loaded/executed counts remain null; log wording and `time.rules` do not establish coverage. Unknown output/counts remain null. Zero scanned is diagnostic, not clean. Status stays null and finding IDs empty until review. `review_groups` groups native locations for reading, rather than vulnerabilities; tester review determines shared callers/controls/root causes. Merge reviewed records into RUN; internal round/raw files are not additional handoffs.

[report_records.py](../scripts/report_records.py) supports `init <new-dir> --assessment-id <id>` and `question Q-01 --track-id be-input --base-id BE-IN-01`. It does not overwrite files or complete draft decisions. [check_report_links.py](../scripts/check_report_links.py) reads the two reports and checks known links/provenance/counts without editing or verifying evidence truth.

Inspect actual version-dependent JSON/log fields: `results`, `errors`, `paths.scanned`, `paths.skipped`, `skipped_rules`, `time`, engine/version. Missing fields remain unknown/null. An empty errors array means only what the inspected output establishes.

Distinguish configured/valid/loaded/executed rules; candidate/scanned/skipped files; parse errors/invalid rules/timeouts/empty targets/unsupported languages/crashes/findings; and started/process-ended/readable-output/question-answered states. Reading 85 configurations does not establish all rules executed on every target. Timing rule lists are not execution counts. A “Partially analyzed” heading with `<none>` is not a parse error.

Round completed requires valid output and no unresolved error preventing its purpose. Record partial/blocked as appropriate and retain usable findings even when another part failed.

## Parsing, local metachecks, and tests

Ordinary scans parse rules; inspect actual errors rather than blindly invoking `--validate`, which may fetch remote `p/semgrep-rule-lints` in some versions. If parse-only offline checking is necessary, inspect the installed semgrep-core help and supported local functionality; its CLI is version-specific, rather than a fixed skill dependency.

[offline-rule-lints.yml](offline-rule-lints.yml) checks only `fix`/`fix-regex`, not full semantics. Scan selected rules with the same local OSS/privacy/strict/output options and that config. Metacheck findings are not product findings. Do not use `--autofix` or silently change semantics to pass.

For new/changed rules, put representative matching/nonmatching fixtures beside rules with matching basenames in a separate test area. Use language-appropriate `ruleid:` and `ok:` annotations. Run supported `semgrep scan --test /local/rule-tests --oss-only --metrics=off --disable-version-check` with isolated settings/required guard and inspect actual counts/errors. Diagnose harness/version problems; direct fixture scanning and exact-location comparison is an acceptable explicitly documented alternative. Parsing or unexecuted tests do not establish detector correctness. See [rules/triage](rules-and-triage.md) and [fixtures](../tests/README.md).

## Continuation and retesting

Each round retains separate output, questions, command, source version, and results. After interruption, inspect prior process/output before retrying; reconciled read-only scans may be rerun as new rounds. Record source-state IDs and reconciled work. Retest affected source/rules against changes and control context. Missing matches caused by ignores/filters/rule/engine changes do not establish fixes. Preserve historical native output and reports, continue feasible independent work, and use the [responsibility loop](responsibility-loop.md) before handoff.

---
name: run-semgrep-scan
description: Run five authorized local Semgrep OSS source tracks from a product checkout, with frozen per-run results and read-only verification; no source or evidence upload.
---

# Run Semgrep Scan

Use Vietnamese for researcher-facing output. The input is this repository's product path (repository root or `finalsource/`). Read `AGENTS.md`, `PROJECT_CONTEXT.md` and `docs/00-context/sources/CONNECTED-SOURCES.md` when present. The bundled runner needs only Python 3, an installed local Semgrep OSS CLI, macOS `sandbox-exec`, Git and the product layout `finalsource/fe`, `finalsource/be`, `finalsource/compose.yaml`. No ZAP contract, environment profile, codebook or historical evidence is required. A product path alone is not scan authorization: use `--authorized-local` only for researcher-approved tracks and source roots.

## Tracks and commands

Default order is `be-public-static` (`finalsource/be`), `fe-public-static` (`finalsource/fe`), `be-auth-static` (`finalsource/be`), `authorization-ownership-static` (`finalsource/be`), then `supply-chain-config-static` (`finalsource`). Each uses its same-named bundled file in `rules/`. Honor one track or an explicitly ordered subset. Work sequentially in one chat.

From the repository root, check readiness without scanning product source:

```text
python3 -B .agents/skills/run-semgrep-scan/scripts/scan.py --check
```

After researcher authorization, scan all five tracks or append `--tracks <TRACK> ...` for the approved subset:

```text
python3 -B .agents/skills/run-semgrep-scan/scripts/scan.py --product . --authorized-local
```

The runner prints an explicit batch ID and run IDs. Resume only that checkpoint with `--resume <BATCH-ID> --authorized-local`; pass `--tracks` only if it repeats the checkpoint's exact ordered selection. Verify a frozen run without scanner, network or live source using `--verify <RUN-ID>`. A changed source or rule set requires a new batch; never overwrite terminal runs. An interrupted in-progress track needs investigation before a new batch.

The runner validates all bundled rules with the local OSS parser and offline metachecks, snapshots source and the selected rule, excludes non-UTF-8 binary files from scanning in private Git metadata, binds their hashes, runs the frozen rule under macOS network denial with isolated settings and OSS/local-only flags, then records scanner exit, target/rule counts and a sanitized `alerts.json`. It verifies the terminal receipt and alert projection before reporting completion. Raw JSON, logs, stdout/stderr and source snapshots stay under `git rev-parse --absolute-git-dir`/`semgrep-scan/`, outside Git commits; never upload or paste them. No registry, login, Pro, Secrets, SCA, autofix, Docker, source repair or functional tests. Missing CLI/sandbox, parsing errors, skipped rules, timeouts, scanner errors, changed source or empty targets are `blocked`, not zero findings.

## Response boundary

For each run, report literal `completed` or `blocked`, source root, configured/loaded rules, candidate/scanned/skipped files and excluded binary files, scanner errors/timeouts, alert count and original severity distribution, verifier result and direct local paths to `evidence/alerts.json` and the run folder. An unknown count stays null. Explain exclusions and limits: static file scanning does not establish route, operation, ownership or runtime coverage. Findings are review candidates, not confirmed vulnerabilities or Prompt E scores; zero findings do not prove a control. SEC mapping, ZAP correlation and triage require a separate request.

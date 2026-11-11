# Install and operate the standalone Semgrep skill

The versioned source is the [complete skill tree](../SKILL.md): instructions, five rule files (85 IDs), catalog, Python helpers, synthetic examples, and fixtures/tests. No developer checkout, reports, or machine-specific paths are required. Maintain changes in the repository, then synchronize personal installations.

## Runtime

Use Python 3.10+ and Semgrep OSS/CE. Helpers use only the standard library; MCP ZAP, Docker, Semgrep accounts/tokens, and ZAP virtual environments are unnecessary. Fixtures were checked with **1.176.0**; [requirements.txt](../requirements.txt) pins the engine, rather than all transitive dependencies. Verify actual CLI help/version when reusing an installation.

For operator-requested setup, from the skill directory:

```sh
SEMGREP_VENV="$HOME/.local/share/security-testing/semgrep-venv"
python3 -m venv "$SEMGREP_VENV"
"$SEMGREP_VENV/bin/python" -m pip install -r requirements.txt
export PATH="$SEMGREP_VENV/bin:$PATH"
```

Package installation requires network access and is separate from local assessment. Do not install runtimes/download rules automatically during scans. Prepare offline caches separately when needed; do not commit virtual environments.

## Install and synchronize

From the skill directory:

```sh
python3 -B scripts/install_skill.py check
python3 -B scripts/install_skill.py install
python3 -B scripts/install_skill.py install --update
python3 -B scripts/install_skill.py check
```

`check` exits 0 for byte-identical files, 1 for missing/different files. `install` creates a new installation or preserves an identical one. Inspect drift before `--update`; update backs up the old tree under `~/.codex/skill-backups/` before replacement, preserving private/stale files in the backup rather than merging them. Python caches are not drift. Do not run concurrent installers against one target. Use `--target /absolute/path/run-semgrep-scanner` for another destination. Recheck after pulling changes. Copying the complete tree into another project's `.agents/skills/` also works; no root-level helpers/docs are needed.

## Validate the package

```sh
export SKILL_DIR="$PWD"
python3 -B -m unittest discover -s "$SKILL_DIR/tests" -p 'test_*.py' -v
python3 -B "$SKILL_DIR/scripts/check_report_links.py" \
  "$SKILL_DIR/examples/reporting/RUN.example.json" \
  "$SKILL_DIR/examples/reporting/ALERTS.example.json"
python3 -B "$SKILL_DIR/scripts/select_rules.py" --base BE-IN-01
```

These commands do not scan a product or use the network. [Fixtures](../tests/README.md) exercise actual engine/rule behavior on synthetic data, without certifying every rule/framework/product.

Assign: “Use $run-semgrep-scanner to assess source at `<product-path>`, against `<criteria or scoped goal>` and deliver the results in Google Sheets.” The agent derives questions, executes compatible work together, and reconciles each criterion. The Sheets handoff requires a connected Google account. Product names/layouts are unrestricted. Bundled rules mainly support NestJS/TypeScript, React, and configuration; other stacks need appropriate local/custom/manual checks.

Use [operations](semgrep-operations.md) for private settings/log/raw output outside the product and local rules with metrics/version checks disabled. These settings do not block networking. Mandatory offline work requires verified isolation; missing guards are a limitation/blocker according to the assignment, not a reason to weaken it or change system firewalls.

`select_rules.py` projects the actual catalog/rules; `record_round.py` collects execution/native output; `report_records.py` creates drafts; `check_report_links.py` checks references/provenance/known counts. None selects verdicts or establishes completion. Maintain one private ALERTS/RUN pair per assessment for [Sheets delivery](sheets-delivery.md). Keep project evidence, screenshots, and execution histories outside the skill. Bundle only reusable references, generic tools, and synthetic fixtures.

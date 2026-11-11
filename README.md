# Security Testing Tool

Two portable security-testing skills for use across projects. Each directory includes its instructions, helpers, and supporting resources; product source and scanner runtimes are prepared separately.

- **[run-semgrep-scanner](.agents/skills/run-semgrep-scanner/SKILL.md):** criterion-based source security assessment using local Semgrep OSS/CE, manual review, and Google Sheets reporting.
- **[mcp-zap-repo-operations](.agents/skills/mcp-zap-repo-operations/SKILL.md):** MCP/ZAP operations for anonymous/authenticated backend/frontend testing and BOLA ownership checks, from discovery through execution and result reconciliation.

`main` maintains the English instructions. `vie-version` preserves the Vietnamese baseline.

## Repository layout

```text
.agents/skills/
├── run-semgrep-scanner/
│   ├── SKILL.md
│   ├── agents/              # UI metadata
│   ├── references/          # Workflow, catalog, setup, reporting
│   ├── rules/               # Bundled local rules
│   ├── scripts/             # Installer, collection, report checks
│   ├── tests/ and examples/ # Synthetic fixtures and contracts
│   └── requirements.txt     # Tested Semgrep engine pin
└── mcp-zap-repo-operations/
    ├── SKILL.md
    ├── agents/
    ├── references/          # Workflow, operations, runtime, setup
    ├── scripts/             # Installer and operations helpers
    └── lib/
        ├── zap-product-assessment/ # Source, schemas, profiles, CLI, tests
        └── mcp-zap-server/         # Reused helpers and license
mcp-zap-server/               # Separate scanner source for build/setup
```

Copy the complete skill directory to another project. Bundled `lib/mcp-zap-server/` contains reused helpers, not a scanner server. External scanner source is unnecessary when a suitable connector/runtime already exists. Vendored implementation/runbooks and historical fixtures retain their original language and interfaces; maintained skill instructions and metadata are English.

## 1. Clone the repository

```sh
git clone https://github.com/hehuanglu/testing-tool.git
cd testing-tool
```

Unless stated otherwise, commands start at this checkout root. Installers use Python stdlib and do not install engines, configure MCP, or scan products.

## 2. Install the skills

For a project-local copy, replace PROJECT_DIR with the actual destination:

```sh
PROJECT_DIR='/absolute/path/to/your-project'
python3 -B .agents/skills/run-semgrep-scanner/scripts/install_skill.py install \
  --target "$PROJECT_DIR/.agents/skills/run-semgrep-scanner"
python3 -B .agents/skills/mcp-zap-repo-operations/scripts/install_skill.py install \
  --target "$PROJECT_DIR/.agents/skills/mcp-zap-repo-operations"
```

Keep the names and complete directories, rather than copying SKILL.md alone. Root-level libraries/scripts are not needed alongside them. For personal installations shared across projects, omit --target:

```sh
python3 -B .agents/skills/run-semgrep-scanner/scripts/install_skill.py install
python3 -B .agents/skills/mcp-zap-repo-operations/scripts/install_skill.py install
```

Install only needed skills and verify the loaded path when personal/project copies coexist. Maintain repository sources first, then synchronize installations.

After pulling changes:

```sh
git pull --ff-only
python3 -B .agents/skills/run-semgrep-scanner/scripts/install_skill.py check
python3 -B .agents/skills/mcp-zap-repo-operations/scripts/install_skill.py check
```

Check exits 0 for identical trees and 1 for missing/different files. Inspect drift, then update intentionally:

```sh
python3 -B .agents/skills/run-semgrep-scanner/scripts/install_skill.py install --update
python3 -B .agents/skills/mcp-zap-repo-operations/scripts/install_skill.py install --update
```

For project copies use the same --target for checks/updates. Update backs up old content outside skills before replacement (`~/.codex/skill-backups/` for personal defaults; other destinations are printed). Python caches/virtual environments are excluded. Do not concurrently install to one target.

## 3. Prepare runtimes

### Semgrep

Use Python 3.10+ and Semgrep OSS/CE. Helpers use stdlib. Fixtures were checked with **1.176.0**, pinned directly in requirements.txt rather than a full transitive lock. If needed, explicitly prepare an environment outside skill/product:

```sh
SEMGREP_VENV="$HOME/.local/share/security-testing/semgrep-venv"
python3 -m venv "$SEMGREP_VENV"
"$SEMGREP_VENV/bin/python" -m pip install \
  -r .agents/skills/run-semgrep-scanner/requirements.txt
export PATH="$SEMGREP_VENV/bin:$PATH"
```

Package setup uses networking and is separate from assessment. Scans use inspected local rules, private settings/logs, and disabled metrics/version checks. These settings do not block networks: mandatory offline work requires verified isolation. Read [setup](.agents/skills/run-semgrep-scanner/references/setup.md) and [operations](.agents/skills/run-semgrep-scanner/references/semgrep-operations.md). Bundled rules mainly target NestJS/TypeScript, React, and configuration; other stacks require suitable local/custom rules or manual review. Zero matches does not establish safety or coverage.

### ZAP through MCP

Configure a connector to an authorized scanner, then verify actual tools/schemas/endpoints/auth profiles. For scanner builds/setup read its [README](mcp-zap-server/README.md). Reuse suitable isolated existing runtimes rather than rebuilding for every project.

Stdlib helpers can run independently. The bundled assessment library requires **Python 3.13** and locked dependencies:

```sh
ZAP_SKILL="$PWD/.agents/skills/mcp-zap-repo-operations"
ASSESSMENT_ROOT="$ZAP_SKILL/lib/zap-product-assessment"
ZAP_VENV="$HOME/.local/share/security-testing/zap-assessment-venv"
python3.13 -m venv "$ZAP_VENV"
"$ZAP_VENV/bin/python" -m pip install -r "$ASSESSMENT_ROOT/requirements.lock"
PYTHONPATH="$ASSESSMENT_ROOT/src" "$ZAP_VENV/bin/python" \
  "$ASSESSMENT_ROOT/scripts/product_assessment.py" --help
```

Help sends no traffic. Docker/browsers/pinned images/JARs are required only by selected executors. Verify separate MCP_ZAP_REPO for scanner source/build/doctor rather than deriving it from product cwd. Read [setup](.agents/skills/mcp-zap-repo-operations/references/setup.md) and [runtime](.agents/skills/mcp-zap-repo-operations/references/local-runtime.md).

## 4. Assign an assessment

Example Semgrep request:

```text
Use $run-semgrep-scanner to assess source at /absolute/path/to/product.
Scope: backend input and authorization/ownership. Use the supplied criteria
or derive them from this scope. Triage candidates and deliver coverage,
conclusions, and evidence in Google Sheets.
```

Example ZAP request:

```text
Use $mcp-zap-repo-operations to assess anonymous backend APIs at
<authorized test origin>, with source at /absolute/path/to/product.
Discover all in-scope public APIs, use the configured MCP runtime,
read results, and deliver RUN.json, ALERTS.json and SCOPE_ALERTS.json
with untested scope. Use my supplied security policy/catalog when provided.
```

Specify product/source/deployment, objectives, scope, and testing authority. The agent discovers inventory/techniques; rule IDs and hand-written scan commands are unnecessary. Targeted scans/retests do not automatically open every track. Responding in the user's language remains supported.

Products need no fixed names/layouts. Legacy adapters have specific contracts, rather than defaults for new products. Authenticated ZAP requires real actors/sessions; direct/BOLA requests do not replace native authenticated DAST. FE needs actual browser/UI journeys, and passive/UI traffic does not close applicable active duties.

## 5. Check installation without scanning a product

Semgrep helper tests and synthetic reports:

```sh
SEMGREP_SKILL="$PWD/.agents/skills/run-semgrep-scanner"
python3 -B -m unittest discover -s "$SEMGREP_SKILL/tests" -p 'test_*.py' -v
python3 -B "$SEMGREP_SKILL/scripts/check_report_links.py" \
  "$SEMGREP_SKILL/examples/reporting/RUN.example.json" \
  "$SEMGREP_SKILL/examples/reporting/ALERTS.example.json"
```

ZAP contract tests after preparing the runtime variables above:

```sh
PYTHONPATH="$ASSESSMENT_ROOT/src:$ASSESSMENT_ROOT/tests" "$ZAP_VENV/bin/python" -B \
  -m unittest discover -s "$ASSESSMENT_ROOT/tests" -p test_assessment.py -v
```

These test helpers/contracts against synthetic data rather than assess products. See [Semgrep fixtures](.agents/skills/run-semgrep-scanner/tests/README.md) for actual detector checks. Help/tests/exit 0 do not establish product-scope completion.

## Results and private data

Deliver `ALERTS.json` with actual findings/alerts, triage and native/manual/direct provenance; and `RUN.json` with scope/inventory, actual operations/results, coverage, limits, unfinished work, and completion. Semgrep uses one pair per sequential track. ZAP aggregates assigned scope/tracks and additionally delivers `SCOPE_ALERTS.json` with every assigned user criterion, applicability, questions, finding associations and gaps. The agent prepares internal mappings from supplied JSON/text and product discovery; see [user security scope and offline CLI](.agents/skills/mcp-zap-repo-operations/references/user-security-scope.md).

Keep executor logs/raw/spec/actors/sessions private outside skill/product. Do not commit credentials/tokens/cookies/raw responses/run data into portable skill directories. Zero alerts does not establish safety. Close scope only after inventory/questions are reconciled and unexecuted/blocked work remains accurately represented.

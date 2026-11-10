# Install and move the skill between projects

Copy the complete `mcp-zap-repo-operations` directory into a project's `.agents/skills/`, or install it personally from the skill directory:

```sh
python3 -B scripts/install_skill.py install
python3 -B scripts/install_skill.py check
```

Inspect drift before `install --update`. The helper backs up the old installation under `~/.codex/skill-backups/`; use `--target` for another destination. It uses only stdlib and does not install dependencies, configure MCP, or send traffic. Project-local usage needs no personal installation. Do not copy product source, reports, secrets, or virtual environments from a developer machine.

Repo-only maintenance does not authorize synchronizing a divergent personal copy. Use `check` read-only and report drift separately from implementation validation. Current criteria/report CLI usage is documented in the [v3 criteria workflow](criteria-driven-workflow.md).

## Paths and dependencies

Resolve paths from the loaded skill:

```sh
# Set this to the directory containing the loaded SKILL.md, independently of cwd.
export SKILL_DIR='/absolute/path/to/mcp-zap-repo-operations'
export ASSESSMENT_ROOT="$SKILL_DIR/lib/zap-product-assessment"
export ZAP_PYTHON='/absolute/path/to/python-with-assessment-dependencies'
PYTHONPATH="$ASSESSMENT_ROOT/src" "$ZAP_PYTHON" \
  "$ASSESSMENT_ROOT/scripts/product_assessment.py" --help
```

The assessment library requires Python 3.13 and `lib/zap-product-assessment/requirements.lock`. Prepare a separate environment outside skill/product when setup is assigned; do not copy virtual environments or fetch packages automatically during assessment. Stdlib helpers such as `inspect_operations.py`/`review_open_work.py` do not need the assessment library.

`lib/zap-product-assessment/` includes source/schemas/profiles/CLI/tests. `lib/mcp-zap-server/` includes reused transport/report helpers and regression entry points with license/provenance; it is not a scanner server. MCP endpoints/auth profiles/Docker/browsers/pinned images/JARs are needed only by the selected executor. Source/status tasks do not automatically provision scanners.

For scanner build/doctor tasks, verify the separately prepared `MCP_ZAP_REPO`; do not infer it from cwd/product names. Otherwise prefer the configured connector. Legacy product-named adapters retain their own contracts, rather than defining defaults for new products. When a legacy layout is actually selected, `ZAP_PRODUCT_WORKSPACE` is the caller-selected product workspace (default cwd), not the skill directory. Do not create products or reuse historical credentials to satisfy it.

## Portability checks

```sh
PYTHONPATH="$ASSESSMENT_ROOT/src:$ASSESSMENT_ROOT/tests" "$ZAP_PYTHON" -B \
  -m unittest discover -s "$ASSESSMENT_ROOT/tests" -p test_assessment.py -v
PYTHONPATH="$ASSESSMENT_ROOT/src" "$ZAP_PYTHON" -B \
  -m zap_assessment.capabilities check
```

These are offline contract/bookkeeping checks, rather than product assessment/runtime qualification. Keep actor/raw/run data private outside skill/product, never in `lib/` for reuse.

Historical portability checks on 2026-10-26 copied/installed the standalone tree and ran outside the developer checkout: 85 contract/binding/capability/research/portability tests passed with existing Python/dependencies. Bundled transport matched provenance; CLI/helper help needed no external scanner source. Another 79 regression/discovery/common-workflow cases passed with a simulated 8 GiB storage sample; six default extended cases were blocked by host reserve guards. A separate test verified no dispatch below reserve. Runtime guards were not lowered. No new product assessment, scanner provisioning, or cross-platform qualification occurred.

## Managed state commands

Use the existing project interpreter with PYTHONPATH set to the bundled assessment library src directory. Invoke python -m zap_assessment.product_cli scope with state-inspect or state-next and the explicit state directory. Locate a registered assessment with state-resolve and the explicit registry directory. See the helper contract for arguments and status codes.

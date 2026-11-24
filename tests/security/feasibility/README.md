# Local security regression feasibility fixtures

Use Python 3 and a working Docker daemon with the image pinned in [zap-image.txt](../zap-image.txt) already available. From the repository root, run the baseline as the CI gate and the qualification driver to verify failure classifications.

```sh
docker pull "$(cat tests/security/zap-image.txt)"
mkdir -p artifacts/security-feasibility
python3 tests/security/feasibility/run.py baseline \
  --out artifacts/security-feasibility/baseline.json
python3 tests/security/feasibility/qualify.py \
  --out artifacts/security-feasibility/qualification
```

Choose a fresh output file and qualification directory for each invocation. To run one control, replace `baseline` with its scenario name from [qualify.py](qualify.py). For example, `public-csp-regression` should exit 1. `active-blocked` records the execution restriction and exits 3 without starting ZAP.

- [fixture.py](fixture.py) provides synthetic form login, CSP pages with explicit controls, linked JSON endpoints for two users, and a revisioned application policy endpoint.
- [plan.py](plan.py) renders a native Automation Framework plan with literal fixture GETs, authenticated Spider jobs, passive drain and a traditional JSON report. The exploration scopes are specific to each actor.
- [app_assertions.py](app_assertions.py) uses distinct cookie jars and checks returned identity, authorization decisions and before/after application state.
- [runner.py](runner.py) checks native job completion, fixture traffic, scanner findings and application assertions and emits one machine-readable verdict. [run.py](run.py) provides container isolation, a process deadline and the CI exit. [qualify.py](qualify.py) runs the controls twice with clean state.

The [CI contract](../../../ci-verdict-contract.md) defines the exit codes and the [feasibility report](../../../security-testing-feasibility.md) identifies the supported test methods.

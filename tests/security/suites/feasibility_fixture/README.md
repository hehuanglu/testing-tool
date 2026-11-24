# Existing feasibility fixture example

This suite exercises the original synthetic CSP pages and revisioned authorization fixture. Its [specification](specifications/fixture-security.md), [objectives](objectives/objectives.json) and [cases](cases/cases.json) are example data.

Run from the repository root after loading the pinned Docker image.

```sh
PYTHONPATH=tests/security python3 -m security_framework.run \
  --suite feasibility_fixture --scenario baseline \
  --out artifacts/security-suite/feasibility_fixture/baseline/local-01
```

Use a new output directory per invocation. The baseline runs anonymous CSP, authenticated CSP, initial state, authorization responses and post-state, and Automation Framework receipts. The `application-only` and `anonymous-only` scenarios exercise the two narrower paths.

- `public-csp-regression`, `private-csp-regression`, and `authorization-regression` intentionally violate the example assertions. Expect exit 1.
- `bad-password`, `warning`, `bad-plan`, `incomplete`, `missing-evidence`, and `invalid-evidence` exercise failed prerequisites. Expect exit 2.
- `active-blocked` and `jwt-blocked` record restricted or unqualified methods. Expect exit 3 and no scanner execution.

The [framework architecture](../../../../docs/security-test-framework.md) identifies the runtime boundary, controlled inputs and evidence format.

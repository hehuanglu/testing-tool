# Portable ZAP regression suite

This directory is a self-contained runtime bundle. It needs Docker and the image pinned in
`zap-image.txt`; it does not import the assessment package, read a private RUN, call an LLM,
or rediscover assessment scope.

Run the committed suite:

```sh
bash tests/security/run_zap_suite.sh \
  --cases tests/security/cases \
  --out artifacts/zap
```

The output directory must be new or empty. The wrapper mounts this runtime and the cases
read-only, gives each case a distinct fixture, ZAP home and artifact directory, disables
container networking, and returns the suite exit code. A suite exits zero only when every
case is `PASS`, or when discovery finds zero cases and records `EMPTY` with `caseCount: 0`.

## Case contract

Each test is one canonical JSON file named `<id>.json`. Runtime discovers `*.json` in
filename order. Version 1 supports only the qualified `passive-http-v1` profile. The synthetic
lane uses:

- allowlisted fixture `csp-demo`;
- anonymous literal GET routes without query, fragment, credentials, traversal or CRLF;
- required status and media-type response witnesses;
- the exact native alert reference `10038-1`;
- a protected response, a positive control, and a nonempty CSP response witness.

The separate product lane also accepts the registry-controlled `byteme-v1` adapter. Its case
adds a target repository/full commit binding and marks each request origin as `product` or
`detector-control`. The detector control has a separate loopback origin and proves only that
ZAP rule `10038-1` fired; it is never ByteMe evidence.

Use the assessment exporter to create or update a case. It creates a new file exclusively,
returns `UNCHANGED` for byte-identical output, and returns exit 2 plus a candidate on stdout
when reviewer edits already exist. It never overwrites a changed case.

```sh
PYTHONPATH=.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src \
  zap-assessment regression generate \
  --input .agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/examples/regression/csp-reviewed-input.json \
  --out-dir tests/security/cases
```

Adding a file adds a test. Deleting a file removes it on the next invocation. There is no
manifest. Never commit raw assessment RUNs, tokens, response bodies, ports, or generated
runtime metadata in a case.

Generate the ByteMe adapter-qualification case offline, then run it against a clean checkout at
the case's pinned SHA:

```sh
PYTHONPATH=.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src \
  zap-assessment regression generate \
  --input .agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/examples/regression/byteme-csp-qualification-input.json \
  --out-dir tests/security/product-cases

bash tests/security/run_zap_product_suite.sh \
  --cases tests/security/product-cases \
  --out artifacts/byteme \
  --product-source /path/to/clean/ByteMe \
  --variant fixed-control
```

`byteme-v1` creates a uniquely labelled Docker network, unexposed MySQL and backend containers,
ephemeral RSA/DB credentials and one ZAP container. It verifies the checkout and registry
binding, records source/config/image identity, reads the product response and alerts back from
ZAP history, and removes only invocation-owned resources. `upstream-original`, `fixed-control`
and `regression-control` remain distinct in result provenance. The fixed/regression patches are
qualification controls in testing-tool; they are not ByteMe product changes.

## Results

`suite-results.json` records `PASS`, `REGRESSION`, `MISSING_EVIDENCE`, or
`EXECUTION_ERROR` for every discovered case. Each case directory contains the canonical
case copy, rendered AF plan, response evidence, native `traditional-json` report when ZAP
created one, and the ZAP log. A `PASS` means only that the narrow committed assertion was
satisfied with its controls; it is not an OWASP criterion verdict or an assessment result.
`testedCommitSha` is the checked-out commit returned by host `git rev-parse HEAD`;
`pullRequestHeadSha` is separate metadata and is null outside a pull request. A PR normally tests
its generated merge commit, so these values are intentionally allowed to differ.

Run offline parser/contract tests without Docker:

```sh
python3 -m unittest discover -s tests/security -p 'test_zap*.py' -v
```

Run all real-engine qualification controls:

```sh
python3 tests/security/qualification/run_acceptance.py \
  --scenario all \
  --out artifacts/qualification
```

Run the eight ByteMe lifecycle and verdict controls:

```sh
python3 tests/security/product/byteme/run_acceptance.py \
  --product-source /path/to/clean/ByteMe \
  --scenario all \
  --out artifacts/byteme-qualification
```

Qualification modes are harness-only arguments. Committed stable cases cannot select a
fixture fault mode. Authentication, OpenAPI import, active scan, browser journeys and BOLA
are not supported by `passive-http-v1`; their experiments remain isolated under
`experiments/` until each profile meets its own qualification gates.

The registry contains synthetic `csp-demo` and product adapter `byteme-v1`. The ByteMe adapter
is qualified for its narrow anonymous Swagger CSP contract and disposable lifecycle. Its
committed case is explicitly `product-qualification`, not an assessment transfer. A real RUN
v3 still needs a current approved plan, reviewed evidence and an oracle compatible with the
exported assertion. A CSP-missing result cannot be promoted into an anti-framing violation when
an effective `X-Frame-Options` policy satisfies that criterion.

# Compare passive CSP gates

Run from the repository root with Python 3.13 and Docker. Both local paths start the
synthetic loopback fixture inside a separate network-disabled ZAP container per trial.
The suite uses the portable wrapper. The AF experiment renders the plan and runs the AF
engine locally. GitHub qualification runs the pinned action on Linux with a runner-loopback
fixture and records the original action outcome and container exit.

```sh
runner=tests/security/experiments/passive-ci-comparison/run_comparison.py
output=$(mktemp -d "$PWD/artifacts/passive-csp.XXXXXX")
python "$runner" --implementation suite --scenario C01 --out "$output/C01-suite"
python "$runner" --implementation suite --scenario C04 --out "$output/C04-suite"
python "$runner" --implementation af --scenario C01 --out "$output/C01-af"
python "$runner" --implementation af --scenario C04 --out "$output/C04-af"
```

Use `--scenario all` with a fresh output directory for each implementation to run all seven
scenario IDs. C01 repeats in a fresh session. C07 first times out under the engine deadline
then runs a fresh healthy trial. On GitHub the recovery uses the pinned action. The action
job has its own wall-clock ceiling.

For C04, open `comparison-results.json`, then the `artifact` and `locators` in the C04
primary record. The case gate exits 1 with `MISSING_EVIDENCE / RESPONSE_CONTENT_MISMATCH`.
Open the fixture receipt (`evidencePath` or `receipt`) and find the docs response ID and
login marker. C01 has a docs marker plus a nonempty enforcing CSP and a control alert. C02
and C05 provide pointers into the ZAP report. Both runners use `traditional-json-plus`
and join those pointers to fixture receipts by the emitted response ID. On repeated
URLs, use the message-linked alert as the evidence for C05. The AF URL tests reflect
the site node and retain their independent outcomes in the artifact.

The harness exits 0 when every actual status, case exit and required artifact matches the
qualification oracle. A case can exit 1 as intended while qualification succeeds.
GitHub attaches one filtered artifact per implementation, scenario and run attempt. Retain
the checkout SHA, image digest and action SHA before comparing results across environments.

After a pin change, use fresh output roots to rerun both `--scenario all` commands, rerun
`tests/security/qualification/run_acceptance.py --scenario all`, then run the
`ZAP passive CI comparison` workflow and read back every matrix artifact. The comparison
covers synthetic HTTP only. See the [comparison report](../../../../docs/reviews/zap-passive-ci-comparison.md)
for evidence and the decision for this case.

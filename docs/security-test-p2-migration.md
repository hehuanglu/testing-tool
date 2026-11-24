# Migrate to the P2 security framework

Existing suite commands, open criteria and v1 evidence stay available. P2 adds an adapter and engine contract and a versioned receipt for consumers that need to distinguish test results, execution and release decisions. [Architecture](security-test-framework.md) · [CI verdict contract](../ci-verdict-contract.md)

## Migrate an execution path

1. Keep the reviewed case, authentication profile and evidence predicates. Move source resolution, build, readiness and fixture ownership into the project's `prepare(resources)` implementation. Register cleanup when a resource can first exist. Return the owned origin or test runtime and the minimal inputs the engine consumes.
2. Define the engine capability and supported methods. Run suite admission before fixture acquisition. Apply the engine-specific scope, prerequisite and identity checks before treating any observation as usable. Preserve engine reasons and distinguish assertion failure from setup, transport, report and cleanup failure.
3. Use the original case-level adjudication after execution and cleanup. Bind each observation to its producer and keep the source, plan or configuration, dependency and runtime identities and hashes of the exact artifacts. Give independent runs distinct IDs and new output directories.
4. Compare result, reason, exit and material witnesses with the qualified revision. Keep the old entry point until the replacement passes the relevant positive, failure and teardown controls. A new engine or adapter needs its own qualification record.

## Read a shared v1 result

Run the verifier from the framework checkout. Supply the recorded shell exit. Use `--input-root` when the receipt's suite and framework inputs live at an older revision. Use a clean Git checkout at that revision when binding the immutable SHA.

```sh
export PYTHONPATH=tests/security
python3 -m security_framework.ci --out /path/to/receipt.json --exit-code "$lane_exit" \
  shared /path/to/result.json \
  --input-root /path/to/recorded-framework/tests/security \
  --framework-revision "$framework_sha"
```

The v2 receipt references the original `result.json` by SHA-256. A witness points into that artifact using a JSON pointer. Keep both files. `execution.sourceStatus` and `exitCode` retain the original aggregate. Per-case status and reason stay with each objective. `acceptance.status` is `NOT_EVALUATED` for a shared suite. Capability qualification comes from a separately approved qualification record. A blocked capability carries its no-dispatch observation.

## Read a product-native bundle

Run Bus Booking's existing `tests/security/run.py` at the pinned product commit with its own full or long mode and capture the exit. Its filtered output is `results.json`, `manifest.json` and `summary.md`. The product retains control of the runtime, fixture data, sanitized output and release policy. Use the clean recorded source and pre-provision matching JDK, Maven dependencies and image content IDs from the qualification manifest. The legacy runner records content IDs after resolving its configured image tags.

```sh
python3 -m security_framework.ci --out /path/to/receipt.json --exit-code "$lane_exit" \
  bus-booking-native /path/to/product-bundle \
  --project /path/to/bus-booking-checkout --project-revision "$product_sha" --mode full
```

Supply `--acceptance-gate` only if the original run used `--require-acceptance`. Product exit 3 in this mode indicates release acceptance was withheld after successful execution. The v2 outcome preserves both facts. Product criteria keep `PASS`, `FAIL`, `MISSING` and `REVIEW` as recorded. The verifier checks the two artifact hashes, source and scope against committed blobs, declared criterion inventory, native passive reconciliation, independent release checks and cleanup evidence. A single objective can point to MockMvc, HTTP, passive or other native observations. Consume the original source bundle to inspect the details behind each pointer.

## Gate and publish in CI

- Check out the exact framework SHA and, when used, the separate product SHA. Bind the run's inputs to the selected reviewed lane. Record runtime and dependency identities and compare actual image IDs and platform to the reference if reproducing a measurement.
- Record the shell process exit before applying the job condition. A successful verifier exit means the evidence was valid. Gate on the recorded execution status and use the product's separate acceptance policy where required. Treat an absent receipt or an unexpected exit as a failed lane.
- Verify scope-owned teardown on every terminal path. Preserve only validated, allowlisted projections and their digest-bound original filtered results. Keep raw HAR, unfiltered logs and reports, session tokens, fixture credentials, and product configuration with secrets out of CI artifacts.
- The existing shared workflow performs the baseline and explicit no-dispatch checks with read-only checkout permissions. Product receipt validation can consume the existing product workflow's filtered artifacts with a checkout of the exact source. Hosted verification requires an actual run at the proposed inputs. [Shared workflow](../.github/workflows/security-suite-framework.yml)

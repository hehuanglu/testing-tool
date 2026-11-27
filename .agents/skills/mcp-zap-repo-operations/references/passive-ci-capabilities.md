# Passive HTTP capabilities for fixed CI cases

Scope: synthetic `csp-docs`, anonymous GET, Docker image from
[`zap-image.txt`](../../../../tests/security/zap-image.txt). The action pin is
`c41784dfded31e10c69d78896700f48e5fd5fa3a`. See the
[comparison report](../../../../docs/reviews/zap-passive-ci-comparison.md) for
the qualification runs, tested SHAs, and results by scenario.

| Responsibility | Input and implementation | Output, defaults and limit |
|---|---|---|
| Launch in GitHub | [Pinned action metadata](https://github.com/zaproxy/action-af/blob/c41784dfded31e10c69d78896700f48e5fd5fa3a/action.yml) and [bundled Node entrypoint](https://github.com/zaproxy/action-af/blob/c41784dfded31e10c69d78896700f48e5fd5fa3a/dist/index.js). Supply a workspace-relative plan, explicit image digest and fixed command options. | Defaults to the mutable `ghcr.io/zaproxy/zaproxy:stable`. Pulls the image, makes the workspace writable and mounts it at `/zap/wrk` with host networking. It has no issue-writing path or artifact upload. A failed pull or nonzero Docker exit calls `setFailed`; GitHub's step outcome loses the original numeric exit. The container persists for independent exit readback. Source read. |
| Send fixed requests | AF `requestor` consumes literal method and URL. The suite puts its fixture and ZAP together in a network-disabled container. GitHub action needs a reachable runner-loopback fixture. | A fixture receipt records a response it sent. A request log, status warning or successful container exit alone cannot identify a response. |
| Recognize exact HTML | AF [URL Presence Job Tests](https://www.zaproxy.org/docs/desktop/addons/automation-framework/test-url/) consume URL and body/header regexes with `operator: and`. Use a separate body-only test for page identity and a joint test for header policy. | The default operator is `or`; explicitly select `and`. Job-test output and traditional alert rows do not by themselves expose a join key from the URL test to a particular response when a URL repeats. A failed joint test can mean missing CSP or wrong content. |
| Drain passive scan and read the alert | AF `passiveScan-config` removes the per-rule cap; `passiveScan-wait` runs before `report`. Read the `10038-1` instances on both fixed paths with origin, method and rule ref. | The traditional report has alert IDs and locators. An alert ID is not a response identifier. A report with message fields can be joined to a fixture receipt using the emitted response ID. If that join is unavailable for repeated responses, leave the obligation missing. |
| Map and retain | Repository classifier combines response identity, enforcing CSP on the same response, and a known working detector control. Workflow keeps fixture receipts, AF job tests, filtered logs, report and case results under a unique output path and uploads them before the final assertion. | AF exit and workflow step outcome are execution evidence. Case verdict and qualification status have separate meanings. A negative case can satisfy qualification. A qualified capability limit never claims equivalence. |

## Trace a case in both directions

[Workflow v3](criteria-driven-workflow.md#verdicts-and-completion) owns the
assessment verdict. The fixed 50-criterion catalog and the Gate 2 binding
still apply. Follow criterion `caseIds` to the approved case and its obligations.
Match the exact actor, build, action and response context in the observation.
Read the reviewed result and retained links before making a criterion-level
decision. In reverse, start at the CI evidence locator and case ID, open the
reviewed mapping and case requirement, verify revision and digest, and recover
the assessment and criterion IDs. Keep the SHA executed in CI separately from
the reviewed target SHA and the plan digest.

For the [synthetic case](../../../../tests/security/cases/csp-docs.json),
`source.kind=synthetic-demo` points to the fixture design. Its expectation
requires an enforcing CSP on GET `/docs` and a `10038-1` alert on GET
`/control`. The observation chain has three producers: fixture receipt, ZAP
alert and CI classifier. Synthetic controls do not contribute assessment
observations.

The [ByteMe candidate](../../../../tests/security/product-assessment-cases/byteme-swagger-anti-framing.json)
points to `ByteMe-AF-V3-20261112-LIVE-1`, case
`byteme-swagger-anti-framing`, criterion `SEC-A06-06`, revision
`ByteMe-P-DRAFT-5` and the full plan digest. Its `source.evidence` links
the baseline and policy operation IDs, semantic locators and digests. The
[historical readback](../../../../docs/reviews/zap-regression-generator-acceptance-20261111.md#anti-framing-profile-qualification-2026-11-12)
documents the exact build and message. Keep the case contract and mapping
alongside any hand-authored AF plan. Before admitting an assessment case,
review the same RUN input through `regression generate`, compare the plan
requests, identity and expectations to the candidate and record the case and
plan digests together. A changed case, context or digest requires new
readback. The AF plan alone does not carry the assessment binding.

## Two questions on one ByteMe message

The retained anonymous GET `/swagger-ui/index.html` response is 200 HTML
with a Swagger marker, `X-Frame-Options: DENY` and no enforcing CSP.

- Anonymous anti-framing case for `SEC-A06-06`. The exact observed response
  supports the reviewed header-policy expectation under the case's browser
  assumptions. It establishes no browser execution.
- Anonymous mandatory-CSP question. If a separate approved requirement
  mandates an enforcing CSP on this page, the same response contradicts that
  expectation. This is an example of a separate obligation; the committed
  anti-framing case supplies no approval or verdict for it.
- Proposed signed-in-role case. The role session and matching Swagger
  response are missing. A reviewed plan would pin the role, request and
  expectation, and require identity, HTML marker and headers from that role's
  response. Under `all_cases`, disposition of this case remains required if
  approved alongside the anonymous case, even when the anonymous observation
  already contradicts one oracle. Each criterion closes on its own cases.

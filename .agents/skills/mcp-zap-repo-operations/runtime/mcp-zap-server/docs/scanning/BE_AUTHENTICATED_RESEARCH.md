# Native backend authenticated research

`be-authenticated-research/1.0` keeps the backend functional scope and explicitly accepts credentials/tokens in local native ZAP memory, history, session DB and raw reports. Those files remain private and are not published automatically. Strict secret-safe contracts and historical failures are unchanged. The default `zap.auth.experimental-json-bearer-enabled` remains false.

Native `JsonBearerAuthBootstrapProvider` configures context/user JSON login and header session management. Research profiles configure `subject-json-pointer` and `expected-subject` from independently created actor provenance. Validation requires a JSON HTTP200 protected response matching the subject, in addition to positive indicators. Subsequent validation does not explicitly call login; native automatic reauthentication, if observed, must be distinguished from refresh or revoke support. Failed or exceptional validation invalidates the handle for future guided starts.

Direct topology is required: `ZAP_SCAN_JOBS_STORE_BACKEND=in-memory`, `ZAP_SCAN_QUEUE_COORDINATOR_BACKEND=single-node`. Queued JSON bearer remains rejected. A process restart discards handles and requires fresh prepare/validate. The header credential scaffold is not an injection proof.

The assessment entry is separate from strict P0, validates a versioned plan schema and reuses the upstream CI runner's MCP client/parsers. It calls native prepare/validate and passes `authSessionId` into every guided crawl/attack. The ordinary CI gate has not become an authenticated runner. No scan engine was duplicated.

From the workspace root, with Docker test deployment `finalsource-zap-test` already running:

```sh
JAVA_HOME="$(/usr/libexec/java_home -v 25)" mcp-zap-server/gradlew -p mcp-zap-server bootJar --offline --no-daemon
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/be_authenticated_research.py --help
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/be_authenticated_research.py run \
  --output /absolute/new/private/run-directory \
  --jar '/Users/hahoangloc/Working/testing tool/mcp-zap-server/build/libs/mcp-zap-server-0.16.0.jar'
```

Use `--kind interrupted` for the interrupted run. The command creates fresh fixture users, owned category rows via the existing fixture helper, and fixture accounts/goals/transactions; it requires the corresponding test authority. It never restarts the target. It builds a local derivative of the installed JVM image using the new JAR, then creates a dedicated ZAP/MCP pair with loopback ports, separate random API keys and labels. Local config and provenance are saved in the run directory. The sample profile is under `examples/authenticated-scanning/research/`.

Before active work the runner locks exact origin/method/path/owned IDs, rule IDs40012/40018, low strength/medium threshold, query/JSON body vectors, one producer/thread and deadlines. It sets native context regexes and a sender scope guard. Foreign account/category reference fuzzing and path-ID/header/cookie fuzz are excluded from this campaign and disclosed. Guard-denied traffic is rewritten to a non-business GET path and excluded from useful attack coverage. JSON POST/PUT bodies use optional `method`/`postData` on `zap_attack_start`, preserving native `scanAsUser`; explicit method/body is rejected for anonymous or queued execution.

A separate MCP client samples identity every2 seconds during work. Auth/binding loss latches new starts and requests stop only for recorded owned operations. Uncertain start ACKs are journaled and native scan state recorded without retry. Dedicated runtime cleanup reconciles any outstanding native work. Reports are generated through MCP after terminal/passive settle, copied in full, parsed/read to EOF and hashed. The manifest verifier detects missing/truncated/changed bytes; it is not a security verdict.

```sh
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/be_authenticated_research.py verify \
  --output /absolute/existing/run-directory
```

Run two fresh scenarios on the same JAR/target image plus one interruption. Keep vulnerable/fixed scanner controls separate from product A→B fixed-build regression. Source, JAR, image, add-ons, rules, history, seeds, cases and stop observations are separate evidence. Source hash is not source-to-image attestation; runtime behavior is the acceptance evidence.

Do not claim the entire track complete from unit tests, startup, zero alerts or a fixture detection control. Natural expiry with a long product TTL, unsupported lifecycle endpoints, missing build B, unexercised vectors and remaining business cases each need an honest disposition. Keep execution/evidence/security/cleanup/gate separate. Retain fixture data lacking a deletion API with exact references; never reset the database to clean research fixtures.

The product inventory observed for this implementation contains19 operations (16 protected plus public health/login/register). The final scenarios also seed DELETE of a separate owned account through native ZAP and assert its absence afterward. POST/PUT active vectors and query values are exercised; cookie sessions are absent, Authorization negatives are separate controls, and path-ID active fuzz remains an explicitly unexercised technique.

Repeatability uses `zap-product-assessment/scripts/compare_research_runs.py --before RUN1 --after RUN2 --output NEW.json`. It refuses missing/truncated reports, failed auth/operations and changed rules/add-ons. Different Docker image IDs are inconclusive by default. When only rebuild metadata differs, `scripts/record_research_image_equivalence.py` can record complete layer digests and a runtime config hash; pass that explicit file with `--image-equivalence FILE`. The distinct IDs stay disclosed. Different filesystem/config/JAR/add-on data remains inconclusive. This local observation is not a platform attestation or product fixed-build regression.

Natural expiry can be checked later without changing the product TTL:

```sh
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/be_authenticated_research.py check-expiry \
  --credentials /absolute/existing/run/credentials.json --output /absolute/new/expiry-observation
```

The token payload supplies diagnostic timing only; the API response supplies the actual before/after observation. Full native expiry/automatic-relogin behavior remains pending until observed.

After preserving reports, `scripts/cleanup_research_accounts.py --evidence-root BUNDLE --output NEWDIR` logs in only generated actors with registration provenance, verifies protected subjects, deletes their own fixture accounts through API, and asserts empty post-state. It does not delete users/categories/goals lacking an API or reset the database. Source/JAR/image artifacts may remain locally for reproduction.

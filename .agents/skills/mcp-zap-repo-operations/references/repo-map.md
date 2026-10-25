# Bản đồ repo và runner

Mọi path dưới đây tính từ checkout mcp-zap-server, trừ mục assessment. Đọc file thực trước khi dùng; đây là bản đồ nguồn, không phải bằng chứng tất cả mode đã chạy trên máy.

## Source, build và tests

- Java/Spring Boot: `src/main/java/mcp/server/zap/core/`, cấu hình `src/main/resources/application.yml`, dependency/task contract `build.gradle`, `gradle.properties`, `settings.gradle`. Java25; Gradle wrapper9.8.1 ở snapshot.
- Gateway adapters nối ZAP; `service/*McpToolsService.java` công bố tool, `GuidedScanWorkflowService.java` định tuyến; `service/authz/` scope; `service/policy/` policy; `configuration/` startup/security; `service/queue/`, `service/jobstore/`, `history/` quản lý execution/evidence. Không thay gateway dependencies hoặc scan engine để giải quyết setup.
- `./gradlew test`: unit/Spring integration không mang tag docker. `./gradlew dockerTest`: chỉ tag docker, có Testcontainers/fixture runtime riêng. `build` không tự chạy dockerTest.
- Trên máy này PATH java từng là11; chọn JDK25 theo lệnh chuẩn macOS trong shell của lệnh build:

```sh
JAVA_HOME="$(/usr/libexec/java_home -v 25)" ./gradlew test --no-daemon
```

Đổi task thành `build`, `dockerTest --tests 'fully.qualified.TestClass'`, `jacocoTestReport` tùy việc. Xác minh JDK path trước; không sửa shell profile. Tránh `clean` trước khi bảo toàn evidence cũ; không thêm `--scan`/Sonar upload vào local check.

Kết quả ở `build/test-results/{test,dockerTest}` và `build/reports/tests/`. XML là kết quả lần chạy gần nhất của task được chọn, không phải chứng nhận toàn bộ source hiện tại. Ghi tests/failures/errors/skipped, thời điểm, command, source/image pin. Trước run mới lưu bản cũ nếu cần giữ lịch sử.

- `python3 -m unittest discover -s tests/python -p 'test_*.py'`: CI gate/webhook/contracts/Compose/Helm tests. Cần PyYAML (CI pin6.0.3), Docker Compose và Helm cho từng nhóm. Helm thiếu thì tests skip; không báo full pass khi có skip. Không cài dependency chỉ để mở bản đồ.
- `tools/healthcheck/`: Go healthcheck nhúng trong image distroless; không phải scan runner. `Dockerfile` và `scripts/verify-distroless-signature.sh` quản lý build/signature. Signature của base image không chứng minh toàn bộ app image/source.
- `.github/workflows/ci.yml`: Python, MCPB, Gradle build và dockerTest theo event; coverage/report upload. Workflow tồn tại không chứng minh CI remote đã pass. Không publish/dispatch pipeline nếu chỉ được yêu cầu kiểm tra local.

## Các runner có side effect

- `bin/bootstrap-local.sh`, `bin/self-serve-doctor.sh`, `dev.sh`: xem local-runtime reference.
- `.github/actions/zap-security-gate/mcp_zap_gate.py`: runner Python MCP→crawl/optional attack→settle→findings/report/diff. Đọc `--help`, action input contract và `docs/integrations/GITHUB_ACTIONS_INTEGRATION.md` trước chọn tham số.
- `.github/actions/zap-security-gate/run-gate.sh`: wrapper môi trường GitHub Actions; tạo Compose project, có cleanup `down --remove-orphans`, workspace permissions. Không chạy thẳng trên project scanner đang dùng. Shell dùng cú pháp Bash mới như `${value,,}`; Bash3.2 mặc định macOS không đủ. Chọn Bash phù hợp và workspace/project riêng khi chạy local có chủ đích.
- `examples/gitlab/run-zap-security-gate.sh` dùng chung Python runner với biến GitLab; đọc `docs/integrations/GITLAB_CI_INTEGRATION.md`. GitHub/GitLab wrappers cần project name, output/workspace và target riêng.
- Webhook: `.github/actions/zap-webhook-callback/send_zap_webhook.py`, wrapper và `examples/gitlab/send-zap-webhook.sh`; xem `docs/integrations/WEBHOOK_CALLBACKS.md`. Gửi callback là giao tiếp ra ngoài, không phải một kiểm tra local tự động được phép.
- Automation Framework: `ExpertAutomationMcpToolsService.java`, `AutomationPlanService.java`, `AutomationPlanTargetPolicy.java`, docs scanning/automation-framework. Plan có thể gửi traffic/chạy scan; import/review không đồng nghĩa cho phép execute.
- AWS smoke `examples/aws-ec2/smoke-api.py`, cloudformation/setup-host/firewall và EKS starter là deployment riêng, không thuộc local audit mặc định.

## Contracts CI và evidence gốc

Nguồn chuẩn `docs/scanning/CI_GATE_CONTRACTS.md`, `SEEDED_API_GATE_PLAYBOOK.md`.
Result v2, snapshot/diff v3, seed/manifest/suppressions v1. v3 ghi ZAP version và full add-on inventory; `different/unknown` không được coi resolved/new comparable. Seed mode tạo candidate, không chấp nhận baseline thay reviewer. Root gate main trả0/1; không áp exit0/1/2/3 của assessment phụ vào nó.

Root `artifact-manifest.json` không bắt buộc SHA cho copied native report theo contract hiện tại; khác bundle verifier của assessment bắt buộc full byte/hash readback. Report generator có artifact không đồng nghĩa bundle độc lập có đủ coverage/provenance.

## Docs, packages và extension

- `docs/README.md`, `docs/package.json`: Astro/Starlight; từ docs chạy `npm ci`, `npm run check`, `npm run build` khi cần sửa/kiểm tra docs. `docs/scripts/sync-docs.mjs` sinh các trang từ Markdown chuẩn, không sửa bản generated. Public docs không chứa private rollout notes; audit máy để ngoài repo.
- `packaging/claude-desktop/`: Node>=20.18.1; `npm ci --ignore-scripts --no-audit --no-fund`, `npm test`, `npm run build` theo README. Build tải/đóng gói distribution, không là status-only. `verify:status` là kiểm tra connector Node, không thay native Claude session proof.
- `packaging/macos/`: build-package.py, launcher `mcp-zap`, tunnel helper, source/distribution notices. Đọc README và `docs/getting-started/MACOS_PACKAGE.md`; build từ bootJar đúng version và verify source manifest/licensing. Tunnel thay đổi reachability, không bật mặc định.
- `plugins/mcp-zap-connect/`: skill-only onboarding; ba marketplace manifests cho clients. Không có full-repo operations skill trong snapshot upstream.
- Extension contracts `src/main/java/mcp/server/zap/extension/api/`; `extensionApiJar`, `samplePolicyMetadataExtensionJar`, `standalonePolicyMetadataExtensionJar`. Đọc `docs/extensions/{README,BUILD_YOUR_OWN_EXTENSION,EXTENSION_API_COMPATIBILITY,EXTENSION_API_RELEASE_POLICY}.md`. Trạng thái `experimental-local`; standalone task stage local Maven rồi compile. Không hứa Maven Central/stable binary/runtime plugin loading/multi-engine chỉ vì JAR build được.

## Shared service / vận hành nâng cao

- `helm/mcp-zap-server/`: deploy, migration job, storage, NetworkPolicy, HPA/PDB, values variants. `src/main/resources/db/migration/` và chart migration copies cần giữ tương ứng. Helm render tests khác live cluster acceptance.
- `docs/src/content/docs/operations/`: observability, structured logging, abuse protection, runtime policies, queue retry/coordinator, scan history, production checklist, release handoff.
- `ops/observability/`: Grafana dashboard, Prometheus alerts; cung cấp cấu hình, chưa chứng minh metrics/alerts đã nối trên máy.
- `docs/operator/runbooks/`: auth bootstrap failure, CI pilot install, production simulation, EC2. HA cần shared jobs, node IDs/leases, session affinity, revocation/history và ZAP recovery; không suy từ MCP replica count. Public repo không có HA Compose runnable.

## Assessment phụ

`../zap-product-assessment/` không phải upstream runner. `cli.py` anonymous planner/pilot/recover/verify; `bola.py` adapter cơ bản; `bola_operational.py` owned synthetic login+read; `bola_borrowed.py` borrowed Docker prepare/plan/preflight/run/verify/cleanup. Python3.13 và `.venv` riêng.

Campaign scripts: integration, binding, fault, bola_campaign, bola_operational_pilot, bola_borrowed_pilot. Fault dùng fake transport không chứng minh ZAP. Các campaign tạo traffic/fixtures, không chạy để làm status. Schema builders có thể ghi file; `verify_m2_evidence.py` từ chối output đã có, `verify_m3_evidence.py` ghi đè verification.json, borrowed verifier cũng có output mặc định lịch sử. Dùng helper readback của skill cho audit không rewrite.

# Kế hoạch implement bộ sinh test hồi quy ZAP — bàn giao Sol

Ngày: 2026-11-11. Repo nghiệm thu: https://github.com/hehuanglu/testing-tool.
Chat nguồn đã đọc: **Thiết kế bộ sinh test ZAP**, ID `01a1cb5d-7431-7061-adef-464df096671f`, gồm thiết kế Canvas và ví dụ JSON/YAML.
HEAD khi khảo sát: `c954ea870a4180e603fa8ff2926aacb78c74fde7`, nhánh `main`.

## 1. Chỉ thị thực hiện

Implement theo quyết định trong tài liệu này; không dành một vòng mới để thiết kế lại kiến trúc. Viết script chạy được, sinh case thật, chạy ZAP thật ở local và GitHub Actions của repo trên. Hoàn tất phần bắt buộc A trước, sau đó thử nghiệm B và C theo phạm vi ghi rõ. Một mục thử nghiệm thất bại phải có script, lệnh đã chạy, kết quả và nguyên nhân; không biến nhận định bằng lời thành bằng chứng hỗ trợ.

Sản phẩm cuối là tính năng của skill `mcp-zap-repo-operations`: khi chuẩn bị suite, skill chuyển case đã review thành file test cố định trong Git. CI chỉ đọc file, dựng target/fixture, chạy thao tác đã định nghĩa, áp assertion và lưu kết quả. CI không gọi LLM, không tự lập lại kế hoạch, không đọc assessment riêng tư và không quyết định lại phạm vi 50 tiêu chí. Một test đạt không đồng nghĩa tiêu chí OWASP hay assessment hoàn tất.

Tài liệu này là kế hoạch triển khai, chưa phải báo cáo nghiệm thu. Lượt lập kế hoạch không chạy scan, không push và không dispatch workflow. Các run GitHub được yêu cầu dưới đây là công việc phải làm trong lượt implement.

### Quyết định đã khóa

1. Mỗi case có một file `tests/security/cases/<id>.json`, là nguồn chuẩn duy nhất tại runtime. Runner glob `*.json` theo thứ tự tên; không duy trì manifest liệt kê case, không commit YAML sinh ra hoặc script Python riêng cho từng case.
2. Plan AF được dựng tạm cho mỗi run/case. Mỗi case có session/home ZAP, fixture và output riêng; MVP chạy tuần tự. Không chia sẻ alert/session giữa case.
3. Runtime dùng ZAP Automation Framework (AF), gọi `/zap/zap.sh -cmd -autorun <plan>`. Không cần MCP server trong CI. Tái sử dụng engine ZAP, không tự viết scanner.
4. Bộ sinh nằm trong package assessment hiện có; runtime nhẹ nằm trong `tests/security/`, chỉ dùng Python stdlib để không buộc image ZAP cài package Python 3.13 của assessment.
5. Giữ contract JSON CSP từ chat trước; mở rộng nhỏ bằng `profile: passive-http-v1`. Các capability khác có profile riêng và chỉ được nhận sau nghiệm thu.
6. Kết quả case: `PASS`, `REGRESSION`, `MISSING_EVIDENCE`, `EXECUTION_ERROR`. Suite exit 0 khi mọi case PASS, hoặc suite rỗng được ghi rõ; mọi trường hợp khác exit 1. Không có trạng thái “skip nhưng đạt” cho case đang có trong suite.
7. Không ghi đè case đã sửa: giống byte là no-op, khác là xuất candidate để review. Xóa file case làm test biến mất ngay run kế tiếp.
8. Không sửa logic approval, verdict, recovery hay parser native hiện có chỉ để exporter chạy được. Sinh test là tác vụ chuẩn bị artifact riêng, không tự chạy traffic sản phẩm.

## 2. Hiện trạng và phần tái sử dụng

Các đường dẫn dưới đây tương đối với repo root; `SKILL=.agents/skills/mcp-zap-repo-operations`, `ASSESS=$SKILL/lib/zap-product-assessment`.

- `tests/security/zap_passive_smoke.py`: HTTP fixture `/docs`, `/control`, AF requestor/wait/report, assertion CSP `10038-1`. Tách fixture và cách gọi subprocess; nâng cấp readback từ set path thành response records. Không chỉ đổi tên demo thành generator.
- `.github/workflows/zap-passive-smoke.yml`: image digest, chạy Docker `--network none`, upload artifact. Giữ nguyên demo để đối chiếu khi xây tính năng; có thể loại workflow trùng sau khi workflow mới đạt đầy đủ.
- `docs/plans/zap-ci-suite-design-handoff.md`: báo cáo ba run local demo; đây là thông tin lịch sử, không thay cho run của implementation mới.
- `$ASSESS/src/zap_assessment/criteria_workflow.py::review_workflow`: kiểm tra workflow/revision/case. Dùng ở bước export; không yêu cầu toàn bộ assessment đã hoàn tất mới export một case có đủ evidence.
- `$ASSESS/src/zap_assessment/question_evidence.py::resolve_question_evidence`: dùng khi dữ liệu có question/observation tương thích. Không ép RUN v3 vào helper bằng dữ liệu giả; code adapter phải dựa schema hiện hành và kiểm tra link của case thực tế.
- `$ASSESS/src/zap_assessment/report_reconciliation.py::normalize_report`: yêu cầu `instance.id`. **Không dùng trực tiếp** cho `traditional-json` có instance thiếu ID; viết adapter nhỏ riêng. Không sửa parser này để nhận identity giả.
- `$ASSESS/src/zap_assessment/regression.py` và `$SKILL/lib/mcp-zap-server/.github/actions/zap-security-gate/run-assessment-regression.sh`: so sánh/replay evidence đã lưu, không tạo fresh traffic. Giữ chức năng cũ.
- `mcp_zap_gate.py`: tham khảo JSON ổn định, artifact metadata, GitHub summary; không import cả file vào runtime chỉ để dùng vài helper, không biến finding baseline thành oracle CSP.
- `$ASSESS/pyproject.toml`: Python `>=3.13,<3.14`, dependency `jsonschema==4.26.0`, console script `zap-assessment`. CLI hiện chưa có namespace `regression generate`; cần thêm thật.

Tại thời điểm khảo sát, `.github/`, `tests/` và tài liệu handoff là **untracked**. Không xóa/ghi đè chúng như file thừa. Không có `AGENTS.md` được tìm thấy trong cây khảo sát. GitHub API chưa có `.github/workflows` ở default branch (404), `gh run list` không trả run. Vì vậy chưa có bằng chứng workflow đã chạy trên remote.

## 3. Các action/lệnh ZAP đã có — quyết định dùng

Đã đọc `action.yml` và README trực tiếp trên GitHub ngày 2026-11-11. Các SHA dưới đây là snapshot khảo sát, không phải lời khẳng định tag release mới nhất. Pin action/image độc lập; image default `stable` không đủ tái lập.

### 3.1 Baseline — sẵn có, dễ tích hợp nhưng không thay suite từng case

[zaproxy/action-baseline tại SHA khảo sát](https://github.com/zaproxy/action-baseline/tree/72166cb1b917b984128586ed28801f4b4a37a0e2).
Input có `target`, `docker_name`, `rules_file_name`, `cmd_options`, `fail_action`, `allow_issue_writing`, `artifact_name`, `token`. Mặc định `fail_action: false`, `allow_issue_writing: true`; nếu dùng phải đặt tường minh `allow_issue_writing: false` để không phát sinh issue.

Lệnh có sẵn: `zap-baseline.py -t <url> -m 1 -J report.json -r report.html`. Có `-c` rule config, `-n` context, `-U` user trong context, `-z` ZAP options, `--hook`, `--plan-only`. Baseline spider rồi passive scan; không bảo đảm request nghiệp vụ cụ thể đã đi qua. Chỉ làm smoke bổ sung sau MVP, không dùng kết quả toàn site để kết luận case. [Tài liệu lệnh baseline](https://www.zaproxy.org/docs/docker/baseline-scan/).

### 3.2 Full scan — lệnh dễ gọi, nghiệm thu case khó hơn

[zaproxy/action-full-scan tại SHA khảo sát](https://github.com/zaproxy/action-full-scan/tree/373906d606ca990dd62655c65983bab507527b41).
Input gần baseline. Lệnh `zap-full-scan.py -t <url> -m 1 -J report.json`; spider và active scan, có context/user, hooks, rule config. `-m` giới hạn spider, `-T` giới hạn khởi động/passive, **không coi chúng là deadline toàn active scan**. Bọc deadline process/job riêng. Dùng cho thử nghiệm active trên fixture disposable, không làm default PR scan của mọi case. [Tài liệu full scan](https://www.zaproxy.org/docs/docker/full-scan/).

### 3.3 API scan — sẵn import OpenAPI/SOAP/GraphQL

[zaproxy/action-api-scan tại SHA khảo sát](https://github.com/zaproxy/action-api-scan/tree/916872bb8a5b91632527a48f20efdb6822b18c08).
Thêm input `format` (`openapi`, `soap`, `graphql`). `target` là definition file/URL đối với OpenAPI/SOAP, endpoint đối với GraphQL.
Lệnh `zap-api-scan.py -t /zap/wrk/openapi.yaml -f openapi -S -J report.json` cho thử nghiệm passive; bỏ `-S` sẽ có active scan. Có `-O` override hostname OpenAPI và `--schema` cho GraphQL. Nghiệm thu phải xác nhận endpoint được import và request thực tới target, không chỉ parser đọc được spec. [Tài liệu API scan](https://www.zaproxy.org/docs/docker/api-scan/).

### 3.4 Automation Framework — lựa chọn chính

[zaproxy/action-af tại SHA khảo sát](https://github.com/zaproxy/action-af/tree/c41784dfded31e10c69d78896700f48e5fd5fa3a).
Input: `plan`, `docker_name`, `docker_env_vars`, `cmd_options`; **không có** input `target`, `format`, `fail_action`, `artifact_name`, `allow_issue_writing`. File cần giữ sau run đặt trong `/zap/wrk/`; dùng upload-artifact riêng.

AF có `-autogenmin`, `-autogenmax`, `-autocheck`, `-autorun`. Template sinh bởi ZAP chỉ mô tả plan ZAP, không sinh fixture, provenance hay business assertion; vì vậy không thay exporter của skill. Dùng `-autogenmax`/`-autocheck` để kiểm tra capability của đúng image ghim. [AF CLI](https://www.zaproxy.org/docs/desktop/addons/automation-framework/).

MVP dùng `docker run` trực tiếp trong GitHub Actions để chạy Python orchestrator và fixture cùng namespace loopback, giữ được `--network none`; orchestrator gọi đúng AF CLI như trên. Không ép dùng `uses: zaproxy/action-af` nếu phải làm mất fixture isolation chỉ để gọi wrapper. Có thể smoke wrapper trong lane riêng sau khi core đạt; reuse AF engine đã đáp ứng mục tiêu dùng năng lực có sẵn của ZAP.

Các primitive cần tận dụng:

- `requestor`: method, headers, body, optional user, expected response code; đã có sẵn, không viết HTTP executor khác cho CSP. `responseCode` mismatch tạo warning, nên MVP bỏ field này khỏi plan và phân loại status bằng readback riêng để không nhầm thiếu evidence thành engine error. [Requestor](https://www.zaproxy.org/docs/desktop/addons/automation-framework/job-requestor/).
- `passiveScan-config` → `requestor` → `passiveScan-wait` → `report`: pipeline MVP. `maxDuration: 0` ở wait là chờ không giới hạn nội bộ, runner vẫn deadline 180 giây/case. [Passive wait](https://www.zaproxy.org/docs/desktop/addons/passive-scanner/job-pscanwait/).
- `report` template `traditional-json`: native alert artifact; adapter đọc `alertRef`, method, URI và JSON pointer. [Định dạng report](https://www.zaproxy.org/docs/desktop/addons/report-generation/report-traditional-json/).
- `spider`, `activeScan`, OpenAPI import, authentication, browser support là năng lực ZAP; sự tồn tại của add-on không chứng minh runner đã hỗ trợ. Mỗi lane mới phải kiểm tra job template/add-on trong image và chạy controls.

**Mã thoát không dùng chung:** packaged baseline/full/API: 0 thành công, 1 FAIL theo config, 2 WARN, 3 lỗi khác. AF mặc định: 0 không error/warning, 1 có error, 2 warning; `exitStatus` có thể đổi hành vi. MVP không thêm `exitStatus` fail theo mọi alert: `/control` cố ý phát alert. Python chịu trách nhiệm verdict case; AF nonzero là lỗi thực thi với native exit được giữ riêng. Không dùng `|| true`, `-I` hoặc `continue-on-error` để che lỗi suite.

## 4. Phân loại phạm vi

### A — bắt buộc, khả thi cao

- A1 schema/export deterministic, review candidate, add/delete/empty suite: **dễ**.
- A2 GET anonymous với fixture CSP, AF, report adapter: **dễ–vừa**, chủ yếu nâng cấp demo; điểm cần chứng minh là report không gộp mất instance và traffic đủ.
- A3 input thật từ RUN v3, evidence link/revision validation: **vừa**; cần adapter dữ liệu và negative tests, không phải bài toán suy luận tự động.
- A4 result/artifact/cleanup/deadline và GitHub xanh/đỏ thật: **vừa**, phải chạy hết checklist chứ không dừng ở YAML hợp lệ.
- A5 hướng dẫn skill và export bundle portable: **vừa**; tách Python assessment và runtime image.

### B — triển khai thử sau A, phạm vi hẹp và đo được

- B1 OpenAPI passive trên API local: **vừa**, dùng script có sẵn và một spec 2 endpoints. Không tuyên bố SOAP/GraphQL từ kết quả OpenAPI.
- B2 bearer token tĩnh từ env, một protected GET và token hết hạn: **vừa**. Chưa gồm login/refresh/SSO. Nâng profile khi có auth witness và redaction test thật.
- B3 active scan một rule đã chọn trên fixture vulnerable/fixed: **khó vừa**, rủi ro timing/detector. Thử thật trong lane manual, chưa mặc định PR.

### C — khó, phải tách spike khỏi stable support

- C1 cookie/form login + CSRF + mất session giữa run: **khó**. Có AF auth nhưng còn auth verification/refresh/readback.
- C2 browser journey SPA: **khó**. Crawl AJAX không tự chứng minh user journey cụ thể; cần browser script, selector, wait và proxy evidence.
- C3 BOLA hai actor + ownership + post-state: **khó**. ZAP gửi traffic được, oracle quyền và fixture là phần phải cài theo sản phẩm; zero alert không phải BOLA pass.
- C4 async job, TTL, OAST, WebSocket/GraphQL đặc thù: **nghiên cứu tiếp**, không nằm trong nghiệm thu stable của lượt này. Ghi lý do và interface cần thêm, không gắn unsupported thành Not applicable.

Mốc bàn giao bắt buộc: A hoàn chỉnh; B1–B3 có thử nghiệm runnable và kết quả; C1–C3 có spike nhỏ theo mục 10 nếu môi trường đáp ứng. Chưa có prerequisites thì ghi `BLOCKED` với dependency cụ thể và tiếp tục mục độc lập. Không giữ A chờ một spike khó, không nâng spike thành supported chỉ vì một run xanh.

## 5. Contract dữ liệu cụ thể

### 5.1 Đầu vào bộ sinh

Lệnh thêm mới:

```bash
zap-assessment regression generate --input reviewed-input.json --out-dir tests/security/cases
zap-assessment regression generate --input ci-mapping.json --run /private/RUN.json --case-id CASE_ID --out-dir tests/security/cases
```

Mode đầu chỉ nhận `source.kind=synthetic-demo`, nhãn này giữ tới result. Mode hai nhận RUN và mapping riêng; không chấp nhận `reviewed: true` do caller tự khai thay kiểm tra evidence. Không đọc file ngoài RUN thông qua JSON pointer hoặc source.path.

Mapping synthetic dùng đúng ví dụ sau. `observed` không được dùng làm expected assertion; expectation nằm ở `ci.expect` và phải có `basis`:

```json
{
  "source": {
    "kind": "synthetic-demo",
    "path": "docs/plans/zap-ci-suite-design-handoff.md",
    "caseId": "csp-docs"
  },
  "ci": {
    "id": "csp-docs",
    "profile": "passive-http-v1",
    "fixture": "csp-demo",
    "requests": [
      {"id": "docs", "method": "GET", "path": "/docs"},
      {"id": "control", "method": "GET", "path": "/control"}
    ],
    "requireResponses": {"status": 200, "mediaType": "text/html"},
    "expect": {
      "basis": "The documentation page must send an enforcing CSP header.",
      "alertRef": "10038-1",
      "presentOn": "control",
      "absentOn": "docs",
      "requireNonEmptyCspOn": "docs"
    }
  }
}
```

Output là object `schemaVersion: 1`, `source`, cộng các field trong `ci`; không chứa `observed`, timestamp sinh, absolute path, cổng, token, body từ RUN. Source product thêm `assessmentId`, `caseId`, `criterionIds`, plan revision/digest, locator operation/result đã lọc và digest evidence. Giữ ID nguồn ổn định; không commit raw RUN. Dùng đúng tên trường revision/digest từ contract hiện hành, không suy đoán bằng field fallback tùy ý.

Export RUN theo thứ tự:

1. Tìm duy nhất case trong `criteriaWorkflow.plan.cases`; lấy criterion IDs, expected behavior/basis/required evidence.
2. Xác thực plan binding hiện hành và result đúng case/revision/context, không chuyển evidence cũ sang build mới. Case `violated` có thể export test kỳ vọng đúng để kiểm tra fix.
3. Nối `caseResults[].evidenceLinks` tới `operations` bằng operation ID và JSON pointer `resultPath`; yêu cầu support đã readback, không dùng context-only hoặc pending/unknown operation. Reuse reviewer/validator phù hợp; thu hẹp lỗi đúng case, không yêu cầu criterion khác hoàn tất.
4. Kiểm tra CI mapping đủ fixture/request/response witness/control/assertion; bảo đảm expectation từ yêu cầu, không tự học từ alert count.
5. Sanitize source projection, validate rồi ghi file. Thiếu dữ liệu trả `MISSING_PREREQUISITE` + field/reason; operation ngoài profile trả `UNSUPPORTED_OPERATION`; input/schema lỗi trả `INVALID_INPUT`. Không thay cây case khi lỗi.

### 5.2 Validation và ghi file

- JSON Schema v1 dùng `additionalProperties: false` theo object; ID slug `[a-z0-9][a-z0-9-]{0,63}`, ID bước duy nhất, assertion trỏ ID tồn tại. Profile A chỉ GET, route literal bắt đầu `/`, cấm `//`, scheme, query, fragment, traversal/CRLF và credential fields. Chưa hỗ trợ query thì reject rõ, không strip query rồi so khớp.
- Filename phải `<id>.json`; duplicate ID trong suite, symlink case/output hoặc path escape đều lỗi trước traffic. Resolve fixture từ registry allowlist; case không được chỉ định Python module/shell command tùy ý.
- Canonical JSON: UTF-8, indent 2, sort keys, newline cuối; giữ array request order. Không đưa runtime metadata vào canonical file.
- Tạo mới bằng exclusive write. Existing giống byte: `UNCHANGED`, exit 0. Existing khác: `REVIEW_REQUIRED`, candidate JSON ra stdout, diagnostic ra stderr, exit 2; giữ nguyên file cũ. Không tự chấp nhận candidate.
- Ghi kết quả/runtime artifact atomic khi có thể. Output mỗi invocation là thư mục mới; không đọc report cũ để lấp output thiếu.

### 5.3 Runtime evidence và verdict

Fixture record sau khi gửi response thành công: request ID/method/path, status, media type, CSP-present/nonempty, run/case ID; không chỉ đếm request tới server. Fixture không tự gọi target để lấp witness. Chỉ ZAP requestor tạo traffic nghiệm thu. Health check, nếu có, ở route riêng và không được tính vào case.

Match alert bằng `(exact origin including port, HTTP method, path, alertRef)`; không chỉ hostname hay path. `pluginid=10038` không thay `alertRef=10038-1`. Parse report có site/alerts/instances đúng kiểu; alerts rỗng có thể hợp lệ, thiếu field cấu trúc không phải “không có alert”. Lưu JSON pointer instance, không invent native ID. Test cả two-instance report để phát hiện merge/cap.

Thứ tự quyết định cho CSP (theo chat trước):

1. Không chạy được ZAP, deadline, native exit nonzero, report mất/sai cấu trúc → `EXECUTION_ERROR`, reason riêng.
2. Thiếu response; response sai status/media; thiếu positive control alert; kết quả bị giới hạn hoặc không chứng minh drain hoàn tất → `MISSING_EVIDENCE`.
3. Prerequisites đủ và alert `10038-1` đúng GET `/docs` → `REGRESSION`, dù header readback có hay không. Giữ evidence pointer.
4. Không alert `/docs`, nhưng CSP header vắng/empty trong readback → `MISSING_EVIDENCE/INCONSISTENT_OBSERVATION`, không pass. Đây là contract thận trọng của MVP detector; tương lai có thể thêm assertion header độc lập với nhãn riêng.
5. Hai response đúng, control alert có, docs alert vắng, docs CSP nonempty → `PASS`.

Không claim CSP mạnh/an toàn XSS từ một rule “CSP missing”. Reason PASS phải nêu phạm vi hẹp đó.

Suite result chứa `schemaVersion`, `runId`, `commitSha`, `imageDigest`, ZAP/add-on versions khi lấy được, `caseCount`, counts bốn status, `cases[]` với id, source kind, case hash, status, reason, native exit, relative evidence/report paths. Lỗi suite trước discovery có `suiteError` và không giả một case đã chạy. Empty suite: `caseCount:0`, `status:EMPTY`, exit 0; summary ghi “0 tests”, không ghi security passed.

## 6. File/module phải tạo hoặc sửa

### Trong assessment package

- `src/zap_assessment/regression_export.py`: input adapter, RUN validation, canonical projection, candidate/no-op/write.
- `schemas/regression-case-v1.schema.json`, `schemas/regression-export-v1.schema.json`.
- Sửa `src/zap_assessment/cli.py`: thêm `regression generate`; lazy import exporter để không thay các command cũ. Giữ `regression.py` cũ.
- `tests/test_regression_export.py`: validation, provenance, determinism, overwrite và subprocess CLI.
- `examples/regression/csp-reviewed-input.json`: input ở trên; một RUN v3 synthetic riêng chỉ phục vụ contract test, luôn gắn nhãn synthetic.

### Runtime portable trong repo

- `tests/security/run_zap_suite.sh`: entrypoint host; đọc pin image từ một file `tests/security/zap-image.txt`; mount source read-only, output riêng writable; `--network none --hostname localhost`; trả đúng exit container, cleanup bằng trap; không `chmod 777` toàn repo.
- `tests/security/run_zap_suite.py`: discovery, validation, case isolation, fixture lifecycle, render plan, subprocess timeout, classify, result writer. Chỉ stdlib; khớp schema với validator nhẹ được test parity bằng corpus valid/invalid.
- `tests/security/zap_report.py`: parser/matcher riêng, tránh buộc import package assessment.
- `tests/security/fixtures/csp_demo.py`: tách HTTPServer hiện có, add response witness; mode healthy, csp-regression, wrong-status/media, missing-control cho qualification. Mode lỗi không là field người dùng bật trong committed stable case.
- `tests/security/cases/csp-docs.json`: **phải do generator tạo**, không chỉ viết tay rồi nói đã sinh.
- `tests/security/qualification/`: scenario builder và runner acceptance; tạo temporary suite/fixture config cho negative cases, không sửa và quên khôi phục stable case.
- `tests/security/test_zap_suite.py`, `test_zap_report.py`: unit/subprocess tests không cần live ZAP cho lỗi parser/input.
- `tests/security/README.md`: lệnh local, schema, thêm/xóa/cập nhật, status, artifact, giới hạn hỗ trợ.

### Workflow và skill

- `.github/workflows/zap-regression.yml`: stable PR/push branch/workflow_dispatch chạy suite thực tế; `permissions: contents: read`; upload artifact `if: always()`; job deadline 10 phút cho CSP, matrix qualification tách riêng khi mở rộng.
- `.github/workflows/zap-regression-qualification.yml`: contract tests + real ZAP controls, `strategy.fail-fast: false`; không che negative exit, harness assert expected status/exit rồi mới xanh.
- `$SKILL/references/ci-regression-suite.md`: quy trình skill chọn case → chuẩn bị mapping → export → review diff → handoff chạy CI; capability registry và cách ghi unsupported.
- Sửa `$SKILL/SKILL.md`: link reference ở read-when-applicable, giải thích test suite không thay assessment verdict và không tự phát traffic khi export.
- `docs/reviews/zap-regression-generator-acceptance-20261111.md`: báo cáo cuối có link run, SHA, artifact, scenario status, supported/experimental/blocked.

Portable nghĩa là có thể copy `tests/security/` vào repository mục tiêu và chạy bằng Docker mà không cần private RUN hay package assessment. Không xây installer/marketplace hay generic plugin framework trong lượt này. Chứng minh bằng bản copy sạch tới thư mục tạm ngoài repo và chạy một case.

## 7. Trình tự công việc và checkpoint

### P0 — chuẩn bị, không thiết kế lại

Kiểm tra HEAD/dirty state; giữ untracked demo. Tạo nhánh `codex/zap-regression-generator` khi bắt đầu implement. Xác nhận Python 3.13 ở exporter, Docker và quyền GitHub push/Actions. Dùng image digest demo làm pin ban đầu:

`zaproxy/zap-stable@sha256:030d3df57735dacbb83464854758e674dd9ad01d79d12a129a8e58b1fd384238`

Pull/inspect image, ghi ZAP version, Python runtime, add-ons/template. Nếu digest không dùng được, chọn digest thay thế và ghi lý do; không lặng lẽ chuyển sang mutable stable. Chạy demo cũ một lần để có baseline runtime mới.

### P1 — schema + generator

Implement module/CLI, input synthetic, product RUN adapter, các positive/negative contract tests. Sinh file CSP bằng CLI; hash lần 1/lần 2 bằng nhau. Sửa file đích bằng tay ở temp directory rồi generate lại để chứng minh không overwrite. Checkpoint: CLI thật, test thật, output case đọc được.

### P2 — runtime CSP

Tách fixture; dựng AF plan bằng serializer an toàn. Có thể xuất JSON (YAML-compatible) nếu `-autocheck` trên image xác nhận; nếu dùng YAML, serialize scalar bằng JSON quoting, không interpolate chuỗi raw của case. Bắt đầu GET only. Config `maxAlertsPerRule:0`, `alert.maxInstances=0`, `alert.mergeissues=false` là giả thuyết cấu hình cần kiểm chứng bằng two-instance negative control; không coi option xuất hiện trong command là đã hiệu lực.

Chạy ZAP process group có deadline 180 giây, terminate rồi kill sau grace 5 giây; session home riêng bằng `-dir`; log/output path không dùng từ case tùy ý. Wait `maxDuration:0`; report sau wait. Upload diagnostics khi lỗi nhưng không dùng report partial cho PASS. Tiếp tục case độc lập sau lỗi một case nếu runtime còn khả dụng. Luôn đóng server/thread/process ở finally.

Checkpoint: healthy, CSP removed, docs request omitted chạy **cùng code runner**, cho đúng ba status, report là do engine tạo trong run đó.

### P3 — artifacts, failure handling và portable

Thêm suite-results, evidence, plan đã render, native report, log, metadata/hash. Synthetic report có thể upload nguyên. Đối với auth/product, chỉ upload allowlisted projection, không chỉ regex thay token; test secret canary ở URL/header/body/log để xác nhận không lọt. Raw private được giữ ngoài upload path khi cần debug. Runtime result dùng raw trước sanitize; không làm mất field cần verdict.

Thêm add/delete/empty/duplicate và failure tests. Copy bundle sạch chạy lại. Checkpoint: local đủ acceptance A, không orphan process hoặc artifact cũ.

### P4 — GitHub Actions thật

Commit đúng các file thuộc tính năng và demo cần dùng, push nhánh của repo đích, tạo PR nếu quyền cho phép; không merge main. PR là đường chạy chính cho workflow mới. `workflow_dispatch` chỉ dùng sau khi workflow đã có ở default branch; đừng giả định `--ref` làm workflow mới chưa đăng ký dispatch được. Cho phép push trigger chỉ nhánh implement để thử trước PR nếu cần.

Chạy qualification và stable PR, tải artifact bằng `gh run download`, đọc JSON và kiểm tra head SHA. Tạo commit tạm bỏ CSP để stable job đỏ `REGRESSION`, rồi commit tạm bỏ request `/docs` để đỏ `MISSING_EVIDENCE`, cuối cùng khôi phục stable và chạy xanh. Dùng commit thường/revert, không force-push mất lịch sử bằng chứng. Record run IDs trước khi push tiếp để tránh nhầm run của SHA khác. User đã yêu cầu live workflow trong nghiệm thu; không dừng sau bước viết YAML.

### P5 — integration skill và case sản phẩm

Thêm hướng dẫn và ví dụ export. Dùng một RUN v3 thực có sẵn và một passive header case đã review nếu có quyền đọc. Không bịa sản phẩm từ synthetic fixture. Sinh mapping/suite cho build sản phẩm local disposable, chạy lại qua ZAP, chứng minh nguồn expectation và thiếu dữ liệu skill phải bổ sung. Nếu chưa có RUN/product fixture được phép sử dụng, báo **product-transfer BLOCKED**; A synthetic core có thể đạt riêng nhưng không tuyên bố end-to-end real assessment transfer hoàn tất.

### P6 — B/C spikes và báo cáo

Chạy theo mục 10, độc lập stable default. Cập nhật capability file/reference bằng kết quả. Không refactor rộng sau khi core đã đạt chỉ để chuẩn bị capability chưa có use case.

## 8. Nghiệm thu bắt buộc A — case và oracle

Mỗi mục phải có scenario ID, command, mode `offline`/`live-local`/`live-github`, expected, actual, status, output locator. Script harness assert status **và reason**, không chỉ nonzero.

1. **GEN-01**: input giống nhau → byte output giống nhau; source ổn định, không timestamp/cổng.
2. **GEN-02**: file tồn tại đã sửa → exit 2 + candidate, file gốc hash không đổi.
3. **GEN-03**: thiếu fixture/control/basis hoặc operation auth trong A → lỗi cụ thể, không ghi file/không traffic.
4. **GEN-04**: RUN đúng link được export; sửa revision, operationId, resultPath, context hoặc chuyển support sang context-only → reject. Dữ liệu fixture này là offline contract proof.
5. **LIVE-01**: healthy CSP → PASS; control alert `10038-1`, docs response witness và header nonempty.
6. **LIVE-02**: bỏ CSP docs → REGRESSION; report thật có instances cho cả control và docs đúng method/origin. Đây cũng là qualification cap/merge.
7. **LIVE-03**: omission request docs trong plan thử nghiệm, vẫn giữ docs trong required requests của case → MISSING_EVIDENCE/REQUIRED_RESPONSE_MISSING. Không xóa cả obligation rồi giả kiểm tra missing evidence.
8. **LIVE-04**: control cũng có CSP → MISSING_EVIDENCE/CONTROL_ALERT_MISSING; không pass vì cả report sạch.
9. **LIVE-05**: docs trả 302/401 hoặc wrong content type → MISSING_EVIDENCE, không nhầm login page là docs. Test redirect không dẫn sang ngoài origin; A fixture không external redirect.
10. **LIVE-06**: force deadline thật rất ngắn trong harness → EXECUTION_ERROR/TIMEOUT, giữ kết quả, đóng ZAP/fixture, chạy được case độc lập tiếp theo. Không cần tạo product chậm giả định.
11. **PARSE-01**: parser từ report live đã lưu; đổi port/origin, method, query, alertRef → không match. Không fabricate ID khi `instance.id` thiếu.
12. **PARSE-02**: missing/corrupt report, thiếu site/instances, report cũ từ invocation khác → không PASS. Mẫu offline được phép ở unit level, không gọi đó là live engine evidence.
13. **SUITE-01**: copy case thứ hai với ID/filename khác → count 2; xóa → count 1 và không output stale; xóa hết → EMPTY count 0. Không sửa workflow để thêm/xóa case.
14. **SUITE-02**: duplicate ID, invalid filename/schema, symlink escape → suite input error trước traffic. Một case runtime fail vẫn có result cho case sau.
15. **ART-01**: artifact có JSON parse được và references tồn tại; sanitized auth/product projection không chứa secret canary; không upload private RUN.
16. **PORT-01**: bundle ngoài checkout chạy cùng entrypoint, không PYTHONPATH assessment/MCP riêng tư.
17. **GH-01**: run stable trên GitHub xanh ở đúng commit; artifact tải và kiểm lại được.
18. **GH-02**: run stable regression trên GitHub đỏ, reason REGRESSION; artifact vẫn tải được.
19. **GH-03**: run stable missing traffic trên GitHub đỏ, reason MISSING_EVIDENCE; artifact vẫn tải được.
20. **GH-04**: commit phục hồi cuối xanh; các negative controls vẫn nằm trong qualification harness và đạt nhờ expected-failure assertions, không bị xóa để làm xanh.

Unit tests không thay LIVE/GH. Qualification harness xanh không thay GH-02/GH-03: hai mục đó cần thấy chính stable check đỏ đúng lý do. Exit 0 của Docker/ZAP không thay case PASS.

## 9. Lệnh, workflow contract và gói bằng chứng

Các interface sau là yêu cầu phải cài, không phải lệnh đã tồn tại:

```bash
# Exporter: dùng env Python 3.13 và requirements.lock hiện có
zap-assessment regression generate \
  --input .agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/examples/regression/csp-reviewed-input.json \
  --out-dir tests/security/cases

# Cùng entrypoint local/CI; host wrapper xử lý Docker
bash tests/security/run_zap_suite.sh --cases tests/security/cases --out artifacts/zap

# Harness tự tạo temp cases và gọi entrypoint thật
python3 tests/security/qualification/run_acceptance.py --scenario all --out artifacts/qualification

# GitHub: ghi nhận ID/SHA rồi chờ và đọc artifact thật
gh run list --repo hehuanglu/testing-tool --branch codex/zap-regression-generator
gh run watch RUN_ID --repo hehuanglu/testing-tool --exit-status
gh run view RUN_ID --repo hehuanglu/testing-tool --json headSha,conclusion,url,jobs
gh run download RUN_ID --repo hehuanglu/testing-tool --dir artifacts/downloaded/RUN_ID
```

Không dùng chuỗi placeholder `RUN_ID` nguyên văn; lấy ID từ kết quả list. Run failed dự kiến vẫn cần inspect jobs và artifact, không coi `watch` nonzero là lý do bỏ readback.

Workflow stable dùng checkout/upload-artifact pin SHA đã xác minh; timeout cấp job; `contents: read`; chạy wrapper trong step bình thường; upload `if: always()` và summary luôn được viết nếu có result. Không dùng secrets cho fixtures A; không `pull_request_target`. Artifact name chứa job/scenario/run attempt tránh collision, retention 7 ngày cho synthetic CI; báo cáo cuối lưu bản evidence tối thiểu đã sanitize vào repo để link run hết hạn không làm mất toàn bộ nghiệm thu. PR check ổn định tên `ZAP regression / suite`.

Mỗi run lưu:

```text
artifacts/zap/
  suite-results.json
  run-metadata.json
  csp-docs/
    case.json
    plan.yaml
    evidence.json
    zap-report.json
    zap.log
```

Trong báo cáo ghi run URL, head SHA, job conclusion, artifact tên/ID/digest nếu API có, hash case/runner/image, expected/actual từng control. Với engine start failure có thể không có report: result phải chỉ rõ missing artifact do lỗi, không viết JSON rỗng giả report ZAP. Không claim “all supported” nếu chưa thực chạy từng profile.

## 10. Thiết kế thử nghiệm B/C để Sol không phải tự chọn phương pháp

Mỗi spike ở `tests/security/experiments/<id>/`, có README, script, fixture/spec, result schema cùng bốn trạng thái nếu phù hợp và workflow manual/qualification riêng. Không đặt case thử nghiệm vào `cases/` stable. Giới hạn mỗi spike một happy path, một negative control, một missing-evidence/auth control. Nếu sau hai vòng sửa cùng một blocker vẫn thất bại, ghi chẩn đoán và chuyển spike khác; không thay scanner assertion thành mock để đóng việc.

### B1 — OpenAPI passive

Dựng API local gồm `/health` và `/items`, spec chỉ khai `/items`; phản hồi JSON. Dùng `zap-api-scan.py ... -f openapi -S`, assert actual traffic `/items`, spec target đúng local origin, JSON report mới. Negative spec trỏ route không có → thiếu coverage/lỗi setup, không PASS. Chạy hai lần cùng build. Đây là qualification import/API transport, không claim business authorization. Nâng profile `openapi-passive-v1` chỉ khi kết quả ghi route coverage và phân biệt import failure; không tự chuyển sang full active vì spec import không được.

### B2 — bearer tĩnh

Fixture `/private` chỉ trả JSON đúng marker khi token đúng, token sai trả 401. Lấy token từ env runtime và inject bằng requestor headers, không lưu vào case. Dùng positive response marker/actor witness; login HTML/401 là MISSING_EVIDENCE/AUTH_LOST. Header/alert assertion bổ sung được phép nhưng auth witness phải độc lập. Chạy good token, bad token, secret canary scan trong artifact. Nâng `bearer-passive-v1` chỉ sau ba control; không claim refresh/SSO.

### B3 — active scan giới hạn

Fixture HTTP local có một reflected-XSS endpoint vulnerable và bản fixed HTML-escape; chọn rule XSS active thực có trong image, ghi chính xác rule ID/version từ inventory. Seed URL rồi AF activeScan policy chỉ enable rule đó; scope context duy nhất fixture, deadline process 300 giây. Assert native alert đúng param trên vulnerable và vắng trên fixed **cùng evidence rule thực chạy/response đúng**. Nếu detector không ổn định, giữ experimental kèm run logs; không đổi thành “response contains payload” rồi gọi native ZAP alert. Full scan wrapper là smoke tùy chọn, không mở hết rule để cứu test thiếu hiểu biết.

### C1 — form/cookie/CSRF auth

Fixture `/login` cấp CSRF, POST login cấp cookie, `/private` kiểm session; mode revoke session giữa hai request. Dùng AF auth/context/users trên đúng add-on image; nếu cần script auth thì script được commit và hash. Oracle: private response marker trước và sau; revoke → AUTH_LOST/MISSING_EVIDENCE hoặc refresh có witness đúng actor. Cần chứng minh không anonymous scan được ghi authenticated. Kết quả chỉ qualify fixture auth protocol, chưa qualify mọi sản phẩm.

### C2 — browser journey

Fixture SPA có nút fetch `/private-data` chỉ sau click; browser script cố định mở trang/click/wait. Chạy browser qua ZAP proxy; pin browser/runtime version. Assert request marker trong ZAP history/readback và UI terminal marker; bỏ click phải thiếu evidence. Spider tự thấy route không thay thao tác click. Chưa có browser executor khả dụng thì BLOCKED với package/image thiếu; không dùng trình duyệt cá nhân của operator để tuyên bố CI reproducible.

### C3 — BOLA hai actor

Fixture có actor A/B và object do A sở hữu. Setup tạo object trong disposable fixture; GET owner A là positive control; GET bằng B phải 403, mode vulnerable cho B đọc được cùng object. Gửi qua ZAP, readback actor/object/status/body marker. Unauthorized success → REGRESSION theo **ZAP-derived custom oracle**, không native alert. Timeout/404/object sai/auth mất → MISSING_EVIDENCE. Cleanup readback và fixture reset phải chạy được sau failure. Không tái sử dụng oracle này cho mutation/async BOLA chưa được thử.

Tiêu chuẩn nâng capability stable: contract có version, scripts đọc được, hai run độc lập xanh ở healthy, negative control bắt regression, incomplete path không PASS, artifact sạch, cleanup đúng, một run GitHub thật. B3/C còn experimental nếu chưa đủ; A không phụ thuộc việc nâng này.

## 11. Hướng dẫn cập nhật skill

Reference mới phải cho agent quy trình ngắn, có đầu vào/đầu ra rõ:

1. Chỉ khi người dùng muốn lưu CI regression, chọn case có giá trị và evidence đủ từ assessment; không auto export tất cả 50 tiêu chí.
2. Phân loại profile theo capability đã qualification, không theo tên tool chung chung.
3. Chuẩn bị CI fixture/response witness/expected behavior/positive control; thiếu input báo chính xác dependency để bổ sung.
4. Chạy generator, review candidate diff và provenance; không chép secrets/raw reports vào Git.
5. Chạy suite local và workflow target; bàn giao cách thêm/xóa/cập nhật file case.
6. Giữ đánh giá assessment, dữ liệu historical và CI regression result tách biệt. Export không thay Gate 2; traffic sản phẩm chỉ theo phạm vi đã được cho phép, fixtures CI do feature dựng được test trong scope nghiệm thu này.

Thêm capability status với ba mức `supported`, `experimental`, `unsupported` kèm profile và link bằng chứng qualification. Không lấy “ZAP có API này” làm trạng thái supported của skill. Khi suite sau này dùng target khác, adapter và scope cần được thiết lập lại; không hard-code route demo vào logic product export.

## 12. Điều kiện kết thúc và nội dung Sol phải trả

Chỉ báo **A complete** khi GEN/LIVE/PARSE/SUITE/ART/PORT/GH trong mục 8 đạt, skill reference đã sửa và stable final SHA xanh. Phân biệt `A core complete`, `product-transfer blocked/qualified`, `B/C experiment status`; không gọi toàn tính năng end-to-end hoàn tất nếu real product transfer chưa có evidence.

Bàn giao gồm:

- Link PR/branch và SHA cuối, danh sách file chính, lệnh generate/run.
- Link run xanh cuối, run đỏ regression, run đỏ missing-evidence, qualification runs; lý do đỏ và artifact đã tải kiểm.
- Báo cáo nghiệm thu trong `docs/reviews/`, counts và scenario IDs, source labels synthetic/product, hash/pin.
- Danh sách capability stable/experimental/blocked, blocker cụ thể và bước tiếp theo; không thêm tuyên bố generic auth/BOLA coverage.
- Những test cũ đã chạy khi sửa CLI/export integration. Chạy focused tests trước; không cần scan lại sản phẩm để sửa docs.

Nếu GitHub thiếu quyền hoặc Actions bị tắt: giữ implementation local hoàn chỉnh, ghi thao tác GitHub đã thử và lỗi cụ thể, báo phần GH chưa nghiệm thu. Không thay bằng YAML lint hay chạy container local rồi ghi GitHub passed. Không merge main hoặc đổi permissions repo để vượt blocker.

## 13. Prompt bàn giao dùng nguyên văn

> Implement theo `docs/plans/zap-regression-generator-sol-implementation-plan-20261111.md` trong repo `hehuanglu/testing-tool`. Quyết định thiết kế đã chốt; ưu tiên code, script chạy thật và bằng chứng nghiệm thu. Hoàn tất A theo P0–P5, rồi thực hiện các spike B/C theo phạm vi và điều kiện dừng. Giữ file demo/untracked hiện có, không sửa verdict/approval của assessment để làm test xanh. Tạo nhánh `codex/zap-regression-generator`, commit/push các thay đổi thuộc nhiệm vụ và chạy workflow GitHub Actions thật; giữ bằng chứng run xanh, run đỏ REGRESSION và run đỏ MISSING_EVIDENCE, rồi phục hồi final xanh. Không merge main. Mỗi case là một JSON, CI chạy cùng entrypoint local và không gọi LLM. Không kết thúc ở plan, mock, YAML hoặc local-only. Báo riêng phần stable đã nghiệm thu, product transfer và experimental/blocker; mọi claim phải có script/run/artifact tương ứng.

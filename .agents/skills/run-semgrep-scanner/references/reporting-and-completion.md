# Hai file kết quả và completion

## Trạng thái ở hai chiều

Round: `completed`, `partial`, `blocked`, `interrupted`. Completed khi output đọc được và không còn lỗi làm thiếu mục tiêu lượt; exit/counts/errors lưu riêng. Có findings vẫn completed được. Partial khi còn phần thiếu; blocked khi chưa thực hiện được phần kiểm có nghĩa; interrupted khi bị ngắt.

Assessment và track: `completed`, `partial`, `blocked`, `stopped`. Completed khi inventory/scope và mức triage được giao đã xử lý, không còn bước đủ điều kiện bỏ ngỏ. Supported issues không tự làm partial. Partial khi có phần có nghĩa nhưng còn câu hỏi/source/triage cần thiết; blocked khi chưa kiểm được phần có nghĩa; stopped khi user yêu cầu dừng. Lỗi một nhánh không ngăn phần độc lập.

Questions: `resolved`, `open`, `blocked`, `not-applicable`. Resolved cần câu trả lời đủ căn cứ ở mức nhiệm vụ được giao, có thể là phát hiện issue. `needs-review` còn cần triage thì câu hỏi chưa resolved. Với candidates-only, có thể resolved ở mức phát hiện mẫu đã giao, nhưng phải nói triage ngoài yêu cầu; không gọi completed audit bảo mật. N/A cần căn cứ applicability, không từ thiếu rule.

## Handoff và phiên bản

Assessment mới mặc định dùng đúng **ALERTS.json** và **RUN.json cho mỗi track** ở `<assessment-root>/<track-id>/`, local ổn định ngoài source targets, không overwrite lịch sử. Theo [workflow tuần tự](sequential-track-workflow.md), lưu và tự kiểm cặp hiện tại trước execution track sau. Một track có thể có nhiều rounds; còn external dependency/blocker đã hết bước local khả thi thì bàn giao partial/blocked trung thực và tiếp tục track độc lập. User yêu cầu execution/report gộp thì giữ mapping từng track; mỗi cặp vẫn khép kín references cùng assessment.

Raw/log/rules/settings private riêng; không bắt folder evidence/archive/hash manifest hay EVALUATION file/canvas. Nhận định tự kiểm ở `tracks[].review` trong RUN; báo cáo đánh giá riêng chỉ tạo khi user giao. Evidence nhúng ALERTS theo [evidence contract](evidence.md). Audit/setup-only/sửa skill không sinh hai báo cáo assessment giả hoặc chạy lại product ngoài yêu cầu.

Schemas mới: `semgrep-tester-alerts-v2`, `semgrep-tester-run-v2`. Đây là contract ghi nhận, không schema framework/validator gate mới. Đọc v1 thì ghi evidence chưa có, không invent hoặc rewrite lịch sử.

Blocked trước scan: findings có thể `[]` nghĩa chưa có observations, nhưng native counts chưa biết để null; status/limitations nói chưa scan, không dùng 0 như kết quả sạch. Manual observations có thật vẫn giữ nguồn manual. Phân biệt empty array đã biết không có phần tử với null chưa có dữ liệu.

## Kiểu dữ liệu chung

IDs là string duy nhất trong collection, references phải trỏ record có thật cùng assessment. Timestamps ISO 8601 có timezone khi biết, null khi chưa biết/không thực thi (như ví dụ synthetic). Location là `{path, start, end}`: path product-relative, start/end là `{line, column}` với số 1-based khi biết, null khi chưa biết; không invent vị trí. End theo native output khi có, không suy thêm range. Inventory nhiều roots ghi root mapping trong product/source state để path không nhập nhằng.

Các mảng được biết không có phần tử dùng `[]`; counts/fields chưa quan sát null. Free-text mô tả đã lọc, không token/password/raw headers/source nhạy cảm. Một kết luận chung không thay các liên kết hỏi–thao tác–finding/evidence.

## ALERTS.json

Top-level: `schema`, `assessment_id`, `status`, `summary`, `findings`.

`summary`:

- `native_matches_by_round`: mỗi round ID → số native results thực đọc được hoặc null, kể cả inventory-only matches nếu có; không ép bằng số security findings.
- `finding_records`: số records observations sau aggregation; không phải số vulnerabilities.
- `unique_issues`: nullable nếu chưa dedup/triage đủ; chỉ tính issues được support theo phương pháp ghi, không cộng false-positive/needs-review thành vulnerabilities.
- `by_source`, `by_native_severity`, `by_triage`: counts theo đơn vị finding records. Native severity chỉ Semgrep records có field thật; manual/null severity tách riêng bằng `native_severity_null_records`. Không ép manual vào ERROR/WARNING/INFO.
- `counting_method`, `deduplication`: mô tả đơn vị/mapping, grouping occurrences và phần chưa xác định. Native matches qua các lượt khác current records/root causes.

Mỗi finding có đủ:

- `id`, `source` (`semgrep`/`manual-source-review`), `track_ids`, `question_ids`, `round_ids`, `manual_review_ids`.
- `rule_id`, `native_severity`, `native_confidence`, `message`: native fields null nếu manual hoặc tool không có. Manual claim nằm ở triage/evidence, không dựng native message. Native message có sensitive interpolation thì redact có ghi chú.
- `locations`: source/config locations thực. `occurrences`: `{id, round_id, native_rule_id, location, native_identifier}`; native_identifier nullable khi không có. Manual không tạo native occurrence giả. Mỗi native occurrence liên kết đúng round; round_ids có thể nhiều lượt.
- `related_finding_ids`: observations cùng root cause đã biết; không bắt gộp khi chưa đủ. Nếu aggregate nhiều rules, giữ occurrence native_rule_id; rule_id là ID chung nếu xác định được, nếu không null kèm giải thích.
- `triage`: `{status, rationale, impact, assumptions, next_step}`. Status `needs-review`, `supported`, `false-positive`, `not-applicable`; impact nullable nếu chưa xác định, assumptions mảng, next_step nullable nếu không còn việc cho record. Evidence hỗ trợ rationale/control review.
- `tester_priority`: null hoặc `{value, rationale}`, tách native severity; không map tuỳ ý WARNING thành CVSS.
- `evidence`: mảng records theo [evidence](evidence.md); `evidence_gaps`: mảng thông tin thiếu ảnh hưởng nhận định, không bịa để đủ fields.

## RUN.json

Top-level fields phải hiện rõ:

- `schema`, `assessment_id`, `status`, `started_at`, `finished_at`, `product` (path/roots/languages/frameworks và thông tin revision có thật), `scope` (yêu cầu/nguồn, gồm mức triage và exclusions).
- `source_states`: `{id, roots, observed_at, revision, dirty, notes}`; revision/dirty null nếu không biết/không có Git. Ghi change notes khi source đổi; không bắt snapshot/hash.
- `tracks`: `{id, scope, selected_base_ids, applicability, status, remaining_question_ids, rationale, review}`. Applicability mô tả fact/nguồn/giới hạn (có thể object hoặc text), status theo assessment enum. Track không áp dụng có thể completed với rationale không có trách nhiệm áp dụng, không đặt status N/A ngoài enum. `review` ghi tự kiểm hai chiều như dưới; không default pass từ exit/checker.
- `inventory`: `{id, kind, name, locations, discovery_source, certainty, track_ids, scope_decision}`. Kind surface/module/function/config phù hợp product; có protocol/entrypoint/input khi hữu ích. Không sinh inventory từ findings whitelist.
- `questions`: `{id, question, base_question_id, track_id, surface_ids, expectation, expectation_source, techniques, round_ids, manual_review_ids, result, status, next_step}`. Base nullable cho phát sinh, surface_ids trỏ inventory. Expectation phân biệt provided policy với source hypothesis; techniques là những cách chọn/dùng có ghi mức thực thi.
  Ghi thêm `closure_condition`, `recorded_at`, `introduced_after_round_id`, `changes` theo [checkpoint](tester-workflow.md). `result` có thể là text hoặc object để tách source fact/policy dependency/bước còn làm được; không default verdict. Đây là bổ sung v2, không rewrite báo cáo lịch sử thiếu các fields mới.
- `rounds`: `{id, purpose, started_at, finished_at, command, cwd, targets, source_state_id, engine, version, rules_selection, exclusions, privacy, exit_code, errors, skips, timeouts, counts, status, finding_ids}`. Command/argv redacted. Rules selection ghi file/ID/origin và configured vs actual capability. Privacy ghi settings/metrics/version check/guard thực, không suy network blocked từ metrics off. Exclusions/suppressions và source paths bị thiếu phải hiện. Unknown errors/skips nếu output không đọc được để null.
- Round counts: `native_matches`, `rules_configured`, `rules_loaded`, `rules_executed`, `candidate_files`, `scanned_files`, `skipped_files`, `excluded_binary_files`: số thực hoặc null. Không suy loaded/executed từ YAML hoặc time.rules, không suy counts bằng phép trừ inventory khác đơn vị.
- `manual_reviews`: `{id, question_ids, source_state_id, locations, call_paths, observations, controls, expectation, finding_ids, evidence_ids}`. Ghi implementation đã đọc, tách native execution. Manual steps/locations đúng source state, không fake Semgrep trace.
- `coverage`: mapping questions/source đã xử lý, skipped/unsupported/chưa đọc/chưa triage và ảnh hưởng; unit rõ, không đổi files scanned thành endpoint/role/runtime coverage.
  Chỗ thống nhất cho inventory matches là `coverage.inventory_candidate_reviews`, mẫu dưới. Không tạo inventory surface mới chỉ để chứa mỗi match.
- `limitations`, `unperformed`, `next_steps`: phần ảnh hưởng, lý do, việc đã thử và điều kiện tiếp tục. Giữ mọi remaining_question_ids; hành động còn khả thi phải làm trước handoff theo [vòng trách nhiệm](responsibility-loop.md).

## Tự kiểm của operator trong RUN

Với assessment mới, mỗi `tracks[].review` ghi gọn:

- `reviewed_at`: thời điểm tự kiểm có thật; `reviewer_mode`: `operator-self-review`, hoặc mô tả reviewer thực nếu user có giao. Cùng operator tự đối soát không thành independent/senior approval.
- `process_assessment`: nhận định quy trình đủ cho scope/claim/mức triage đã giao chưa, căn cứ inventory/question/round/manual review và gaps cụ thể. Có thể là object hoặc text với references rõ.
- `evidence_assessment`: nhận định native accounting, triage/claim/control, source locations/provenance và coverage đã đủ hỗ trợ danh sách records hiện tại chưa; tách native/semantics khỏi bookkeeping checker.
- `remaining_dependencies`, `next_steps`: external policy/runtime/source/capability còn thiếu và điều kiện tiếp tục, gắn question IDs liên quan. Không ghi source step còn làm được rồi chuyển track như đã xử lý. `[]` khi thực sự không còn phần tương ứng.

Hai nhận định độc lập với `status`: có supported issue không tự làm quy trình kém; evidence đủ cho một needs-review record không làm assessment completed khi triage cần policy còn mở. Không bắt numeric score, oracle, source hashes hoặc reviewer thứ hai. Không thêm review fields vào báo cáo lịch sử để giả đã tự kiểm tại thời điểm cũ; v2 hiện có vẫn đọc theo dữ liệu thật.

## Đối soát và retest

### Inventory candidate ledger trong RUN

```json
{
  "id": "C-01",
  "round_id": "R-01",
  "native_result_index": 0,
  "rule_id": "detector-id-from-native",
  "location": {"path": "relative/source.ts", "start": {"line": 10, "column": null}, "end": {"line": 10, "column": null}},
  "question_ids": ["Q-01"],
  "manual_review_ids": [],
  "candidate_kind": "receiver-not-yet-established",
  "context_read": [],
  "disposition": null,
  "finding_ids": [],
  "next_step": "Read receiver import/constructor and callers."
}
```

Ví dụ synthetic chưa có review. `native_result_index` là index 0-based trong results của đúng round; null nếu không khôi phục được, không invent. Trong workflow mới, dùng ledger này để đối soát mọi native result của round, gồm inventory-only và security-observation results: mỗi `(round_id, native_result_index)` có một disposition record, có thể nối nhiều findings khi mapping thực cần. Nếu output thiếu thì giữ phần biết được, ghi accounting gap/status thay vì invent đủ hàng. Disposition do tester ghi (open, inventory-only-closed, promoted-to-observation hoặc mô tả cụ thể), không phải vulnerability verdict tự động. Candidate không vào ALERTS vẫn giữ trách nhiệm, context và next step. Native counts giữ **mọi** results, không bằng số candidates/ALERTS. Nhiều detector tại một location có thể chia sẻ manual review nhưng giữ từng native index/rule/message gốc; chỉ tester quyết định chung issue/root cause.

### Helpers nhẹ, không là approval gate

`scripts/report_records.py` khởi tạo draft hoặc question null đúng nghĩa, không chọn status/verdict/policy/completion. `scripts/record_round.py` thu execution/output vào vùng private, không triage. `scripts/check_report_links.py RUN.json ALERTS.json` chỉ đọc/kiểm IDs, references, counts biết được và provenance. Lỗi chỉ rõ record/field, không tự sửa evidence/lịch sử. Xem cách dùng trong [operations](semgrep-operations.md) và [tests](../tests/README.md). Không kiểm evidence đúng với source, không chứng nhận verdict và không phát sinh file handoff thứ ba.

Parse JSON, đối chiếu assessment/status/IDs hai chiều, occurrence→round, evidence→source_state/thao tác, manual_review→evidence/finding, questions→inventory/base/track và remaining questions. Counts theo đơn vị đã khai báo, không suy vulnerabilities từ tổng records. Round/source state phải tương ứng evidence; source thay đổi thì đọc/chạy lại phần ảnh hưởng hoặc giữ limitation rõ.

Retest dùng source diff/rules/paths/ignore/engine thực; mất match do suppression/filter/rule change chưa là fixed. Không sửa native/history/verdict cũ. Kết quả hiện hành phải nói phần nào chưa retest.

Xem [ví dụ synthetic nhất quán](../examples/README.md) và [validation](validation.md). Ví dụ không có trace/output runtime thật. Phản hồi cuối **Vận hành** (việc thật, kết quả, mức hoàn tất từng track, links hai file) và **Hạn chế** (phần chưa làm, đã thử, điều kiện tiếp tục, giới hạn nhận định); chỉ sửa skill thì báo thay đổi/validation, không tạo assessment product.

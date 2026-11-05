# Kết quả implement ZAP workflow phase 2

Ngày 02/11/2026. Đã triển khai theo [kế hoạch phase 2](zap-workflow-phase2-implementation-plan-20261102.md), trên working tree có sẵn tại HEAD `18f17860bad327a18345f949644aac4d40b7fece`; giữ các thay đổi trước lượt này.

## Phần đã implement

- Hai core module mới: `coverage_presentation.py` cho historical/current views, import history có source binding, criterion counts và work-unit identity; `residual_review.py` cho residual atoms, kiểm tra refs/source text, diagnostics, nhóm next work và quyết định có giới hạn extent.
- Tích hợp vào scope/report/selector: giữ legacy coverage cùng coverageMeaning, N/A/exclusion riêng, historical selectedTracks, discovery/track extent, không đếm trùng case/question. Retained aggregates và câu hỏi refine có revision/boundary/cycle guards; child observed không đóng aggregate.
- CLI chỉ đọc `scope review-residuals`, `scope inspect-resume`; optional residual context cho next-work, execution/planning proposals riêng. WorkingInputs có path/pointer/context validation; compact report bị từ chối khi dùng làm internal `--previous`. Thiếu metadata không cấm lưu checkpoint.
- Bundle validator và sanitizer giữ semantic refs, kiểm tra derived presentation/summary/residual consistency và loại raw/credentials. Evidence resolver, admission và unknown-effect safety giữ nguyên. Ba implementation pin functions thêm hai dependency mới cho allocation tương lai; không sửa pins lịch sử.
- Ba test module mới và regression bổ sung trong business discovery, security scope, selector, checkpoint và adapter. Cập nhật SKILL cùng tám reference được yêu cầu, không viết lại toàn bộ hướng dẫn.

Các file code/tests nằm trong [assessment library](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/); hướng dẫn bắt đầu ở [SKILL.md](../../.agents/skills/mcp-zap-repo-operations/SKILL.md). Chi tiết contract ở [user security scope](../../.agents/skills/mcp-zap-repo-operations/references/user-security-scope.md), resume ở [retention/recovery](../../.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md).

## Kiểm tra thực chạy

Python 3.13.2: `/tmp/zap-skill-audit-20261102-venv/bin/python`; bảy dependency khớp requirements.lock, không cài mới. Baseline đúng bộ 17 module: **193 tests, 185 pass, 8 skip optional source**. Bộ cuối gồm ba module mới và 17 module regression: **235 tests, 227 pass, 8 skip**, không failure. Lệnh được ghi trong [operational validation](../../.agents/skills/mcp-zap-repo-operations/references/operational-validation.md#phase-2-offline-verification--2026-11-02).

Đã kiểm tra script entry từ cwd ngoài repo cho review-residuals, next-work, inspect-resume và report; report tạo đúng ba file và validate được. Foreign refs trả nonzero. Skill validator, syntax/YAML, links/anchors và diff whitespace được kiểm tra. Nhật ký nằm ở `.local/zap-workflow-phase2-implementation-20261102/`.

Walkthrough phát hiện và đã sửa các lỗi tích hợp: query evidence/planning không được đòi ALERTS của unrelated historical mappings; assessment source path và coverage product slug phải so trong namespace riêng; report không có security catalog vẫn giữ scopeRevision đã khai cho working-input resume. Có regression cho các đường này.

## Preview offline 100ms

Bundle preview riêng, không đổi officialRunPath:

- [RUN.json](../../.local/zap-workflow-phase2-preview-84f1dd0a78/reports/RUN.json)
- [ALERTS.json](../../.local/zap-workflow-phase2-preview-84f1dd0a78/reports/ALERTS.json)
- [SCOPE_ALERTS.json](../../.local/zap-workflow-phase2-preview-84f1dd0a78/reports/SCOPE_ALERTS.json)

Expected decisions được ghi trước projection trong [expected.json](../../.local/zap-workflow-phase2-preview-84f1dd0a78/expected.json); [actual.json](../../.local/zap-workflow-phase2-preview-84f1dd0a78/actual.json) đối chiếu chính xác input. Adapter preview mới nằm ngoài skill và không import/chạy report.py cũ.

- SEC-A01-03: historical partial vẫn hiển thị, current mapped questions chưa có observations; không chuyển thành current credit.
- SEC-A05-01: lịch sử DOM cùng JOIN-name delta được trình bày riêng, không suy ra mọi rendering context an toàn.
- SEC-A01-05: tenant policy/model là dependency thật, applicability unknown; không N/A.
- SEC-A06-02: tách preparation cho semantic mapping/readback kết quả processing đã giữ khỏi dependency thiếu exact historical causal telemetry. Không sửa nhãn old blocked attempts, không yêu cầu scan mới để nâng coverage.
- SEC-A07-01: local N/A; upstream password assessment ngoài target, không có local password execution queue. SEC-A09-01 vẫn là catalog obligation mở ngoài ZAP method.
- Hai JOIN questions vẫn observed/matched; ba effects resolved, partial/unknown history giữ nguyên. Bốn legacy question/case refs thành hai work units. Discovery delta ghi rõ 16 reviewed groups, 2 mapped và 14 no-additional-question; không gọi đó là 16 retests.

Chỉ review 8 criterion được chọn; **42 criterion ngoài lượt review và tổng 61 unreviewed refs** vẫn hiện. Quyết định `continue` nghĩa là có việc preparation hữu ích trong phạm vi đã review, không có executable action được chọn; không phải cho phép thực hiện preparation của product trong lượt implementation này. Assignment và DAST đều **partial**. Coverage presentation có 40 historical-only, 4 historical-with-current-delta và 6 N/A, mẫu số 50 criteria.

Walkthrough có **0 network và 0 dispatch calls**. So byte/hash trước/sau xác nhận cả hai bundle chính thức và private inputs không đổi; operations, actionHistory, finding IDs, native instances/counts và currentRetest không đổi. Không sửa adapter lịch sử, sản phẩm, Docker/runtime, personal skill; không commit/push.

## Giới hạn và điểm dừng

Mục tiêu implementation phase 2 hoàn tất. Đây là nghiệm thu offline về contract/reporting/planning và retained-data walkthrough; không phải fresh runtime qualification, review toàn bộ residual cũ hay chứng minh whole-product discovery. Helpers kiểm tra cấu trúc và mapping; tester vẫn chịu trách nhiệm ý nghĩa, đầy đủ nguồn và scopeBasis. Lớp presentation/residual không cấp evidence hoặc risk acceptance. W03/W04 runtime breadth và các preparation được preview nêu ra thuộc assignment vận hành riêng, không tự mở trong lượt này. Không cần chat mới để hoàn tất scope implementation đã giao.

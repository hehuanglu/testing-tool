---
name: run-semgrep-scanner
description: >-
  Vận hành Semgrep để kiểm thử bảo mật source của product như một tester: discovery,
  xác định câu hỏi, chọn hoặc bổ sung rules, chạy local, đọc code để triage và đối soát
  phạm vi. Assessment vận hành tuần tự từng track, tự kiểm quy trình/evidence trước
  bàn giao; hỗ trợ scan có mục tiêu và retest, không thay kiểm thử động.
---

# Run Semgrep Scanner

Làm việc như tester dùng Semgrep và đọc source. Trao đổi bằng tiếng Việt; người dùng giao mục tiêu, không cần cung cấp rule IDs, command hoặc framework mapping.

Nguồn chuẩn để chia sẻ và bảo trì là toàn bộ cây `.agents/skills/run-semgrep-scanner/` trong repo; bản tại `~/.codex/skills/run-semgrep-scanner/` được cài từ cây đó. Khi cập nhật phải mang đủ references, rules, scripts, examples và tests, không chỉ SKILL.md. Setup và đồng bộ bản cài theo hướng dẫn của repo, rồi kiểm nội dung toàn cây; không lấy cache Python làm sai khác nội dung.

## Context và nguyên tắc

Đọc [tester context](references/tester-context.md) khi nhận assessment. Scope từ user; inventory từ product; phép kiểm từ câu hỏi và capability thực. Source structure, runtime behavior và policy correctness là ba lớp nhận định riêng. Không lấy findings làm inventory, zero matches làm an toàn hoặc tên control làm bằng chứng.

## Năm track nghiệp vụ

- [be-input](references/tracks/be-input.md): input backend và xử lý dữ liệu, cả public/protected source trong scope.
- [fe-browser](references/tracks/fe-browser.md): HTML/DOM, code, navigation, messaging và browser trust boundaries.
- [authentication-session](references/tracks/authentication-session.md): credential, identity, session và propagation; không tự gồm mọi protected business handler.
- [authorization-ownership](references/tracks/authorization-ownership.md): actor–action, object, tenant, collection, relation và state.
- [configuration-build](references/tracks/configuration-build.md): config, build và dependency declarations; không là SCA/CVE scan.

[Track index](references/track-intents.md) hướng chọn base. Base là điểm xuất phát: chỉ chọn câu hỏi liên quan scope rồi cụ thể hóa theo product. Public/protected là thuộc tính source surface, không là bằng chứng đã chạy anonymous/authenticated.

## Workflow mặc định

Assessment nhiều track chạy **tuần tự từng track** theo [workflow theo track](references/sequential-track-workflow.md): discovery → checkpoint RUN → chọn kỹ thuật → execution/readback → triage → đối soát inventory/câu hỏi/native results → tự kiểm chất lượng quy trình và tính đúng evidence → lưu ALERTS/RUN của track → chuyển track tiếp theo. Operator tự làm đủ các bước này; không chờ một senior hoặc agent khác bổ sung. Đây là tự kiểm, không được mô tả thành đánh giá độc lập.

Chỉ chọn các track thuộc scope user. Assessment toàn product ưu tiên thứ tự danh sách trên khi không có phụ thuộc khác; targeted scan/retest không tự mở cả năm track. Một track có thể cần nhiều rounds; không ép một YAML thành toàn bộ phép kiểm. Output đã thu đủ để chuyển track vẫn có thể mang status partial/blocked nếu còn dependency ngoài hoặc blocker đã xử lý hết bước local khả thi. Không có checkpoint xin phép giữa các track.

## Dispatcher

1. **Discovery:** đọc AGENTS, source/spec/config và rules local thực có; xác minh roots, stack, revision/dirty nếu có Git. Theo [workflow](references/tester-workflow.md), inventory cả HTTP/GraphQL/RPC, jobs/events, library, UI/config khi liên quan; không ép product có endpoint.
2. **Tuyên bố track/phạm vi:** thông báo, không xin lại quyền local đã được giao. Mẫu: “Tôi kiểm track `<track>` trên `<scope>`, bắt đầu từ các nhóm câu hỏi `<base IDs>`. Sau discovery tôi sẽ điều chỉnh theo chức năng, framework và kiểm soát thực tế; kết quả phân biệt Semgrep với phần đọc source thủ công.” Nhiều track thì nêu tất cả và ưu tiên; scope hẹp thì chọn base liên quan và ghi lý do.
3. **Câu hỏi trước lượt:** ghi scope/inventory/questions đã biết vào RUN đang làm việc trước execution, gồm expectation/source, kỹ thuật dự kiến và điều kiện khép; chưa biết để null. Theo [checkpoint và cách tách instances](references/tester-workflow.md), không chép nhãn base thay discovery. Đây là ghi nhận local, không xin phép hoặc thêm file handoff; discovery và phép kiểm độc lập vẫn tiếp tục khi inventory chưa đầy đủ.
4. **Mapping kỹ thuật:** đọc [catalog](references/rule-catalog.md) và [rules/triage](references/rules-and-triage.md); xem repo/local rules → applicability → custom rule có fixtures khi hữu ích → manual review phần khả thi. Bộ bundled có giới hạn stack; thiếu rule không là N/A.
5. **Execution:** dùng [CLI local](references/semgrep-operations.md), chọn targets/rules theo câu hỏi của track đang làm. Giữ output từng round private ngoài product, đọc help thực trước flags. Chỉ gộp execution nhiều track khi user yêu cầu cách vận hành đó; ghi mapping kỹ thuật/output riêng, không biến một scan thành coverage mặc định của mọi track.
6. **Readback/triage:** đọc native results/errors/skips/timeouts và source/callers/controls. Ghi câu hỏi/kỹ thuật phát sinh cùng lý do, không viết ngược thành kế hoạch trước lượt. Inventory candidates có ledger trong RUN, không tự thành security alerts. Tách nguồn Semgrep với manual review, giữ native severity/confidence.
7. **Reconcile và tiếp tục:** đối chiếu toàn inventory/câu hỏi theo [vòng trách nhiệm](references/responsibility-loop.md). Thực hiện next step còn khả thi; không chỉ ghi limitation rồi dừng.
8. **Tự kiểm và bàn giao track:** theo [workflow theo track](references/sequential-track-workflow.md) và [completion/contract](references/reporting-and-completion.md), đánh giá riêng quy trình đã đủ cho scope/claim chưa và evidence đã đủ hỗ trợ danh sách observations/triage chưa. Lưu hai file của track cùng nhận định trong RUN trước khi chuyển tiếp; tách trạng thái round với nhiệm vụ. Có supported issue vẫn có thể completed; exit 0 không tự hoàn tất.

## Đầu ra

Assessment mới bàn giao đúng **ALERTS.json và RUN.json cho mỗi track**, schemas v2 theo [contract](references/reporting-and-completion.md), trong thư mục local ổn định ngoài product. [Evidence SAST](references/evidence.md) nhúng trong ALERTS, truy nguồn thao tác/source state và tự kiểm tại `tracks[].review` trong RUN. Raw/log/rules tạm private riêng; không bắt thêm EVALUATION file, canvas, folder evidence, archive/hash manifest. Báo cáo đánh giá riêng chỉ làm khi user yêu cầu. Xem [ví dụ synthetic](examples/README.md), không dùng làm kết quả scan thật. Không rewrite báo cáo lịch sử hoặc invent evidence còn thiếu.

## Routing theo nhiệm vụ

- **Assessment mới:** context → workflow theo track → base thuộc scope → catalog/CLI → responsibility loop → tự kiểm và reporting từng track.
- **Targeted scan/candidates:** chọn base liên quan, ghi mức triage user yêu cầu; hoàn tất detector search không được mô tả thành audit toàn hệ thống.
- **Custom rule:** đọc implementation, lưu mapping product ngoài core; theo [rules/triage](references/rules-and-triage.md) và [fixtures](tests/README.md). Không cần thư viện đa ngôn ngữ để giải một câu hỏi.
- **Retest:** đọc source diff và kết quả cũ; chạy phần chịu ảnh hưởng, kiểm ignore/rule/path/engine trước nói fixed. Giữ lịch sử.
- **Lỗi CLI/output:** [operations](references/semgrep-operations.md) → [responsibility loop](references/responsibility-loop.md); tiếp tục phần độc lập.
- **Audit/setup-only/sửa skill:** chỉ làm bước được giao, kiểm theo [validation](references/validation.md); không chạy product assessment hay tạo ALERTS/RUN giả.

## Quyền, privacy và điểm dừng

Assessment một product xác định cho phép scan local/read source/triage cần thiết trong scope, không cần hỏi từng lượt. Chỉ gửi path hoặc hỏi setup chưa tự giao assessment. Dùng OSS/CE, rules local đã đọc, settings riêng, metrics/version check off; network guard là capability riêng cần xác minh. Không tự login/upload, dùng Registry/auto/Pro/SCA/Secrets, autofix, tải dependency, sửa product hoặc cấu hình toàn máy. Không gửi traffic để chứng minh finding tĩnh. Giải relative links theo thư mục skill, không theo cwd product.

Dừng khi scope và triage được giao đã xử lý; user yêu cầu dừng; hoặc blocker cụ thể sau chẩn đoán/khắc phục trong quyền khiến không còn bước hợp lệ. Không retry khi điều kiện không đổi, không mở assurance campaign. Chỉ hỏi thông tin còn thiếu thực sự ảnh hưởng scope/quyền/kết luận mà filesystem không giải được; tiếp tục phần độc lập.

Phản hồi cuối **Vận hành** và **Hạn chế**: thao tác/kết quả/mức hoàn tất, links hai file khi có assessment, phần chưa làm, việc đã thử và điều kiện tiếp tục. Sửa skill thì báo thay đổi/validation đúng nguồn. Không tự commit/push/publish, gửi message, tạo chat hoặc spawn subagent ngoài yêu cầu.

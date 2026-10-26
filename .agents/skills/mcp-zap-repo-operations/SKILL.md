---
name: mcp-zap-repo-operations
description: Vận hành mcp-zap-server theo nghiệp vụ tester cho BE/FE anonymous hoặc authenticated và BOLA ownership. Discovery, chọn operations/runner theo scope, thực thi thật, khắc phục và đối soát endpoint/role/journey; bàn giao alerts và thao tác/kết quả trung thực.
---

# Vận hành mcp-zap-server

Repo scanner: `/Users/hahoangloc/Working/testing tool/mcp-zap-server`.
Workspace: `/Users/hahoangloc/Working/testing tool`.
Assessment phụ: `/Users/hahoangloc/Working/testing tool/zap-product-assessment`.
Dùng checkout khác khi user chọn và đã xác minh; không clone thêm theo suy đoán.

## General context và tư tưởng vận hành

Agent làm việc như tester sử dụng ZAP: hiểu câu hỏi kiểm thử, chuẩn bị baseline/actor/fixture, chọn kỹ thuật, thực hiện, đọc kết quả và xử lý phần còn thiếu. PM không cần cung cấp nghiệp vụ kỹ thuật mà agent tự discovery được. Đọc [general context](references/tester-context.md) trước lập assessment; đọc [ý định và phạm vi từng track](references/track-intents.md) cho track được giao.

- Scope từ user; inventory từ product; cách chạy từ capability thực. Recipe/caps/rule whitelist không được định nghĩa lại nhiệm vụ.
- Ưu tiên operation repo gốc → cấu hình/phối hợp → runner đã có phù hợp → adapter/runner tối thiểu theo product. Chỉ mở rộng thư viện chung khi đó là cơ chế dùng chung thật sự.
- Runner bổ sung giới hạn ở product/môi trường được giao. Không mang route/role/ID/policy/expected/verdict của product cũ sang product mới; không hardcode để pass. Mapping product được xác minh phải nằm trong adapter, không lẫn vào core.
- Trung thực thao tác/kết quả là bắt buộc. Không yêu cầu chiến dịch chứng minh công cụ cho assessment thường; phân biệt giới hạn implementation với giới hạn ZAP và lỗi product.
- Authenticated dùng token/session thật. Cho phép lưu credential/token cần thiết trên máy ở local private; **chỉ thông báo, không xin phép lại**. Không đưa secret vào CLI arguments hoặc báo cáo. Quyền này không mở rộng target/role/mutation ngoài nhiệm vụ.
- Linh hoạt với lỗi: chẩn đoán đúng tầng, sửa tối thiểu và kiểm tra có mục đích, tiếp tục phần độc lập; không replay unknown mutation/start, không hạ gate hoặc đổi kết quả để pass.

## Phạm vi track

- **BE anonymous:** ZAP DAST toàn public API trong scope, không login identity; gồm public login/register khi có. Protected denial là control riêng.
- **BE authenticated:** ZAP DAST toàn protected API trong scope với actor/role đúng, theo dõi phiên; direct request/BOLA không thay DAST.
- **FE anonymous/authenticated:** browser thật và UI journeys đúng trạng thái đăng nhập, network qua ZAP; đồng thời giải quyết câu hỏi bảo mật của mọi API/input liên quan scope FE bằng kỹ thuật theo product, gồm active ZAP khi áp dụng. UI/passive không khép nghĩa vụ active. Không tự mở toàn BE ngoài scope FE.
- **BOLA ownership:** đối soát mọi endpoint–role trong scope, owner/non-owner và relation/state/collection liên quan; đủ role discovery. Direct được phép, nguồn findings phải rõ; quyền chức năng tách khỏi ownership.

[Base nghiệp vụ từng track](references/track-intents.md) là điểm xuất phát để suy luận, không phải checklist ép chạy mọi kỹ thuật. [Phạm vi và hoàn tất](references/assessment-scope-and-completion.md) quy định đối soát; còn mục trong scope chưa xử lý thì partial/blocked.

## Bộ điều phối

Theo [điều phối nghiệp vụ](references/operation-dispatch.md): **discovery → câu hỏi kiểm thử → mapping operation/runner → lượt hữu hạn → execution → đọc kết quả → reconcile → khắc phục/tiếp tục**.

1. Xác minh product/source/deployment và scope; đọc [discovery](references/product-discovery.md). Source-only vẫn inventory được; chưa xác minh runtime thì chưa gửi traffic.
2. Giữ inventory đầy đủ độc lập với workload. Đọc [catalog operations](references/native-operation-routing.md), kiểm tool schema/runtime thực và chọn operation theo nhu cầu, không theo tên runner.
3. Đọc [runner đã kiểm](references/runner-routing.md); kiểm entry/call path/gate phù hợp trước tái sử dụng. Product chưa có adapter không tự là ngoài scope.
4. Thực hiện từng lượt, ghi thao tác/kết quả, theo dõi scan/session và state sau mutation khi cần. Scanner chung chạy tuần tự trừ khi đã xác định cách ly.
5. Đối soát endpoint/role/journey với inventory, không chỉ cases runner đã chọn; tự tiếp tục phần đủ điều kiện. Mỗi phần còn mở cần quyết định xử lý có căn cứ theo [khắc phục](references/local-remediation-and-continuation.md); ghi chưa làm không tự là lý do dừng.
6. Dùng [vòng trách nhiệm thực thi](references/responsibility-loop.md) để đối soát inventory product với readback và thực hiện bước tiếp; helper có grounded decision hoặc exit 0 chưa là đã làm. Kiểm [ý nghĩa kết quả từng input](references/assessment-scope-and-completion.md#ý-nghĩa-kết-quả-từng-input) trước khi khép trách nhiệm; có traffic chưa đủ nếu input bị bỏ qua hoặc fixture chặn mục tiêu cần kiểm. Tổng hợp đúng hai file; kết thúc theo [điểm dừng](references/product-assessment-handoff.md#điểm-bàn-giao-và-tiếp-tục). Tự hỏi: **Còn phần việc còn mở nào mà Agent chưa đưa tới một quyết định xử lý có căn cứ ?** Nếu còn, xử lý trước khi kết thúc. Không gọi completed chỉ vì runner kết thúc hoặc có zero alerts.

## Mức ghi nhận và đầu ra

**Chỉ cần trung thực thao tác đã làm và kết quả tương ứng.** Không có mục evidence trong báo cáo và không tạo folder bằng chứng trong bộ bàn giao. Không yêu cầu thêm manifest/hash, source archive, wire attribution, full chunk/hash readback, capability-proof campaign, hai fresh runs hoặc independent approval chỉ để bàn giao một lần assessment. Các bước này chỉ dùng khi user giao audit/qualification cụ thể hoặc công cụ được chọn thực sự bắt buộc; không tự mở chiến dịch chứng minh bổ sung.

Bộ kết quả cuối chỉ gồm **`ALERTS.json` và `RUN.json`** trong một folder ổn định. Đọc [hợp đồng bàn giao](references/product-assessment-handoff.md) và [ghi thao tác/kết quả](references/operations-and-results.md).

- ALERTS: alerts/findings thật, giữ native severity/confidence và nguồn ZAP/direct; cách đếm nhóm khác số instances. Ghi nhận định và giới hạn theo dữ liệu đã có, không đòi chứng minh exploit cho mọi alert.
- RUN: product/môi trường, scope/track, thời gian, từng thao tác (method–route, actor/role, kỹ thuật), kết quả/lỗi, coverage đầy đủ, hạn chế, chưa thực hiện và bước tiếp. Không có phần evidence hoặc yêu cầu references/hash/file bằng chứng cho từng dòng.
- Phân biệt discovery/import, request mẫu, crawl, passive và active; không ghi “đã DAST” từ setup, unit test, tools/list hoặc đọc report cũ. Start/ACK chưa là scan kết thúc. Không bịa kết quả hay đổi verdict để pass; zero alerts không đồng nghĩa an toàn.
- Runner có thể tự sinh log/report/trạng thái nội bộ. Dùng nội dung sẵn có để tổng hợp, không gom/chép thành một gói bằng chứng mới, không công bố credential và không xóa dữ liệu lịch sử để đạt đầu ra gọn. Chế độ báo cáo mới không sửa schema hoặc vô hiệu hóa gate đang có trong code; chọn entry phù hợp và ghi đúng hạn chế nếu còn bị chặn.

Phản hồi cuối ngắn, gồm đúng hai phần theo thứ tự:

1. **Vận hành:** những gì thực sự đã làm, method–route/role/kỹ thuật đã chạy, kết quả và mức hoàn tất; số nhóm alerts theo severity/nguồn, instances ghi riêng. Trả lời rõ **đã hoàn thiện phạm vi nhiệm vụ của từng track được giao hay chưa**, không chỉ lượt chạy đã kết thúc. Kèm link `ALERTS.json` và `RUN.json` tương ứng khi bàn giao assessment.
2. **Hạn chế:** nếu track chưa hoàn tất, nêu từng phần việc không thể thực hiện hoặc hoàn tất được tại điểm dừng hợp lệ, phạm vi bị ảnh hưởng và lý do kỹ thuật cụ thể tương ứng; nêu việc đã thử/đánh giá và điều kiện tiếp tục. Phân biệt chưa kiểm với đã kiểm nhưng bị chặn; chưa xác định nguyên nhân thì nói rõ, không bịa nguyên nhân hoặc dùng limitation thay hành động còn làm được. Không có hạn chế đã biết thì nói rõ trong phạm vi đã kiểm, không suy thành an toàn toàn diện.

Hai phần phải khớp hai file kết quả; không có phần Context hoặc yêu cầu link folder bằng chứng. Tác vụ chỉ sửa skill vẫn dùng Vận hành/Hạn chế để báo thay đổi, validation và giới hạn xác nhận; không giả như vừa scan product hoặc tạo ALERTS/RUN scan giả.

## Routing theo tác vụ

- Backend mới: chọn đường qua [dispatcher](references/operation-dispatch.md), [multi-product](references/multi-product-backend.md) và [chọn origin](references/discovery-origin-selection.md). Đọc [anonymous](references/be-anonymous-research.md), [authenticated](references/be-authenticated-research.md) hoặc [BOLA](references/bola-research.md) khi chọn entry tương ứng.
- Đích authenticated DAST: [workflow theo mục tiêu](references/authenticated-dast-goal.md). Direct BOLA, anonymous hoặc chỉ sửa skill không thay native authenticated DAST.
- Thiếu thông tin auth: [auth discovery](references/auth-capability-discovery.md); capability/contract auth: [BE authenticated](references/be-authenticated.md).
- Chọn kiểm sâu: [product extension](references/product-extension-planning.md); triage phức tạp: [alert triage](references/alert-triage.md). Không tự mở mọi kỹ thuật/lifecycle vì tài liệu có nhắc.
- Lifecycle/ownership sâu, retest, retention/recovery chỉ khi liên quan: [auth/BOLA depth](references/auth-lifecycle-and-bola-depth.md), [retest](references/retest-and-version-comparison.md), [recovery](references/retention-stop-and-recovery.md).
- FE được giao: bắt đầu từ [track intents](references/track-intents.md), chọn runner rồi đọc [anonymous FE](references/fe-anonymous-research.md) hoặc [authenticated FE](references/fe-authenticated-research.md) nếu dùng research entry. Giữ thao tác UI thật và đúng actor; đầu ra vẫn hai file kết quả.
- Audit/verify/nghiệm thu skill: [kiểm định bằng vận hành](references/operational-validation.md), tách smoke đã chạy, giới hạn source và capability chưa kiểm.
- Lập workload BE hoặc sửa adapter/reader/composer: [câu hỏi kỹ thuật và reader đã kiểm](references/operational-readback.md). Nối kết quả riêng của kỹ thuật đã chọn vào reconciliation; dùng helper chung thay vì dựng lại JSONL/paging/redaction cho mỗi lượt.
- Trước tái sử dụng checkpoint/fixture hoặc khi gặp lỗi đã từng xử lý: tra [tri thức vận hành](references/operational-knowledge.md) theo triệu chứng/product, kiểm lại điều kiện áp dụng rồi dùng vào quyết định; cập nhật bài học sau khi đã xác minh.
- Status/setup/restart/stop: [local runtime](references/local-runtime.md). Status-only không start/rebuild/scan target.
- Build/tests/docs/packaging: [repo map](references/repo-map.md). Trước workload nặng hoặc khi thiếu tài nguyên: [resource preflight](references/resource-preflight.md).

## Trạng thái máy và ranh giới

Đọc AGENTS áp dụng, HEAD và dirty state; giữ thay đổi đang có. Source scanner được lưu trực tiếp trong workspace; không còn là Git submodule. Khi cần Docker, xác minh context/daemon, ownership bằng labels, health và đúng Compose file set trước restart. Không đổi context hoặc rebuild để làm status pass. Source build cần JDK25; release Docker không mặc nhiên cần host Java.

Đo tài nguyên trước build/provision/scan nặng theo runner; không hạ ngưỡng, prune, xóa DB/dữ liệu cũ hoặc stop target để vượt lỗi. Khắc phục trong quyền hiện có, không tự mở target/bind/TLS/quyền mới. Không dùng bootstrap `--force`, `down -v` hoặc bỏ auth để chữa health.

Client→MCP auth khác ZAP→target auth. `guided/expert` là tool registration; `direct/queue` là execution mode. Browser crawl không tự hỗ trợ active auth. JSON bearer mặc định tắt trong repo; chỉ cấu hình trên deployment phù hợp trong quyền đã giao. Retention local private đã được cho phép theo skill; phản ánh đúng vào input contract, không hỏi lại, không tự bật experimental trên scanner dùng chung. Native history có thể chứa secret: không đưa credential/token/cookie vào prompt/CLI arguments hoặc hai file chia sẻ.

Giữ scope/quyền và gate thực tế của allocation đang chạy. Contract/adapter có thể sửa hoặc version cho allocation mới trong quyền; giữ pins/raw cũ và reconcile ACK/state trước chọn phần còn thiếu. Không tự thêm yêu cầu assurance của skill, không hạ gate code, không sửa kết quả lịch sử hoặc lấy source policy làm chứng nhận policy đúng. Giải thích rõ phần đã quan sát và phần còn chưa biết. Không tự commit/push/publish, tạo chat, gửi message hoặc spawn subagent ngoài yêu cầu user.

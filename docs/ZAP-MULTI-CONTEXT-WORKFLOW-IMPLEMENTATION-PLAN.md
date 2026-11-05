# Kế hoạch triển khai workflow kiểm thử ZAP qua nhiều context window

Ngày: 2026-10-31, Asia/Ho_Chi_Minh. Agent triển khai dự kiến: **Sol + High**, ở context window tiếp theo.

## 0. Nhiệm vụ cho agent nhận bàn giao

Triển khai thay đổi cho skill `mcp-zap-repo-operations` theo kế hoạch này: điều chỉnh hướng dẫn vận hành, tận dụng cơ chế continuation hiện có, bổ sung hỗ trợ tối thiểu nếu cần và xác minh bằng kiểm tra offline phù hợp.

Tài liệu này tự chứa yêu cầu triển khai; không cần lịch sử chat. Đây là kế hoạch thay đổi skill, **không phải lệnh tiếp tục scan sản phẩm 100ms**. Chính công việc triển khai cũng có thể trải qua nhiều context window: hoàn thành phần việc có ý nghĩa, lưu thay đổi và checkpoint rõ ràng nếu cần bàn giao, không ép hoàn thiện mọi hạng mục trong một window.

Các đường dẫn làm việc:

- Workspace: `/Users/hahoangloc/Working/testing tool`.
- Skill nguồn: `/Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations`.
- Assessment root: `<skill>/lib/zap-product-assessment`.
- Python môi trường hiện có: `/Users/hahoangloc/Working/testing tool/zap-product-assessment/.venv/bin/python`.
- Mã hỗ trợ Python: `<assessment-root>/src/zap_assessment`.

Trước khi sửa, đọc các `AGENTS.md` áp dụng, `git status` và diff của những file sẽ chạm tới. Workspace đang có nhiều thay đổi chưa commit, gồm chính skill ZAP, lớp security scope mới, skill Semgrep và README. Giữ nguyên thay đổi không thuộc nhiệm vụ; không reset/stash/xoá để tạo trạng thái sạch giả.

Trong nhiệm vụ triển khai này:

- Không scan, login, provision, restart scanner, tạo fixture sản phẩm hoặc đọc credential để chứng minh thay đổi tài liệu/checkpoint.
- Không sửa mã nguồn sản phẩm, báo cáo đánh giá lịch sử, lớp source của Semgrep hoặc tự chạy lại các scan đã hoàn tất.
- Không commit/push/publish, tạo chat, cài automation hay spawn subagent nếu chưa có chỉ dẫn riêng cho phép.
- Không tự đồng bộ bản skill cá nhân khi khác bản nguồn.
- Dùng kiểm tra offline và tình huống giả lập để kiểm chứng continuation; ghi đúng giới hạn xác minh runtime.
- Các con số, route và vai trò 100ms trong tài liệu chỉ là dữ kiện hồi cứu. Không hardcode chúng vào skill dùng chung.

## 1. Yêu cầu người dùng đã chốt

Người dùng muốn skill hỗ trợ một nhiệm vụ kiểm thử được hoàn thiện dần qua nhiều phiên làm việc/context window. Chuẩn bị nên gắn với phần việc sắp làm, kết quả/context đã có được kế thừa, và có checkpoint để window sau tiếp tục.

Hệ quả bắt buộc của yêu cầu này:

1. **Kết thúc một phiên làm việc không đồng nghĩa kết thúc assessment.**
2. **Có thể checkpoint khi vẫn còn việc khả thi.** Không cần gắn nhãn `blocked`, giả lập thiếu quyền hoặc chứng minh đã hết mọi phương án chỉ để bàn giao context.
3. **Nghĩa vụ còn mở vẫn còn nguyên.** Checkpoint không giảm scope, không tạo coverage, không đổi unknown thành kết luận, không làm `partial` thành `complete`.
4. **Phiên tiếp theo phải làm tiếp được.** Có sự kiện đáng tin cậy, trạng thái cần xác minh lại, thao tác đang dở, kết quả đã có và hành động kế tiếp cụ thể.
5. **Việc chuẩn bị được tiến hành theo nhu cầu.** Không phải dựng toàn bộ actor/fixture/runner cho mọi track trước khi tạo ra kết quả đầu tiên.

Chuẩn hoá các bất biến và điểm ra quyết định. Để agent lựa chọn thứ tự track, kích thước phần việc và cách tổ chức phù hợp sản phẩm. Không tạo một thứ tự cố định anonymous → authenticated → FE → BOLA cho mọi assignment.

## 2. Vấn đề thực tế cần giải quyết

### 2.1. Tư liệu có thể đọc lại

- Báo cáo lịch sử: `/Users/hahoangloc/Working/testing tool/assessment-results/100ms-20261031-security-scope/{RUN.json,ALERTS.json,SCOPE_ALERTS.json}`.
- Readback: `/Users/hahoangloc/Working/testing tool/.local/100ms-security-20261031/all-active-readback.json`.
- Composer hồi cứu: `/Users/hahoangloc/Working/testing tool/.local/100ms-security-20261031/compose_reports.py`.
- Audit: `/Users/hahoangloc/.cursor/projects/Users-hahoangloc-Working-testing-tool/canvases/100ms-tester-process-review.canvas.tsx`.

Các file `.local` có thể chứa dữ liệu riêng tư. Chỉ cần đọc các file tổng hợp đã chỉ rõ, không mở credential, private responses hoặc token chỉ để triển khai skill. Nếu tư liệu ví dụ vắng mặt, dùng fixture tổng hợp cho các tình huống ở mục 13; không lấy 100ms làm dependency của skill.

### 2.2. Quan sát cần chuyển thành yêu cầu

- Đã có sửa lỗi, actor/fixture thật và native body testing hữu ích; việc kế thừa tốt cần giữ được những kết quả đó.
- Kết quả hồi cứu có 20 native scan, 555 request. Bốn GET có 0 request từ các input rule đã chọn, nhưng vẫn được gắn vào chỉ số method có active work. Metadata continuation phải giữ **ý nghĩa quan sát**, không chỉ tổng request và scan terminal.
- Hầu hết câu hỏi tiêu chí dùng một closure condition chung; composer gán observation units từ required units. Checkpoint phải bảo tồn sự phân biệt giữa điều cần quan sát, điều đã quan sát và điều vẫn chưa đủ căn cứ.
- Bảy API chưa thực hiện DAST bị gán cùng một lý do thiếu callback. Cần phân biệt việc để dành cho phiên sau với dependency kỹ thuật thật.
- Đã có xử lý quota, đọc lại ACK/state và tiếp tục bằng fixture khác. Cần tái sử dụng các cơ chế này thay vì mỗi window dựng lại toàn bộ setup.
- Chín phiên thử cuối cùng đều đã ENDED/LEFT. Window sau không được coi fixture này vẫn còn JOINED hoặc replay lệnh cũ để khôi phục trạng thái giả.

Không diễn giải các quan sát trên thành quy tắc bắt mọi assessment phải dùng cùng số round, fixture, kỹ thuật hoặc report layout.

## 3. Phân biệt các cấp công việc

Đưa các phân biệt sau vào hướng dẫn, không nhất thiết tạo enum hoặc schema mới cho tất cả:

| Khái niệm | Ý nghĩa | Điều không được suy ra |
| --- | --- | --- |
| Assessment/task | Phạm vi người dùng giao, được hoàn thiện dần | Không đồng nhất với một chat, một window hay một lượt runner |
| Phiên làm việc/context | Một khoảng agent xử lý công việc trước khi bàn giao | Hết phiên không làm scope hoàn tất hoặc bị chặn |
| Phần việc cục bộ | Câu hỏi/nhóm câu hỏi hoặc việc chuẩn bị/chẩn đoán có mục đích cụ thể | Không thay inventory đầy đủ bằng phần việc được chọn |
| Round/allocation | Khối thực thi theo giới hạn thực tế của executor | ACK/terminal/exit0 không tự đóng câu hỏi |
| Attempt/auth session | Danh tính lần chạy hoặc phiên xác thực thực tế | Không khai báo hồi sinh session cũ sau login/cleanup |

Trong code/tài liệu dùng tên rõ để tránh nhầm phiên làm việc của agent với ZAP session, application session và authentication session.

Một checkpoint kết thúc phần việc chuẩn bị cũng hợp lệ: ví dụ đã ràng buộc đúng deployment, phát hiện cơ chế identity và xác định được cách chuẩn bị baseline tiếp theo. Không bắt phải có scan/alert mới đủ điều kiện checkpoint.

## 4. Vòng làm việc mục tiêu

### 4.1. Bắt đầu assessment mới

Thiết lập tối thiểu: người dùng giao gì, product/environment nào, nguồn tiêu chí nào, quyền và tác động dự kiến của thao tác sắp thực hiện. Inventory có thể được làm rõ dần; ghi đúng phần chưa xác định.

Sau đó chọn phần việc đầu tiên có ích: một câu hỏi rủi ro cao, một baseline hợp lệ, hoặc một điều kiện chuẩn bị mở được nhiều nhánh. Không đọc mọi reference hoặc chuẩn bị mọi vai trò chỉ vì chúng tồn tại trong skill.

### 4.2. Bắt đầu một phiên tiếp nối

Đọc checkpoint chính thức và phần RUN/scope/operation liên quan. Xác minh lại những gì dễ đổi hoặc ảnh hưởng trực tiếp tới thao tác tiếp theo. Tái dùng những sự kiện còn hiệu lực và kết quả đã có; không khởi động lại toàn bộ discovery chỉ vì context mới.

Nếu checkpoint thiếu hoặc mâu thuẫn: dùng journal/ACK/native status và object state để phục hồi phần liên quan; ghi chỗ chưa biết. Checkpoint thiếu không tự cho phép chạy lại mutation/start hoặc loại bỏ lịch sử.

### 4.3. Chuẩn bị ngay trước phần việc

Một phần việc nên nêu được, theo mức cần thiết:

- Câu hỏi cần giải và vì sao nó đáng làm lúc này.
- Expected đến từ tiêu chí/spec/policy nào; nếu từ source thì gắn nhãn giả định phù hợp.
- Actor, ownership, đối tượng và trạng thái cần có.
- Baseline và input/branch/sink cần đạt; điều kiện nào cho biết thử nghiệm không đi vào mục tiêu.
- Kỹ thuật phù hợp và quan sát đủ để kết luận.
- Tác động dữ liệu/tài nguyên; cách giữ, dừng hoặc cleanup các resource liên quan.

Tận dụng `securityScope.questions`, responsibility inventory, prerequisites và executor plans đang có. Không bắt người dùng tự viết schema, không sinh tích Descartes criterion × route × role × field × rule và không tạo một executor contract mới chỉ để biểu diễn kế hoạch.

### 4.4. Thực hiện và cập nhật

Sau thực thi, đọc kết quả có ý nghĩa trước khi đánh dấu quan sát: identity thực, input thực sự thay đổi, validation/guard/processing đã đạt, side effect hoặc asynchronous state nếu câu hỏi cần.

Kết quả có thể dẫn tới kết luận, cần sửa input/fixture/adapter, cần câu hỏi tiếp hoặc một dependency thật. Một nhánh bị chặn chỉ chặn các công việc phụ thuộc vào nó.

### 4.5. Chọn tiếp hoặc checkpoint

Agent có thể:

- Làm tiếp trong context hiện tại.
- Đổi câu hỏi/track vì rủi ro, lợi ích hoặc dependency.
- Checkpoint và bàn giao một phiên chưa hoàn tất, dù còn việc khả thi.
- Dừng các thao tác bị mất auth/scope/resource theo gate hiện có.
- Kết thúc assessment khi đã đủ scope, người dùng yêu cầu dừng/giới hạn giai đoạn, hoặc có căn cứ thực tế không còn continuation hợp lệ trong quyền và điều kiện được giao.

Trước checkpoint, ghi được tiến triển hoặc thay đổi hiểu biết từ phiên này, việc còn mở và hành động kế tiếp. Không đặt ngưỡng token, số tool call, số scan, thời lượng hay số window mặc định làm luật dừng.

## 5. Điều kiện checkpoint và điều kiện kết thúc assessment

### 5.1. Checkpoint là điểm bàn giao bình thường

Cho phép checkpoint khi một phần việc đã có kết quả/tri thức đáng lưu, trước khi phải mở rộng sâu sang nhánh khác, khi context khó vận dụng chính xác, khi người dùng muốn bàn giao hoặc khi có lý do vận hành tương xứng.

Không yêu cầu agent chứng minh context đã đầy. Không giả định đo được phần trăm chất lượng context. Cũng không biến checkpoint thành việc bắt buộc sau mọi tool call.

**Còn việc khả thi không làm checkpoint mất hiệu lực.** Việc đó phải được giữ là việc khả thi dành cho phiên sau, kèm điều kiện chuẩn bị và bước đầu tiên. Không đổi sang `blocked` để hợp thức hoá kết thúc turn.

### 5.2. Kết thúc assessment vẫn có yêu cầu riêng

- `complete` phải đến từ đối chiếu scope/inventory/questions và kết quả đọc được như hiện tại.
- Checkpoint khi còn open work giữ `taskCompletion: partial` và `handoffClosesTask: false`.
- Dependency thật phải có nguyên nhân, phần bị ảnh hưởng, những hướng đã đánh giá/thử phù hợp và điều kiện tiếp tục; thiếu code trong adapter không tự chứng minh bất khả thi.
- Nếu người dùng yêu cầu dừng hoặc chỉ giao một stage, kết thúc theo đúng yêu cầu, giữ phần chưa đánh giá rõ ràng. Dừng theo yêu cầu không tự trở thành kết luận an toàn.
- Việc đổi context không xác nhận lại permission, không mở rộng target, không cấp quyền runtime mới và không xoá nghĩa vụ cũ.

### 5.3. Unknown và operation đang chạy

Không bắt mọi async operation phải terminal mới được lưu checkpoint. Thay vào đó:

1. Đọc trạng thái trong giới hạn khả thi; lưu ID/ACK/last-known-state và resource ownership.
2. Với outcome chưa rõ, giữ nguyên unknown và đặt reconciliation trước retry/mutation phụ thuộc.
3. Phân biệt **đủ thông tin để bàn giao** với **đủ điều kiện để dispatch tiếp**.
4. Không ghi “đã dừng” nếu mới gửi stop request. Không ghi “đang được monitor” nếu không có cơ chế thực sự tiếp tục quan sát ngoài context.
5. Producer cần giám sát liên tục mà chưa có monitoring thay thế: dùng stop/budget của chính executor cho producer thuộc quyền quản lý khi phù hợp. Nếu chưa xác minh terminal, giữ trạng thái đó và bước readback đầu phiên sau.

Checkpoint khẩn cấp/không đầy đủ vẫn nên lưu những gì biết được và cờ cần phục hồi. Không chặn việc lưu trạng thái chỉ vì chưa thể reconcile xong trong context hiện tại.

## 6. Nội dung phải kế thừa được

| Loại thông tin | Dùng lại | Xác minh lại khi |
| --- | --- | --- |
| Scope, nguồn, quyền, expected và giả định | Giữ nguồn/provenance và disposition cũ | Có thay đổi từ người dùng hoặc xung đột mới |
| Product/source/deployment identity, route/role model, tool schema đã biết | Giữ facts kèm căn cứ và giới hạn hiệu lực | Build/image/runtime/schema có dấu hiệu thay đổi |
| Actor, fixture ownership/status/version/quota, token/session expiry | Giữ private references và trạng thái lần quan sát cuối | Trước thao tác phụ thuộc hoặc khi tiếp nối sau gián đoạn |
| Operations, ACK/native IDs, pending/unknown outcomes | Giữ journal và tham chiếu hiện có | Trước retry/start/mutation và khi checkpoint lệch journal |
| Quan sát và kết luận | Giữ đúng method/role/input/state và provenance | Có observation mâu thuẫn hoặc điều kiện so sánh đổi |
| Việc tiếp theo | Giữ ưu tiên, lý do và bước khởi đầu | Sau readback hoặc khi một dependency thay đổi |

Không ràng buộc checkpoint vào window ID, thread ID hoặc model cụ thể. Không yêu cầu bản sao nguyên transcript. Token, cookie và private key ở storage riêng; handoff dùng private reference theo contract hiện có và không nhét secret vào prompt/report/argv.

## 7. Hình thức lưu tối thiểu được ưu tiên

### 7.1. Một vị trí continuation chính thức

Ưu tiên lưu metadata tiếp nối trong `RUN.json` của thư mục assessment ổn định. `ALERTS.json` và `SCOPE_ALERTS.json` giữ hợp đồng hiện tại. Bàn giao đánh giá vẫn có đúng ba file; không thêm file checkpoint/handoff bắt buộc thứ tư trong thư mục này.

Journal/native outputs/checkpoint executor hiện có ở vùng làm việc riêng tiếp tục là nguồn cho ACK và trạng thái operation. Metadata mới tham chiếu chúng, không tạo một journal cạnh tranh.

Nếu thư mục bàn giao chưa tồn tại ở giai đoạn sớm, có thể lưu ở working RUN hiện có và chỉ rõ đó là vị trí tiếp nối tạm thời. Khi xuất bộ ba, cập nhật location chính thức. Không bắt đọc đủ toàn bộ catalog, dựng đủ inventory hay tạo kết quả scan giả chỉ để được checkpoint.

### 7.2. Metadata additive, không tái thiết kế completion

Hướng triển khai ưu tiên là một trường `continuation` trong RUN. Tên field cụ thể có thể điều chỉnh sau khi kiểm tra call sites; giữ các nhóm ngữ nghĩa dưới đây. Đây là biểu diễn agent chuẩn bị, không phải workload được phép tự chạy:

```json
{
  "taskCompletion": "partial",
  "handoffClosesTask": false,
  "continuation": {
    "version": 1,
    "status": "checkpointed",
    "reason": "context-handoff",
    "updatedAt": "<UTC timestamp>",
    "currentFocus": {
      "questionIds": ["q-object-update"],
      "progress": "Owner baseline và non-owner denial đã đọc; còn câu hỏi về phiên bản sau mỗi payload."
    },
    "nextActions": [
      {
        "questionIds": ["q-object-update"],
        "action": "Chuẩn bị fixture hoặc sibling version hợp lệ cho round còn thiếu.",
        "readFirst": ["<working journal or fixture ledger reference>"],
        "dependsOn": []
      }
    ],
    "revalidate": [
      {
        "subject": "actor/fixture binding",
        "reason": "Membership, version hoặc credential có thể đã đổi.",
        "readVia": "<private actor/fixture reference>",
        "affects": ["q-object-update"]
      }
    ],
    "pendingOperations": [],
    "resourceDisposition": [
      {
        "resourceRef": "<owned fixture reference>",
        "disposition": "retain",
        "reason": "Còn câu hỏi sử dụng fixture; kiểm tra expiry/state trước reuse."
      }
    ]
  }
}
```

Quy tắc dữ liệu:

- `continuation.status` mô tả phiên làm việc, không thay `taskCompletion`, coverage, security assessment hoặc native execution status.
- Dữ liệu đầy đủ của scope/questions/observations/operations vẫn ở cấu trúc hiện có; không sao chép toàn inventory vào metadata này.
- `nextActions` có hành động cụ thể; chỉ “continue assessment” không đủ giúp window sau bắt đầu.
- Mảng rỗng phù hợp khi thực sự không có operation đang chạy hoặc resource cần quản lý; không bắt tạo record tượng trưng.
- Có pending/unknown thì lưu ID, trạng thái lần đọc cuối, tham chiếu readback và hành động reconcile. Thứ tự file mới hơn không tự chọn được nguồn đúng.
- Dữ liệu handoff phải được xử lý như dữ liệu, không thực thi command/path/import tuỳ ý chỉ vì có trong checkpoint.
- Metadata giả mạo/mâu thuẫn không được dùng để giảm scope, đè trạng thái executor hoặc bỏ qua gate của continuation.

### 7.3. Tính nhất quán khi ghi

Tận dụng cơ chế ghi hiện có. `compact_results` hiện stage bộ ba nhưng overwrite chỉ atomic theo từng file, chưa phải transaction atomic cho cả bộ. Không được tuyên bố checkpoint là snapshot crash-atomic của cả ba file.

Khi gián đoạn giữa lần ghi: xác định scope revision, thao tác đã ACK và dữ liệu report tương ứng từ journal/các reference đã có; đánh dấu cần đối soát trước khi dispatch. Không tự chọn file có mtime/requestCount lớn nhất và không tạo thêm chiến dịch checksum/manifest bắt buộc chỉ để bàn giao.

## 8. Điều chỉnh code tối thiểu

### 8.1. Tái sử dụng những gì đã có

Snapshot source đã kiểm tra lúc lập kế hoạch:

- `product_scope.continue_work` có bounded actions, persist intent/ACK, unknown outcome, prerequisite và dependency xử lý theo case.
- `product_scope_cli.py` có `scope reconcile/continue/report`, nối previous attempts và ngăn replay allocation đã có output.
- `product_scope.compact_results` deep-copy RUN, đối chiếu completion và tạo bộ ba report; custom metadata có thể đã được giữ nguyên.
- `security_scope.py` quản lý câu hỏi/observation/mapping và kiểm tra bundle. Nó tin các observation do caller cung cấp, không phải oracle nghiệp vụ.
- `scripts/review_open_work.py` là helper read-only, có `work` và `checkpoint`. `canHandOffPartial` hiện đòi dependency thật và không còn action khả thi. Trường đó đang diễn tả điều kiện của kiểu bàn giao kết thúc công việc cũ, không phù hợp để làm gate cho mọi context checkpoint.

Xác minh lại snapshot trước khi sửa. Đừng chạy kế hoạch `ZAP-USER-SECURITY-SCOPE-IMPLEMENTATION-PLAN.md` cũ để tạo lại security-scope layer; nó có nhận định source trước khi bộ ba report được triển khai.

### 8.2. Hướng thay đổi được chọn

1. Giữ completion/reconciliation hiện có. Thêm preservation/validation metadata ở đúng lớp báo cáo nếu source hiện tại chưa đủ.
2. Không thêm một executor tự động mới. Tiếp tục dùng CLI/handlers đã được admission kiểm tra.
3. Phân biệt trong helper giữa “có thể kết thúc assignment/partial handoff vì dependency” và “có thể bàn giao context với việc khả thi còn lại”. Giữ nghĩa cũ của `canHandOffPartial` để không âm thầm nới gate cho caller cũ.
4. Bổ sung một kết quả/helper read-only riêng về checkpoint phiên nếu cần cho việc kiểm tra dữ liệu: chỉ ra thông tin thiếu, bước resume, pending reconciliation và công việc còn thực hiện được. Có thể mở rộng helper hiện có thay vì tạo module mới.
5. Helper không được dispatch, đọc credential, gọi runtime, cấp permission hoặc sửa `taskCompletion`. `checkpointReady` nếu dùng chỉ có nghĩa dữ liệu bàn giao đủ dùng, không cấp quyền thực thi tiếp.
6. Không đổi nghĩa `stop`/`continuationStoppedByUser` trong `continue_work` thành checkpoint ngầm. Checkpoint ở ranh giới round/action đã persist; không biến nó thành user cancellation hoặc fabricated terminal status.
7. Không thêm flag `--checkpoint`/command mới vào mọi runner nếu metadata/report + hướng dẫn đã giải quyết được yêu cầu. Chỉ thêm CLI khi có call path cần thiết và test đúng hành vi đó.

Chỉ sửa code có nhu cầu chứng minh được. Nếu custom metadata đã đi qua composer an toàn, giữ nguyên cơ chế đó và tập trung vào hướng dẫn, validation/helper cần thiết và regression tests. Tránh framework queue/scheduler, state machine tổng quát hoặc phiên bản lại toàn bộ executor schema.

## 9. Bản đồ file cần sửa/đối chiếu

Tất cả path dưới đây tương đối với skill nguồn.

| File | Thay đổi cần đạt |
| --- | --- |
| `SKILL.md` | Nêu multi-context là workflow bình thường; chuẩn bị theo phần việc; checkpoint được khi còn việc khả thi; task completion tách session boundary |
| `agents/openai.yaml` | Default prompt phản ánh local preparation, kế thừa và checkpoint/resume; không hứa hoàn tất trong một invocation |
| `references/tester-context.md` | Bổ sung cách dùng facts/assumptions/state và câu hỏi để chọn phần việc |
| `references/operation-dispatch.md` | Bổ sung resume path; phân biệt đổi nhánh, checkpoint và kết thúc task |
| `references/responsibility-loop.md` | Nghĩa vụ được tiếp tục xuyên các phiên; eligible work có thể nằm trong nextActions tại checkpoint |
| `references/product-assessment-handoff.md` | Thay điều kiện “no eligible work” cho bàn giao context bằng hợp đồng checkpoint; giữ điều kiện đóng assessment riêng |
| `references/assessment-scope-and-completion.md` | Complete vẫn giữ chặt; partial có thể là checkpoint với runnable work, không bắt báo blocked |
| `references/local-remediation-and-continuation.md` | Việc thiếu adapter/fixture là công việc chuẩn bị/sửa có thể bàn giao; dependency thật có nghĩa khác |
| `references/retention-stop-and-recovery.md` | Entry point chính cho checkpoint, pending operation, resource ownership và revalidation |
| `references/operational-knowledge.md` | Giải thích giới hạn helper và các ý nghĩa handoff riêng; không biến lessons thành state của lần chạy |
| `references/user-security-scope.md` | Giữ scope/questions qua checkpoint; source/config/log questions không bị ép thành track/endpoint |
| Track references, `authenticated-dast-goal.md`, `product-extension-planning.md` | Sửa các câu mâu thuẫn về persistence/stop nếu có; giữ riêng yêu cầu kỹ thuật của từng track |
| `product_scope.py`, `product_scope_cli.py`, `security_scope.py` | Chỉ thay phần thật sự cần cho metadata/validation/compatibility; không nới verdict/admission |
| `scripts/review_open_work.py` | Phân biệt checkpoint work session với kiểu partial handoff cũ; read-only, không cấp quyền hoặc gán completion |

Ưu tiên đặt chi tiết ở `retention-stop-and-recovery.md`, rồi dẫn đúng chỗ từ SKILL và dispatcher. Chỉ tạo thêm một reference riêng nếu nội dung thực sự làm tài liệu hiện có khó đọc; tránh chép cùng quy trình vào nhiều file.

Tìm toàn skill những câu như `End when`, `Stop only`, `before ending`, `before handoff`, `continue eligible`, `no eligible work remains`. Sửa theo ngữ nghĩa, không thay thế hàng loạt khiến mất yêu cầu không bỏ scope hoặc chống replay.

Một câu cốt lõi có thể dùng trong SKILL, điều chỉnh cho gọn khi triển khai:

> An assessment may span multiple working sessions and context windows. Prepare and execute useful local work units, preserve results and live-state dependencies, and checkpoint for continuation even when eligible work remains. A checkpoint ends the current work session; it does not complete, reduce, or block the assignment. Keep open responsibilities and concrete next actions available to the next session.

## 10. Resume ở window mới

Hướng dẫn window sau thực hiện theo phụ thuộc thực tế:

1. Tìm official RUN/continuation location và scope được giao. Đọc checkpoint cùng phần operations/questions/observations liên quan, thay vì toàn raw history.
2. Nhận diện kết quả nào còn hiệu lực, giả định nào chưa xác minh và thông tin nào đã hết hiệu lực.
3. Với operation pending/unknown, đọc journal/ACK/status hoặc object state trước mọi thao tác có thể lặp side effect.
4. Revalidate target/runtime/schema/actor/fixture/resource chỉ ở mức cần cho hành động sắp chạy. Có drift thì giới hạn tác động vào phần phụ thuộc, không xoá kết quả cũ hoặc repin history.
5. Chọn câu hỏi/việc chuẩn bị tiếp theo. Nếu một nextAction trước đây không còn phù hợp, cập nhật lý do và giữ nghĩa vụ gốc.
6. Thực hiện, đọc kết quả, cập nhật lại trạng thái; checkpoint tiếp khi phù hợp.

Không tái login hoặc reset session chỉ vì đổi window. Khi session đã hết hạn và cần login/provision lại qua flow hợp lệ, đó là attempt/session mới; giữ provenance và không tuyên bố tiếp tục nguyên session cũ.

Prompt tiếp nối chỉ là điểm vào đọc trạng thái. Mẫu gọn:

```text
Tiếp tục assessment tại <official directory hoặc working RUN>, dùng $mcp-zap-repo-operations.
Đọc RUN.json/continuation và các ALERTS.json, SCOPE_ALERTS.json hiện có; đối chiếu journal cho operation pending/unknown trước retry.
Giữ product/environment/scope/quyền đã được xác minh. Credential chỉ đọc từ private reference khi thật sự cần; không đưa vào chat/report.
Dùng lại facts và kết quả còn hiệu lực; revalidate actor/fixture/runtime dễ đổi cho phần việc tiếp theo.
Bắt đầu từ <question/nextAction cụ thể>; nếu điều kiện đã đổi thì cập nhật kế hoạch và tiếp tục phần hợp lệ.
Không coi checkpoint là completion, không rescan toàn bộ chỉ vì window mới. Có thể checkpoint tiếp với nextActions và trạng thái đủ để tiếp nối.
```

Không tự tạo chat mới, gửi message sang chat khác, bật automation hoặc khai báo đã reset context. Những hành động đó cần yêu cầu riêng và công cụ phù hợp. Skill chỉ đảm bảo trạng thái và hướng dẫn tiếp nối có thể dùng được.

## 11. Resource và bảo mật qua checkpoint

- Tách retain fixture, stop producer và cleanup scanner. Không kết thúc fixture dùng một lần chỉ để làm checkpoint “sạch”.
- Cũng không giữ producer chạy vô hạn khi context không còn quan sát nó. Dùng ownership, executor budgets và khả năng giám sát thực tế để chọn disposition.
- Resource có expiry/quota/version phải được ghi điều kiện tái dùng; giữ credential riêng tư theo quy định hiện có.
- Không thay bind/network/TLS/auth, giảm reserve, prune, xoá DB hoặc tắt gate để làm resume thành công.
- Không xác nhận checkpoint “không có operation đang chạy” từ passive backlog0; xem producer/job/scan state liên quan.
- Không nhét nguyên native report/log có secret vào checkpoint hoặc prompt. Tóm tắt phần cần quyết định, giữ raw ở private reference.
- Không checkpoint dựa trên những tiêu chí quan sát được sao chép từ required units. Checkpoint có thể ghi câu hỏi chưa giải và vì sao còn mở.

## 12. Các phần việc triển khai đề xuất

Đây là thứ tự phụ thuộc của việc sửa skill, không phải lịch bắt buộc mỗi window phải hoàn thành một phase.

### A. Đọc source hiện tại và chốt semantics

- Xác minh các call paths ở mục 8; tìm caller dùng `canHandOffPartial` và các trường completion.
- Xác định nơi metadata continuation đã được preserve, sanitise hoặc bị loại.
- Chốt vị trí official continuation và sự phân biệt session checkpoint/task completion.
- Checkpoint A có thể chỉ gồm quyết định thiết kế, file sẽ sửa và bước tiếp; chưa cần đụng runtime.

### B. Sửa hướng dẫn nhất quán

- Sửa entrypoint/default prompt, resume/dispatcher và các quy tắc stop mâu thuẫn.
- Đặt workflow local preparation, checkpoint và selective revalidation ở một reference chính.
- Giữ các bảo vệ source/identity/mutation/resource và scope reconciliation.
- Đọc lại một lượt theo lộ trình của người dùng mới và một lượt theo người tiếp nối chỉ có checkpoint.

### C. Bổ sung hỗ trợ tối thiểu ở code/helper

- Preserve/validate metadata theo nhu cầu thực tế và giữ ngược tương thích.
- Thêm phân biệt session checkpoint với partial task handoff ở helper nếu cần.
- Dữ liệu không đủ thì trả thông tin cần phục hồi/thiếu; không auto-dispatch hoặc làm mất dữ liệu checkpoint best-effort.
- Không sửa các strict executor gates/pins chỉ để thông qua bài kiểm tra continuation.

### D. Kiểm tra hành vi qua nhiều phiên giả lập

- Dùng tối thiểu hai context giả lập bằng các lần đọc/ghi state riêng, không truyền biến bộ nhớ giữa chúng.
- Mỗi lần chỉ dùng artifact được checkpoint cộng fake current-state cần thiết.
- Xác minh scope/results được kế thừa, pending outcomes không replay và stale fixture không được tái dùng như còn sống.
- Sau kiểm tra, giữ output test trong vùng tạm, không trộn với report 100ms lịch sử.

### E. Bàn giao thay đổi

- Nêu file đã đổi, hành vi trước/sau, validation thực tế và giới hạn runtime.
- Nếu tiếp tục ở window khác, lưu trạng thái triển khai ở ghi chú làm việc phù hợp và bước tiếp theo; không tự đánh dấu implementation complete.
- Kết thúc triển khai khi yêu cầu và acceptance ở mục 14 đã đạt, không dựa vào việc đã viết một reference mới.

## 13. Kiểm tra cần thiết

Ưu tiên kiểm tra hành vi và dữ liệu; không thêm test chỉ tìm đúng câu văn hoặc heading của skill.

### 13.1. Tình huống bắt buộc

| Tình huống | Kết quả mong đợi |
| --- | --- |
| Window1 mới chuẩn bị xong baseline/câu hỏi, vẫn còn eligible work | Cho checkpoint; giữ partial, nextAction có thể thực hiện; không bắt đổi sang blocked hoặc chạy thêm scan |
| Window2 đọc checkpoint trên | Dùng lại dữ liệu ổn định, chỉ revalidate phần dễ đổi; không discovery/reset mọi thứ |
| Một câu hỏi đã có đủ observation, câu khác còn mở | Checkpoint/resume giữ kết quả câu đầu và nghĩa vụ câu sau; không hợp nhất thành complete |
| Intent đã persist nhưng mất ACK của mutation/start | Checkpoint giữ unknown; bước đầu resume là reconcile, không replay command |
| Scan đang chạy hoặc stop mới ACK | Giữ operation ID/last-known-state/ownership và bước readback; không gán terminal |
| Token hết hạn, fixture đã ENDED hoặc quota đã hết | Không reuse theo snapshot cũ; chuẩn bị đúng phần phụ thuộc, giữ observation cũ có nhãn |
| Runtime/image/origin/scope revision khác | Yêu cầu đối soát binding/phần bị ảnh hưởng; không merge history hoặc dispatch theo target cũ |
| Report ghi gián đoạn giữa bộ ba | Phát hiện/giữ nhu cầu đối soát; không lấy file mới nhất làm chân lý hoặc tăng completion |
| Metadata thiếu trường giúp tiếp nối | Lưu best-effort và nêu phần cần phục hồi; thiếu metadata không cho phép replay |
| Input có secret thô/encoded trong continuation | Sanitisation hoặc rejection theo quy ước hiện có; secret không đi vào bộ ba/prompt/diagnostics |
| Old RUN không có continuation | Đọc được như trước; tạo checkpoint mới chỉ khi có dữ liệu, không tự chạy network |
| Context handoff với runnable nextActions | Có thể checkpoint phiên; `canHandOffPartial` cũ không bị đổi nghĩa để cấp completion |
| Context đổi nhưng mọi kết quả chưa có scope đủ | `taskCompletion` vẫn partial và `handoffClosesTask` vẫn false |
| Active scan chỉ có auxiliary/site-wide requests | Checkpoint giữ ý nghĩa đó; không biến thành input coverage cho method/field mục tiêu |

Các trường hợp active rule/fixture có thể dùng dữ liệu tổng hợp mô phỏng khác 100ms. Không cần replay thực tế 20 scan hoặc một qualification campaign để test logic report/checkpoint.

### 13.2. Bộ kiểm tra hiện có cần xem

- `<assessment-root>/tests/test_pm_scope.py`.
- `<assessment-root>/tests/test_security_scope.py`.
- `<assessment-root>/tests/test_product_continuation.py`.
- `<assessment-root>/tests/test_operational_readback.py`.
- `<assessment-root>/tests/test_portability.py`.
- Các test/helper call sites thực sự bị thay đổi; không chạy lại mọi suite chỉ để tăng số kiểm tra.

Lệnh tham khảo, kiểm tra lại đường dẫn và dependency trước khi chạy:

```sh
cd '/Users/hahoangloc/Working/testing tool'
export ZAP_ASSESSMENT_SRC="$PWD/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src"
export ZAP_ASSESSMENT_TESTS="$PWD/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/tests"
export ZAP_ASSESSMENT_PYTHON="$PWD/zap-product-assessment/.venv/bin/python"
PYTHONPATH="$ZAP_ASSESSMENT_SRC:$ZAP_ASSESSMENT_TESTS" "$ZAP_ASSESSMENT_PYTHON" -B -m unittest test_pm_scope test_security_scope test_product_continuation test_operational_readback test_portability -q
```

Thêm test module mới vào lệnh nếu đã tạo. Cần xác minh các test được chọn là offline trước khi chạy. Thiếu dependency thì ghi rõ và dùng phần kiểm tra có thể thực hiện; không tự fetch package hoặc provision scanner cho nhiệm vụ này.

Kiểm tra Markdown links, YAML metadata khi sửa, skill validator hiện có nếu áp dụng và `git diff --check` cho phần thay đổi. Tách lỗi đã có từ trước với lỗi mới, không sửa ngoài phạm vi để làm sạch toàn repo.

## 14. Tiêu chí nghiệm thu

Chỉ coi phần triển khai này hoàn thành khi:

- [ ] Entry point và các reference không còn buộc hoàn thiện assessment trong một invocation/window.
- [ ] Có chỉ dẫn rõ checkpoint khi còn eligible work; không cần giả lập blocker và không xin phép lại chỉ để kết thúc một phần việc cục bộ.
- [ ] Điều kiện complete/coverage/security verdict không bị nới bởi checkpoint.
- [ ] Official state và trình tự resume rõ; không có nhiều ledger cạnh tranh.
- [ ] Giữ đúng bộ ba report khi bàn giao assessment; không tạo checkpoint artifact bắt buộc thứ tư trong thư mục đó.
- [ ] Kế thừa facts/results và selective revalidation được mô tả đủ để window sau không lặp discovery/scan mặc định.
- [ ] Pending/unknown operations, ACK/stop semantics và replay guard còn nguyên, có kiểm tra hành vi phù hợp.
- [ ] Retain/cleanup/stop thuộc đúng ownership; không yêu cầu mọi operation terminal mới lưu được state.
- [ ] Secret không đi vào metadata công khai hoặc prompt; old inputs/outputs vẫn tương thích.
- [ ] Các tình huống nhiều phiên ở mục 13 đã được kiểm tra offline với kết quả thật; không coi metadata labels là oracle.
- [ ] Hướng dẫn đủ gọn và progressive disclosure; không thêm thứ tự track, số window hoặc context threshold cố định.
- [ ] Giữ nguyên thay đổi có sẵn của người dùng, báo cáo lịch sử và executor gates; mô tả đúng giới hạn chưa xác minh runtime.

## 15. Prompt gửi Sol + High ở context tiếp theo

```text
Hãy triển khai kế hoạch tại:
/Users/hahoangloc/Working/testing tool/docs/ZAP-MULTI-CONTEXT-WORKFLOW-IMPLEMENTATION-PLAN.md

Workspace: /Users/hahoangloc/Working/testing tool
Skill nguồn: .agents/skills/mcp-zap-repo-operations

Mục tiêu là sửa skill để một assessment được làm dần qua nhiều context window: chuẩn bị theo phần việc, giữ kết quả/trạng thái có thể kế thừa, checkpoint hợp lệ khi vẫn còn việc khả thi và resume có chọn lọc. Kết thúc context không làm task complete/blocked và không giảm scope.

Đọc kế hoạch, AGENTS áp dụng, git status/diff và source hiện tại trước khi sửa. Tận dụng continuation/journal/report đang có; sửa tối thiểu, giữ bộ ba RUN.json/ALERTS.json/SCOPE_ALERTS.json, admission/replay/resource/auth gates và tương thích cũ. Không chạy lại scan100ms, không đọc credential hoặc provision runtime cho nhiệm vụ triển khai này.

Thực hiện code/tài liệu và kiểm tra offline thích hợp. Có thể tiếp tục chính việc triển khai qua nhiều window nếu cần: checkpoint tiến triển, file đã thay đổi, kết quả test và bước kế tiếp cụ thể; không dừng ở một bản kế hoạch mới và không phải ép hoàn tất trong window hiện tại. Không reset/stash/ghi đè thay đổi ngoài phạm vi; không commit/push, tự tạo chat, automation hoặc subagent khi chưa được yêu cầu.
```


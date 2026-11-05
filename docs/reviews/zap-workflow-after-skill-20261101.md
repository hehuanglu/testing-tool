# Đánh giá quy trình vận hành ZAP sau sửa skill

Ngày đánh giá: 01/11/2026, giờ Việt Nam. Đây là review lịch sử thao tác và báo cáo lưu sẵn; không chạy lại assessment và không sửa skill.

## Kết luận

**Chất lượng thực thi và tính trung thực khá tốt; mục tiêu giảm phân mảnh phiên mới đạt một phần.** Agent thực sự thực hiện nhiều vòng trong một lượt, sửa lỗi rồi tiếp tục, phân biệt native alert với quan sát, và giữ các objective thiếu fixture ở trạng thái partial. Tuy nhiên, việc mở chat mới vẫn trở thành nhịp kết thúc gần như mặc định. Inventory chưa cho thấy đường đi rõ ràng đến hoàn tất.

Không kết luận hiệu suất tăng bao nhiêu so với trước sửa: review này chủ ý chỉ dùng giai đoạn sau sửa, không có nhóm đối chứng trước sửa hoặc số đo token/context.

## Phạm vi và cách đọc

Mốc bắt đầu: **12:48:46 ngày 01/11/2026**, khi chat **“Cải thiện execution loop của ZAP skill”** hoàn tất. Mốc cuối dữ liệu kết quả: **18:54:32 ngày 01/11/2026**, theo RUN chính thức.

Đã đọc lịch sử 12 chat vận hành, gồm 17 lượt được API trả về: 16 lượt có thời điểm hoàn tất và 1 lượt không có kết thúc. Trong 16 lượt hoàn tất có 13 lượt thực thi assessment, 2 lượt dừng ở gate dung lượng và 1 lượt dọn dung lượng. Không dùng chat chỉnh skill làm mẫu vận hành; không dùng chat cũ có updatedAt mới để suy ra đã chạy sau sửa.

13 lượt thực thi có thời gian 10,0–28,6 phút, trung vị 16,3 phút, tổng thời gian lượt khoảng 216,2 phút. Đây là wall time của lượt, có cả chờ và công việc hỗ trợ, **không phải thời gian scan thuần hoặc token tiêu thụ**. Cả 13 kết thúc đều khuyến nghị chat/window mới. Không coi độ dài lượt là bằng chứng tự thân cho việc tận dụng context tốt hoặc dừng quá sớm.

Nguồn: lịch sử message/command của các chat bên dưới; SKILL và references hiện hành; RUN/ALERTS/SCOPE_ALERTS và scans.json hiện có. Một số output lịch sử bị cắt theo giới hạn công cụ; không replay từng request.

## Những điểm làm tốt

### 1. Có nhiều vòng và xử lý lỗi trong cùng phiên

Chat **“Tiếp tục kiểm tra ZAP”** bắt đầu 14:41 thực hiện 7 scan, UI STAGE/LEAVE/END và recording capture; khi capture đầu thất bại, agent thử có mục đích với telemetry và đạt RECORDING. Không dừng ngay sau một vòng.

Chat **“Tiếp tục kiểm tra ZAP”** bắt đầu 15:41 gặp ACCEPT dừng do disk gate, giữ XSS đã chạy rồi chỉ tiếp tục SQLi còn thiếu trên lifecycle mới. Chat **“Continue content-share testing”** xử lý deadlock fixture/media, tách hỗ trợ media trực tiếp và tiếp tục phần thiếu. Đây là hành vi phù hợp với execution loop sau sửa.

### 2. Không dùng trạng thái scanner thay cho ý nghĩa kết quả

- STAGE STOP: plugin Complete nhưng hai valid control trả 503; objective vẫn partial.
- Recording: outbound bytes/frames không được tự động tính là recorder đã ready; FAILED và thiếu segment được giữ.
- Content path: SQLi Skipped/time cap, quota nguồn và receipt 200 cũ không được nâng thành mutation mới.
- Media qua TLS trực tiếp được ghi là hỗ trợ, không tính coverage ZAP/FE.

Đây là điểm mạnh đáng giữ. Không cần biến mọi request thành thành công để có kết quả kiểm thử có giá trị; nhưng input bị chặn trước objective thì phải còn nghĩa vụ mở.

### 3. Đã phân biệt provenance và sửa cách diễn giải

Native groups, instances và ZAP-derived observations được báo riêng. Quan sát DELETE WHEP ban đầu là suspected-violation, sau đó được chuyển inconclusive khi xét URL-secret capability và chưa chứng minh unauthorized acquisition. Dữ liệu DELETE/404 gốc vẫn còn trong observation; đây là sửa diễn giải, không phải retest xóa kết quả.

Các check gate dung lượng giữ scanner dừng, không tự hạ gate. Đợt dọn cache sau đó có chỉ thị người dùng riêng trong chat; không quy kết là tự ý prune chỉ để vượt gate.

### 4. Handoff dùng được

RUN chính thức ổn định; có helper/snapshot cụ thể, điều kiện token/JOINED/version, pending/unknown và prompt tiếp tục. Hai lượt disk gate còn nói rõ có thể tiếp tục ngay trong chat hiện tại. Điều này tốt hơn việc chỉ thông báo “đã checkpoint”.

## Vấn đề ưu tiên

### P1 — Chưa chứng minh được lý do chuyển context trong nhiều lần bàn giao

**Quan sát:** 13/13 lượt thực thi đề nghị mở chat mới. Ví dụ:
- “Resume 100ms recording assessment”: lượt khoảng 11 phút, lý do là bước tiếp cần fixture LIVE/STAGE/source khác.
- “Resume ZAP content lifecycle checks”: khoảng 10,3 phút, lý do là cần adapter vector khác và fixture mới.
- “Tiếp tục kiểm thử ZAP live-proof”: khoảng 11,9 phút, lý do chuyển loại fixture/tránh nhầm LEFT/ENDED.

**Đánh giá:** Đổi fixture/vector và có nhiều trạng thái là công việc bình thường của tester; bản thân chúng chưa nói rõ vì sao context đang dùng không còn phù hợp. Skill cho phép checkpoint theo phán đoán, không đòi token quota hoặc chứng minh cạn context. Vì vậy đây là **lý do chưa đủ thuyết phục**, không phải bằng chứng chắc chắn agent còn dư context hay mọi checkpoint đều sai.

**Tác động:** Người dùng vẫn làm cầu nối tiếp tục; scanner phải được lưu/dừng/load nhiều lần. Chat “Tiếp tục đánh giá quyền WHEP” còn cho thấy sau khuyến nghị chat mới, người dùng gửi “tieps tục” ngay tại chat đó và agent vẫn hoàn thành thêm khối UI/lifecycle. Đây là phản ví dụ thực tế cho việc coi khuyến nghị đổi chat trước đó là điều kiện bắt buộc.

**Nên sửa cách vận hành:** Sau reconcile, chọn ngay câu hỏi khả thi tiếp theo và tiếp tục. Nếu thực sự cần checkpoint, nêu trở ngại cụ thể của block kế tiếp hoặc giới hạn giám sát/context hiện tại; không chỉ nói “fixture mới”. Không thêm quota lượt/request/token.

### P1 — Inventory bảo thủ nhưng chưa đủ cụ thể để dẫn đến hoàn tất

**Quan sát:** RUN mới nhất có 29 route, **29/29 coverage partial**. 24 route dùng nguyên câu generic:
“Reconcile method/role-specific inputs and relevant state/object transitions; recorded native/direct/UI subsets do not imply whole-route completion.”
Câu này xuất hiện cả GET /api/health và route internal đang bị ingress chặn.

**Đánh giá:** Không có cơ sở để ép các route này complete. Vấn đề là danh sách việc còn lại chưa diễn đạt câu hỏi cụ thể, applicability và điều kiện kết thúc cho từng route. Câu generic giữ thận trọng nhưng cũng có thể duy trì nghĩa vụ mở vô hạn.

**Nên làm trước khi thêm nhiều scan:** Đối soát trong inventory hiện có: route/role/input nào đã trả lời được câu hỏi; phần nào N/A có lý do; phần nào thực sự thiếu; điều kiện nào sẽ đóng phần đó. Không đòi phủ mọi tổ hợp vô hạn hoặc rescan payload đã giao. Ưu tiên câu hỏi ảnh hưởng kết luận security, thay vì chọn header/path tiếp theo chỉ vì có thể chạy.

### P2 — Lỗi orchestration/fixture vẫn lặp qua nhiều phiên

**Quan sát:** Content START có khóa vòng adapter/fixture; content-recording sau đó tiếp tục gặp callback phụ thuộc ZAP; recording/path gặp 503 và thiếu prerequisite credit. Nhiều partial được giữ đúng nhưng recorder zero-segment/FAILED vẫn chưa có nguyên nhân xác định.

**Đánh giá:** Xử lý sự cố trong phiên là tốt; tránh lặp lại sự cố cùng họ giữa các phiên còn yếu. Không đủ dữ liệu để quy mọi 503 cho rate limit. Không nên tuyên bố các scan này vô ích: chúng vẫn có kết quả boundary/path, nhưng không đóng objective bị fixture chặn.

**Nên làm:** Trước allocation phụ thuộc recording, dùng readback đã lưu để chẩn đoán readiness và dependency; tái sử dụng phần điều phối đã sửa phù hợp. Khi nhánh đó chưa khả thi, chuyển câu hỏi độc lập. Chỉ thêm execution mới để giải quyết câu hỏi còn thiếu thật.

### P2 — Chi phí lưu/khôi phục và helper tăng

**Quan sát:** Thư mục phiên hiện có 13 file resume*.py và 133 file Python. Snapshot tăng đến 43 allocation; một snapshot lịch sử có data khoảng 1,31 GB trước nén, 252 MB sau nén. Đã có hai lượt bị chặn dung lượng và một allocation đang chạy phải dừng vì disk reserve.

**Đánh giá:** Số file không tự chứng minh lãng phí; helper theo epoch còn bảo vệ chống replay. Tuy nhiên, stop/save/load liên tục cùng helper nối tiếp tạo thêm bề mặt nhầm snapshot mà các prompt phải nhắc “không gọi helper cũ”.

**Nên làm:** Giữ một entry resume có kiểm tra lineage/current snapshot nếu thực sự cần sửa helper; bảo toàn snapshot/raw và các gate. Trong cùng phiên, không coi export hoặc hết một vector là lý do dừng scanner. Không xóa lịch sử hay prune để làm report đẹp.

## Trạng thái thực tế tại mốc đọc

- 43 allocation: 31 completed, 10 partial-terminal, 1 stopped-incomplete, 1 incomplete theo scans.json. Đây là trạng thái execution, không phải 31 objective đã hoàn tất.
- Native ZAP: **8 nhóm**, gồm 1 Medium, 4 Low, 3 Informational; **1.062 instances**.
- ZAP-derived observations: **76**, gồm 68 matched, 8 inconclusive.
- 50 tiêu chí: 19 partial, 25 not-operated, 6 applicability-reviewed. Không biến các con số này thành tỷ lệ pass.
- BE anonymous, BE authenticated, BOLA và FE đều partial.
- Tăng instances không đồng nghĩa tìm thêm nhóm lỗi hoặc tăng coverage. Nhiều chat ghi rõ tăng passive instances của nhóm cũ, không có active alert mới.

## Ưu tiên cải thiện

1. Làm rõ nghĩa vụ còn thiếu và điều kiện đóng từng route ngay trong inventory/RUN hiện có.
2. Gom công việc theo actor/fixture/runtime có thể tái sử dụng; mặc định chạy block kế tiếp sau reconciliation.
3. Chẩn đoán recorder/dependency từ dữ liệu lưu trước khi tiếp tục allocation phụ thuộc nó.
4. Dùng checkpoint khi có lý do phù hợp và cụ thể; giữ prompt ngắn trỏ RUN cùng next action, giảm chuỗi chỉ dẫn helper theo epoch.
5. Đánh giá vòng cải thiện tiếp theo bằng: câu hỏi được giải quyết, nghĩa vụ được đóng, lỗi orchestration tái diễn và số lần người dùng phải tiếp tục. Không tối ưu số request, số alert instance hay số phút chat.

Không đề xuất thêm lớp bằng chứng, manifest, phê duyệt hay quota context. Chưa chỉnh skill/helper trong lần đánh giá này.

## Các lượt thực thi đã đọc

- 2026-11-01 12:57:45–13:14:05 · **Chạy phiên bảo mật mới** · 16.3 phút · chat `01a195af-6c3c-7de3-a6d9-8b997379d36f`.
- 2026-11-01 14:08:09–14:35:10 · **Continue ZAP assessment** · 27.0 phút · chat `01a195c3-2906-7780-b7f5-379182dcf553`.
- 2026-11-01 14:41:44–15:10:21 · **Tiếp tục kiểm tra ZAP** · 28.6 phút · chat `01a1960e-9bd3-7ab1-a32d-0cad27c1bb9e`.
- 2026-11-01 15:11:53–15:28:46 · **Tiếp tục kiểm tra ZAP 100ms** · 16.9 phút · chat `01a1962a-3196-76d2-991b-2e8f4e6bf5e9`.
- 2026-11-01 15:41:15–16:00:57 · **Tiếp tục kiểm tra ZAP** · 19.7 phút · chat `01a1963c-1744-7e12-a569-ab23fd5a1b21`.
- 2026-11-01 16:30:55–16:47:05 · **Tiếp tục kiểm thử native live-stream** · 16.2 phút · chat `01a1965e-4aca-7390-ba5a-ca0b5546c64a`.
- 2026-11-01 16:48:53–17:00:49 · **Tiếp tục kiểm thử ZAP live-proof** · 11.9 phút · chat `01a19683-0348-73c0-b7a7-1a4221963d80`.
- 2026-11-01 17:01:10–17:18:13 · **Continue content-share testing** · 17.0 phút · chat `01a1968e-4438-7e62-9efe-77e12710ae41`.
- 2026-11-01 17:19:20–17:30:17 · **Resume 100ms recording assessment** · 11.0 phút · chat `01a1969e-e1a3-7dd3-8e75-c25072019370`.
- 2026-11-01 17:38:15–17:48:32 · **Resume ZAP content lifecycle checks** · 10.3 phút · chat `01a196b0-3652-7c61-9b1f-d6d181023176`.
- 2026-11-01 18:02:26–18:19:42 · **Tiếp tục đánh giá ZAP** · 17.3 phút · chat `01a196c6-5aba-7611-bc3f-1405b191ae99`.
- 2026-11-01 18:20:10–18:30:13 · **Tiếp tục đánh giá quyền WHEP** · 10.0 phút · chat `01a196d6-9ad1-74e0-b8f7-8fe1b4a522a5`.
- 2026-11-01 18:40:40–18:54:39 · **Tiếp tục đánh giá quyền WHEP** · 14.0 phút · chat `01a196d6-9ad1-74e0-b8f7-8fe1b4a522a5`.

Hai lượt disk gate, một lượt cleanup và lượt không có thời điểm kết thúc không đưa vào thống kê 13 lượt thực thi. Chat chỉnh skill chỉ dùng xác định mốc. Lịch sử trước mốc không dùng để chấm quy trình sau sửa.

## Nguồn nội bộ

- [Skill hiện hành](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/SKILL.md)
- [Quy tắc checkpoint/recovery](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md)
- [Helper tự nêu giới hạn kiểm tra handoff](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/scripts/review_open_work.py:268)
- [RUN chính thức](/Users/hahoangloc/Working/testing%20tool/assessment-results/100ms-fresh-20261101/RUN.json)
- [ALERTS](/Users/hahoangloc/Working/testing%20tool/assessment-results/100ms-fresh-20261101/ALERTS.json)
- [SCOPE_ALERTS](/Users/hahoangloc/Working/testing%20tool/assessment-results/100ms-fresh-20261101/SCOPE_ALERTS.json)
- [Allocation ledger](/Users/hahoangloc/Working/testing%20tool/.local/100ms-fresh-20261101/scans.json)

Các file RUN/ALERTS/SCOPE_ALERTS là con trỏ mutable và có thể được cập nhật bởi phiên khác. Các số trên là snapshot tại updatedAt đã nêu; báo cáo này không thay thế kết quả sản phẩm.


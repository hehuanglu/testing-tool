# Audit vận hành mcp-zap-repo-operations — 2026-11-03

## Kết luận

Skill có nhiều quy tắc đúng về không replay, approval, provenance và không kết luận quá bằng chứng. Điểm yếu nghiêm trọng là phần điều phối và khôi phục vẫn dựa quá nhiều vào agent tự giữ nhất quán giữa nhiều artifact, trong khi lớp persistence có các cửa sổ lỗi khiến chính API resume bị khóa. Lịch sử còn chứng minh một lỗi khác: agent tự dừng dù checkpoint và việc khả thi đã có. Viết thêm “hãy tiếp tục” không chứng minh đã khắc phục hành vi này.

Báo cáo có **31 phát hiện và giới hạn vận hành**. Đây là toàn bộ vấn đề có căn cứ trong phạm vi kiểm tra này, không phải lời bảo đảm đã phát hiện mọi bug của toàn bộ thư viện hay mọi chat. P1: có thể chặn vận hành/khôi phục hoặc phá hiệu quả kiểm thử trên phạm vi đáng kể. P2: giới hạn tích hợp, vận hành hoặc rủi ro cần xử lý. Không dùng P0 vì chưa có bằng chứng mất dữ liệu/unsafe replay thực tế.

## Phạm vi và chất lượng bằng chứng

- Đọc skill hiện hành, các reference cốt lõi về lifecycle, recovery, delegation, planning, runner, evidence, reporting và operational validation; kiểm tra source reviewer/selector/coordinator/journal/merge cùng tests liên quan.
- Đọc **8 chat** qua read_thread (các lượt được ghi rõ trong [bằng chứng lịch sử](/Users/hahoangloc/Working/testing tool/docs/reviews/zap-operations-audit-20261103/chat-evidence.md)); có chat còn trang cũ chưa đọc. Không lấy listing summary làm bằng chứng sự kiện.
- **H1** Locate ZAP skill checkpoint; **H2** Tiếp tục ZAP review và resume; **H3** Đánh giá khả năng khôi phục chat; **H4** Nghiệm thu skill ZAP trong context sạch; **H5** Tiếp tục đánh giá ZAP Clicon; **H6** Tiếp tục run Clicon; **H7** Tiếp tục đợt đánh giá ZAP; **H8** Vận hành skill MCP ZAP.
- Lời final của agent chứng minh điều agent đã báo cáo/quyết định dừng; không tự chứng minh mọi traffic đúng như báo cáo. Sự kiện scan/path ở F15 chưa được đối chiếu raw trong audit này.
- Đã tái hiện offline lease/journal/merge bằng fixture tạm. [Ca tái hiện](/Users/hahoangloc/Working/testing tool/docs/reviews/zap-operations-audit-20261103/recovery-repro.py), [phân tích chi tiết](/Users/hahoangloc/Working/testing tool/docs/reviews/zap-operations-audit-20261103/recovery-findings.md). Bài test selector dependency cũng dùng fixture giả. Không gửi traffic sản phẩm, không sửa skill/source, không đổi RUN/approval/Sheets/runtime.
- Working tree có nhiều thay đổi chưa commit và file mới. HEAD nền là 18f17860bad327a18345f949644aac4d40b7fece; review nhắm bytes hiện hành, không chỉ HEAD. Xem source-snapshot.json để đối chiếu digest.

## Điểm đáng chú ý từ lịch sử

1. **Ngắt thật và tự dừng là hai lỗi khác nhau.** H4 có turn failed vì usage limit; H6 có lỗi kiểm soát nền tảng. H3/H5 có turn completed, agent tự nhận dừng khi còn việc làm được. Không quy mọi lần ngắt cho model/context/usage limit.
2. **Checkpoint có dữ liệu nhưng chưa đủ tự giải thích.** H1 ban đầu chỉ liệt kê ba vị trí; sau đó phát hiện checklist/RUN/selector/currentFocus lệch nhau. Hiện cùng assessmentId xuất hiện trong hai RUN lớn với 145 và 175 operations.
3. **Handoff có thể phát tán lỗi điều phối.** H4 tạo prompt giới hạn kết thúc theo lane, rồi prompt đó được dùng ở lượt sau. Một số lượt khi ấy có user instruction rõ về kết thúc block nên không thể gán toàn bộ trách nhiệm cho việc agent không tuân lời user; vấn đề là workflow đã sinh ra chuỗi prompt hẹp này.
4. **Nhiều request không tương đương tiến độ đánh giá.** H7 thu trên một trăm Requester messages trước khi xử lý xong origin/context của reviewer. H4 phải sửa cả allocation và cặp actor. Đây là nợ tích hợp evidence.
5. **Có sửa thật, chưa có chứng nhận toàn cục.** Current skill đã thêm full remaining workflow vào prompt, canary evidence trước mở rộng và audit inventory hai chiều. Các thay đổi này không được gọi là lỗi còn nguyên. Cần nghiệm thu lại hành vi, không dùng lịch sử cũ để kết luận sửa mới vô hiệu.

## Danh sách phát hiện

### F01 · P1 · Không có điểm vào duy nhất để tìm RUN chính thức

**Nhóm:** Khôi phục. **Mức chứng cứ:** Lịch sử + hiện trạng.

**Bằng chứng:** H1 trả ba checklist rồi mới đối soát. Hiện hai thư mục .zap-20261103-4qUdAo và .zap-skill-acceptance-20261103-w1 cùng assessmentId và planRevision nhưng có 145 và 175 operations.

**Hệ quả:** Chat mới phải tự đoán lineage trước khi làm việc; chọn bản cũ dễ bỏ sót kết quả hoặc diễn giải sai bước tiếp theo.

**Hướng xử lý:** Một registry theo assessmentId trỏ tới working directory và generation chính thức; bản sao phải ghi rõ read-only/superseded và predecessor.

**Nguồn:** [retention-stop-and-recovery.md:66](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md:66>) · [retention-stop-and-recovery.md:167](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md:167>).

### F02 · P1 · Checkpoint gồm nhiều bản trạng thái phải cập nhật thủ công

**Nhóm:** Khôi phục. **Mức chứng cứ:** Lịch sử + thiết kế.

**Bằng chứng:** H1 ghi nhận checklist cũ hơn RUN; resumeNextReadback trỏ Z-07-A01-03 trong khi currentFocus đã sang bước khác. Skill giao checklist, RUN, journal, packet và continuation các phần của trạng thái.

**Hệ quả:** Một save thành công không xác lập bộ checkpoint nhất quán. Agent phải dựng lại trạng thái khi bị ngắt giữa các lần ghi.

**Hướng xử lý:** Một committed generation; checklist, next action và prompt là projection sinh từ state/journal, không là nguồn chân lý độc lập.

**Nguồn:** [retention-stop-and-recovery.md:19](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md:19>) · [business-work-blocks.md:12](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/business-work-blocks.md:12>).

### F03 · P1 · Acquire lease không nguyên tử với journal

**Nhóm:** Khôi phục. **Mức chứng cứ:** Tái hiện offline.

**Bằng chứng:** Ghi từng file lease trước journal leased. Crash trong khoảng này tạo lease không có task binding trong journal; reviewer/reacquire/release bình thường không phục hồi được. Xem recovery-repro.py. Ngoài ra, nếu journal đã ghi nhưng báo lỗi, rollback xóa lease vẫn để lại record leased; ca R3 tái hiện cùng dạng bế tắc.

**Hệ quả:** Có thể bế tắc toàn coordinator ngay cả khi chưa phát effect.

**Hướng xử lý:** Ghi transaction intent có đủ binding trước, rồi commit lease; cung cấp recovery có kiểm chứng, không xóa lease mù.

**Nguồn:** [criteria_delegation.py:308](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_delegation.py:308>) · [criteria_delegation.py:230](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_delegation.py:230>).

### F04 · P1 · Release nhiều lease không tiếp tục được sau gián đoạn

**Nhóm:** Khôi phục. **Mức chứng cứ:** Tái hiện offline.

**Bằng chứng:** Journal released được ghi trước vòng unlink. Ngắt sau unlink đầu tiên để lại lease mồ côi; retry cần đủ lease cũ nên thất bại.

**Hệ quả:** Đã xong effect nhưng không thể đóng tài nguyên hoặc tiếp tục run bằng API bình thường.

**Hướng xử lý:** Release phải idempotent, lưu release-intent/commit và tiếp tục xóa đúng các lease còn lại sau xác minh binding.

**Nguồn:** [criteria_delegation.py:461](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_delegation.py:461>).

### F05 · P1 · Journal bị ghi dở khóa luôn đường chẩn đoán bình thường

**Nhóm:** Khôi phục. **Mức chứng cứ:** Tái hiện offline.

**Bằng chứng:** Journal có allow_partial_tail nhưng Coordinator luôn mở ở chế độ strict; một record cuối thiếu newline làm status/reviewer/recovery không đọc được.

**Hệ quả:** Fail-closed ngăn replay là đúng, nhưng thiếu chế độ phục hồi an toàn để đọc prefix hợp lệ và cô lập phần chưa xác định.

**Hướng xử lý:** Read-only salvage giữ nguyên raw, báo tail chưa xác định và khóa effect liên quan; recovery riêng có audit trail.

**Nguồn:** [journal.py:28](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/journal.py:28>) · [criteria_delegation.py:226](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_delegation.py:226>).

### F06 · P1 · Đầu việc resume không xét dependency đã khai báo

**Nhóm:** Khôi phục. **Mức chứng cứ:** Tái hiện offline.

**Bằng chứng:** Với plan hợp lệ T1.dependsOnCases=[T2], cả hai chưa xong, resume_next vẫn trả T1 do sắp thứ tự ID. Hàm chỉ là candidate, đúng như tài liệu thừa nhận.

**Hệ quả:** Không thể dùng selector như scheduler; agent dễ quay lại ca chưa đủ điều kiện hoặc phải tự làm lại dependency graph sau mỗi ngắt. Chưa chứng minh dispatch trái phép.

**Hướng xử lý:** Selector trả ready/deferred/needs-readback có lý do từ dependency graph, block và mốc thời gian; giữ admission riêng.

**Nguồn:** [criteria_resume.py:47](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_resume.py:47>) · [criteria_workflow.py:123](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_workflow.py:123>) · [retention-stop-and-recovery.md:33](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md:33>).

### F07 · P1 · Khôi phục trạng thái không đồng nghĩa tiếp tục thực thi

**Nhóm:** Khôi phục. **Mức chứng cứ:** Thiết kế + lịch sử.

**Bằng chứng:** H3 agent thừa nhận bài thử chỉ chứng minh process mới đọc receipt và tìm việc tiếp theo, không chứng minh agent thực hiện tiếp. Skill cũng xác nhận hard stop cần lượt mới hoặc external wake-up.

**Hệ quả:** Người dùng tiếp tục đóng vai bộ lập lịch; checkpoint không tự đánh thức chat sau usage limit.

**Hướng xử lý:** Tách rõ recoverable state, autonomous within-turn execution và external resumption. Nếu được giao tự vận hành qua hard stop, cần cơ chế wake-up được cấp quyền riêng.

**Nguồn:** [retention-stop-and-recovery.md:42](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md:42>) · [operational-validation.md:44](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-validation.md:44>).

### F08 · P1 · Dừng tự nguyện khi vẫn có việc khả thi

**Nhóm:** Điều phối. **Mức chứng cứ:** Đã xảy ra; sửa prose chưa đủ nghiệm thu.

**Bằng chứng:** H3: agent nói rõ không bị usage limit nhưng vẫn dừng; lượt sau tiếp tục thừa nhận kết thúc khi còn việc. H5 lặp lại sau khi user hỏi 'thế sao dừng?'.

**Hệ quả:** Không đạt mục tiêu làm hết workflow; tăng số lần người dùng can thiệp, mất context và lãng phí setup.

**Hướng xử lý:** Exit decision phải đối chiếu remaining ready work và lý do dừng; acceptance đo hành vi thực hiện liên tiếp qua nhiều block, không chỉ lưu next action.

**Nguồn:** [SKILL.md:30](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/SKILL.md:30>) · [retention-stop-and-recovery.md:38](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md:38>).

### F09 · P1 · Prompt nối tiếp tự thu hẹp nhiệm vụ còn lại

**Nhóm:** Điều phối. **Mức chứng cứ:** Lịch sử; tài liệu hiện đã sửa.

**Bằng chứng:** H4 final tạo prompt 'Kết thúc phần kế khi lane đã chọn được kiểm chứng hoặc có dependency tái hiện được'. User copy prompt, khiến giới hạn do agent tạo trở thành chỉ dẫn cho lượt sau. H1 xác nhận nguyên nhân.

**Hệ quả:** Chuỗi chat bị chia thành các lượt nhỏ bắt người dùng nhắn tiếp dù assessment vẫn còn quyền và việc.

**Hướng xử lý:** Không kế thừa tự động giới hạn do generated prompt đặt ra. Prompt chỉ chứa locator và ưu tiên; stopping rule lấy từ yêu cầu thật và canonical state. Dòng 140 hiện đã thêm yêu cầu này, chưa đủ chứng minh hành vi đã hết lỗi.

**Nguồn:** [retention-stop-and-recovery.md:138](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md:138>) · [retention-stop-and-recovery.md:140](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md:140>).

### F10 · P2 · Lỗi một lane dễ trở thành điểm dừng cả lượt

**Nhóm:** Điều phối. **Mức chứng cứ:** Thiết kế + lịch sử.

**Bằng chứng:** H3 guard UI lỗi nhưng SOURCE-A02-03 còn làm được; H5 scan sai phạm vi nhưng source/DOM vẫn khả thi. Skill hiện nói tiếp tục độc lập, còn selector và checklist không tự thực hiện chuyển nhánh.

**Hệ quả:** Một blocker cục bộ gây ngừng toàn cục và lặp chẩn đoán ở chat kế.

**Hướng xử lý:** Lưu dependency theo resource/case và hàng ready độc lập; ghi decision trace khi không chuyển được nhánh.

**Nguồn:** [local-remediation-and-continuation.md:25](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/local-remediation-and-continuation.md:25>) · [criteria_resume.py:34](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_resume.py:34>).

### F11 · P2 · Lịch block không phải trạng thái thực thi có schema chung

**Nhóm:** Điều phối. **Mức chứng cứ:** Thiết kế + hiện trạng.

**Bằng chứng:** H2 có 12 block ngoài plan, 13 work unit, 82 case. business-work-blocks chỉ yêu cầu agent ghi và đối chiếu; selector không nhận lịch block.

**Hệ quả:** Chat khác phải hiểu lại quan hệ block/case/work unit và tự quyết ưu tiên; metadata có thể đúng riêng lẻ nhưng lệch nhau.

**Hướng xử lý:** Định nghĩa schema lịch nhẹ gắn plan digest, case IDs, trạng thái và thứ tự phụ thuộc; validator kiểm tra mapping và projection.

**Nguồn:** [criteria-driven-workflow.md:31](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md:31>) · [business-work-blocks.md:3](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/business-work-blocks.md:3>) · [criteria_resume.py:6](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_resume.py:6>).

### F12 · P2 · TTL đặt cuối nhưng không có lịch thức dậy hay phục hồi control tự động

**Nhóm:** Điều phối. **Mức chứng cứ:** Thiết kế.

**Bằng chứng:** Skill nói rõ deadline không tạo background monitor. Nếu chat ngắt lâu, same token/fixture/control có thể thay đổi; deadline đơn lẻ không đủ dùng lại.

**Hệ quả:** Bài expiry có thể mất điều kiện đối chứng và phải tạo attempt mới; user phải nhớ mốc giờ.

**Hướng xử lý:** Lưu subject/control lifecycle và deadline riêng, revalidation hữu hạn, trạng thái expired-invalidated/ready. Chỉ thêm wake-up khi được user giao.

**Nguồn:** [business-work-blocks.md:16](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/business-work-blocks.md:16>) · [retention-stop-and-recovery.md:34](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md:34>).

### F13 · P1 · Thu nhiều traffic trước khi chứng minh đường đóng evidence hoạt động

**Nhóm:** Bằng chứng & phạm vi. **Mức chứng cứ:** Lịch sử; có sửa nhưng chưa qualified mọi lane.

**Bằng chứng:** H7 ghi 121 Requester messages, 32 browser responses, nhưng alias Docker khác localhost của từng case khiến reviewer không nhận nhiều evidence. Lỗi lẽ ra lộ ngay message đầu.

**Hệ quả:** Chi phí runtime đã phát sinh nhưng tiến độ verdict thấp; resume phải sửa adapter và linking thay vì hoàn tất testing.

**Hướng xử lý:** Giữ lane canary capture→receipt→semantic→reviewer và qualify từng kiểu actor/context cần thiết trước mở rộng; quy tắc mới đã có, cần kiểm chứng thực thi.

**Nguồn:** [business-work-blocks.md:6](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/business-work-blocks.md:6>) · [operational-readback.md:23](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-readback.md:23>).

### F14 · P1 · Hợp đồng context chưa biểu diễn đủ bài kiểm tra so sánh

**Nhóm:** Bằng chứng & phạm vi. **Mức chứng cứ:** Lịch sử; sửa từng phần.

**Bằng chứng:** H4 helper từng chỉ nhận cặp cùng actor; owner/non-owner BOLA và cặp route directory bị chặn. Sau đó phải thêm finite allocation/role-object matrix.

**Hệ quả:** Reviewer chặn evidence đúng không phải lỗi bảo mật sản phẩm; agent dễ mắc vòng sửa cơ chế giữa assessment.

**Hướng xử lý:** Qualification bằng các câu hỏi chuẩn: hai actor/cùng object, hai route, alias deployment, same-token expiry; giữ từng native context, không nới blanket equality.

**Nguồn:** [operational-readback.md:19](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-readback.md:19>) · [operational-readback.md:25](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-readback.md:25>).

### F15 · P1 · Cấu hình scan không bảo đảm phạm vi thực thi mong đợi

**Nhóm:** Bằng chứng & phạm vi. **Mức chứng cứ:** Lịch sử vận hành, chưa retest tại audit này.

**Bằng chứng:** H5 final ghi scan tắt đệ quy vẫn có 25/32 request tới path khác trên cùng Local Compose. Đây là lời báo cáo từ chat, chưa xác minh lại raw trong audit này.

**Hệ quả:** Không thể coi chọn URL/rule là guard. Nguy hiểm hơn với route có trạng thái; loại evidence sau chạy không hoàn tác traffic.

**Hướng xử lý:** Egress/method/path guard có khả năng cưỡng chế và telemetry tất cả request; thử guard trong sandbox phù hợp trước lane có effect.

**Nguồn:** [runner-routing.md:11](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/runner-routing.md:11>) · [native-operation-routing.md:1](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/native-operation-routing.md:1>).

### F16 · P1 · Plan có đủ hàng catalog nhưng chưa chứng minh bao phủ sản phẩm

**Nhóm:** Bằng chứng & phạm vi. **Mức chứng cứ:** Lịch sử + giới hạn thiết kế.

**Bằng chứng:** H8 v3 có đủ 50 tiêu chí nhưng agent thừa nhận thiếu discovery Client Spider/OpenAPI và đối chiếu bề mặt. Quy trình coordinator audit được sửa sau khi user hỏi.

**Hệ quả:** Có thể hoàn thành tất cả ca do mình nghĩ ra mà bỏ sót endpoint/role/state thuộc tiêu chí universal.

**Hướng xử lý:** Giữ mapping hai chiều inventory↔cases, nguồn inventory độc lập và coverage delta sau discovery. Kiểm tra chất lượng trên sản phẩm khác, không chỉ v5.

**Nguồn:** [criteria-driven-workflow.md:17](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md:17>) · [delegation-policy.md:54](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/delegation-policy.md:54>).

### F17 · P2 · Reviewer kiểm tra khai báo, không tự chứng minh ngữ nghĩa

**Nhóm:** Bằng chứng & phạm vi. **Mức chứng cứ:** Giới hạn thiết kế được thừa nhận.

**Bằng chứng:** Skill nói helpers không chứng minh raw-to-semantic accuracy; người điều phối vẫn gán unit, outcome và basis. Một label đúng cấu trúc không chứng minh quan sát đủ.

**Hệ quả:** 'Reviewer accepted' dễ bị hiểu thành kiểm chứng độc lập của kết luận; audit recovery thuần fixture không phát hiện oracle sai.

**Hướng xử lý:** Evidence adapters kiểm tra predicate cụ thể, nguồn raw bất biến, controls âm/dương; review độc lập tập trung vào ca rủi ro thay vì đặt thêm chữ ký cho mọi ca.

**Nguồn:** [criteria-driven-workflow.md:38](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md:38>) · [operational-validation.md:65](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-validation.md:65>).

### F18 · P2 · Không có đường end-to-end v2 chung từ plan tới executor

**Nhóm:** Runtime & công cụ. **Mức chứng cứ:** Thiết kế.

**Bằng chứng:** Runner-routing nói v2 dùng Python callback registry, không phải CLI live chung; discovery không tự tạo admitted executor. Native read CLI chỉ hỗ trợ nhánh hữu hạn.

**Hệ quả:** Mỗi lần đổi sản phẩm/capability hoặc fresh context agent phải ghép nhiều API, tăng lỗi interface và code tạm.

**Hướng xử lý:** Một entrypoint có inspect/plan/readback/resume thống nhất, adapter interface versioned; khai báo phần chưa hỗ trợ trước Gate 2.

**Nguồn:** [criteria-driven-workflow.md:32](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md:32>) · [runner-routing.md:59](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/runner-routing.md:59>) · [helper-contract-map.md:3](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/helper-contract-map.md:3>).

### F19 · P2 · Tính product-neutral của workflow lớn hơn khả năng runner thực tế

**Nhóm:** Runtime & công cụ. **Mức chứng cứ:** Giới hạn nguồn đã công bố.

**Bằng chứng:** Anonymous/auth lane chủ yếu rules 40012/40018; fixture authenticated FE còn finalsource-specific; native read bind endpoint loopback cố định. BOLA common direct-http không tự thành ZAP-derived.

**Hệ quả:** Người vận hành dễ tưởng có runner cho mọi câu hỏi; mất nhiều thời gian xây adapter mới hoặc chọn sai provenance.

**Hướng xử lý:** Capability matrix theo operation/auth/protocol/body/fixture/readback/deployment, hiển thị unsupported ngay khi lập plan; không quảng bá workflow như universal executor.

**Nguồn:** [runner-routing.md:21](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/runner-routing.md:21>) · [runner-routing.md:39](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/runner-routing.md:39>) · [runner-routing.md:63](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/runner-routing.md:63>).

### F20 · P2 · Cold start thiếu preflight một lệnh cho toàn bộ phụ thuộc đã dùng

**Nhóm:** Runtime & công cụ. **Mức chứng cứ:** Thiết kế.

**Bằng chứng:** Setup yêu cầu Python 3.13 + lockfile, environment riêng; connector/browser/scanner phụ thuộc executor. Resume example dùng 'python' thay vì ZAP_PYTHON đã xác định.

**Hệ quả:** Chat mới có thể dùng sai interpreter, cwd, skill copy hoặc tool surface; lỗi vặt xảy ra trước khi đọc được checkpoint.

**Hướng xử lý:** Persist runtime manifest với executable/version/dependency lock/skill digest; doctor read-only kiểm tra đúng những phụ thuộc của next action.

**Nguồn:** [setup.md:18](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/setup.md:18>) · [retention-stop-and-recovery.md:25](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md:25>).

### F21 · P2 · Sửa helper ngay trong run làm tăng rủi ro lệch pin và contract

**Nhóm:** Runtime & công cụ. **Mức chứng cứ:** Thiết kế.

**Bằng chứng:** Skill cho phép repair và cảnh báo shared pins gồm recipes khác; nhiều file hiện dirty/untracked nên HEAD đơn lẻ không xác định bytes đang chạy.

**Hệ quả:** Chat mới có thể dùng code khác code tạo evidence; sửa một lane làm hỏng allocation khác, hoặc lại cần dựng binding.

**Hướng xử lý:** Ghim digest thực tế của executor/reader cho mỗi attempt, có migration/compatibility và smoke hồi quy trọng điểm; giữ sửa độc lập với raw history.

**Nguồn:** [runner-routing.md:17](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/runner-routing.md:17>) · [local-remediation-and-continuation.md:11](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/local-remediation-and-continuation.md:11>).

### F22 · P2 · Preparation subagent là phụ thuộc bắt buộc không có fallback coordinator

**Nhóm:** Delegation. **Mức chứng cứ:** Thiết kế.

**Bằng chứng:** Delegation-policy yêu cầu giữ dependency nếu preparation worker unavailable, không được coordinator thay vai dù có đủ dữ liệu.

**Hệ quả:** Host không có worker hoặc hết slot/model có thể chặn intake/planning vì cơ chế tổ chức, không vì nghiệp vụ hay evidence.

**Hướng xử lý:** Cho phép fallback được ghi nhận khi host không hỗ trợ; giữ chuẩn review chất lượng thay vì buộc một topology thực thi.

**Nguồn:** [delegation-policy.md:64](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/delegation-policy.md:64>) · [delegation-policy.md:128](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/delegation-policy.md:128>).

### F23 · P1 · Coordinator có thể kết thúc khi worker và công việc còn hoạt động

**Nhóm:** Delegation. **Mức chứng cứ:** Lịch sử + rủi ro thiết kế.

**Bằng chứng:** H7 user phải hỏi '3 sub agent đang chạy sao ko tiếp tục?'; agent sau đó nhận kết thúc quá sớm. Skill nói worker không đồng nghĩa monitor.

**Hệ quả:** Draft/result không được merge kịp; worker/producer và lease có thể còn cần người giám sát trong lúc root đã dừng.

**Hướng xử lý:** Checkpoint bao gồm active worker tasks, outputs, resource supervision; root exit kiểm tra toàn bộ worker và cơ chế nhận kết quả, không chỉ ca hiện tại.

**Nguồn:** [delegation-policy.md:118](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/delegation-policy.md:118>) · [retention-stop-and-recovery.md:177](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md:177>).

### F24 · P2 · Lớp v1/v2 và nhiều khái niệm trạng thái làm cold resume nặng

**Nhóm:** Tài liệu & khả năng bảo trì. **Mức chứng cứ:** Hiện trạng.

**Bằng chứng:** Các reference gốc cộng với criteria modules đang gần 4.000 dòng; recovery hướng dẫn inspect-resume legacy cạnh resume-next v2. RUN đang dùng có 46.559 dòng / 2.782.613 bytes.

**Hệ quả:** Agent phải đọc nhiều để tránh chọn nhầm helper; context loãng và lặp inspection là chi phí có thể thấy, dù số dòng tự nó không phải bug.

**Hướng xử lý:** Tách current operating path khỏi archive; một trang route theo phase/version, typed checkpoint nhỏ và truy vấn theo case thay vì đọc toàn RUN.

**Nguồn:** [retention-stop-and-recovery.md:5](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md:5>) · [helper-contract-map.md:5](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/helper-contract-map.md:5>).

### F25 · P2 · Resume template có thể loại source evidence dù plan cho phép

**Nhóm:** Tài liệu & khả năng bảo trì. **Mức chứng cứ:** Thiết kế.

**Bằng chứng:** Template recovery dòng 142 nói 'exclude external-tool/source-only findings'; workflow lại cho source/config và catalog static review theo authority. Không nói rõ chỉ loại khỏi ZAP-derived ALERTS.

**Hệ quả:** Fresh chat có thể hiểu sai thành bỏ source work hợp lệ, nhất là run v5 có nhiều SOURCE cases.

**Hướng xử lý:** Ghi rõ phân loại provenance: source-only được dùng cho criterion có method đã duyệt; không đưa vào native/ZAP-derived alert counts.

**Nguồn:** [retention-stop-and-recovery.md:142](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md:142>) · [SKILL.md:20](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/SKILL.md:20>) · [criteria-driven-workflow.md:11](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md:11>).

### F26 · P1 · Acceptance chủ yếu chứng minh helper, chưa chứng minh agent vận hành liên tục

**Nhóm:** Nghiệm thu. **Mức chứng cứ:** Lịch sử + hiện trạng test.

**Bằng chứng:** test_criteria_resume có 4 unit tests: restore JSON, candidate, dependency, approval. H3 thừa nhận test recovery không chứng minh agent tiếp tục làm việc. Các chat lặp lại lỗi dừng sau nhiều lần sửa prose.

**Hệ quả:** Có test xanh nhưng trải nghiệm vận hành vẫn thất bại. Fault windows lease/journal chưa được những test selector này bao phủ.

**Hướng xử lý:** Nghiệm thu tách 3 tầng: durability fault injection, cold-start replay/readback, agent nhiều block với can thiệp user được đếm; không biến số tests thành chứng nhận toàn workflow.

**Nguồn:** [test_criteria_resume.py:11](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/tests/test_criteria_resume.py:11>) · [operational-validation.md:42](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-validation.md:42>).

### F27 · P2 · Final-only publishing kết hợp pending vô hạn dễ làm user không có bản mới dùng được

**Nhóm:** Bàn giao & vòng đời. **Mức chứng cứ:** Thiết kế; lựa chọn user cần giữ.

**Bằng chứng:** H7 user chủ động yêu cầu chỉ sync lượt cuối; H2/H3 còn 39 pending và sheet tạm. V2 cấm complete khi còn criterion applicable thiếu evidence, kể cả hết feasible actions.

**Hệ quả:** Không được sửa bằng cách tự sync thường xuyên hoặc gán N/A. Nhưng 'final delivery turn' cần tách khỏi evidence completion để tránh treo báo cáo vô hạn.

**Hướng xử lý:** Giữ final-only; định nghĩa bàn giao partial tại user stop hoặc dependency thật, source revision và trạng thái delivery rõ. Chốt cách bàn giao giới hạn theo yêu cầu user, không nới verdict.

**Nguồn:** [single-table-drive-output.md:50](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/single-table-drive-output.md:50>) · [criteria-driven-workflow.md:86](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md:86>).

### F28 · P2 · Delivery state được agent quản lý, không nằm trong completion reviewer

**Nhóm:** Bàn giao & vòng đời. **Mức chứng cứ:** Thiết kế.

**Bằng chứng:** Skill tách assessment completed khỏi delivery; driveOutput và verified snapshot là agent-maintained. resume_next trả verify-final-delivery kể cả workflow đã completed mà không xét driveOutput.

**Hệ quả:** Dễ lặp bước verify hoặc kết thúc với bảng cũ nếu chỉ nhìn assessmentStatus; chưa có kết thúc workflow hợp nhất bằng máy.

**Hướng xử lý:** State machine riêng cho projection/write/readback/verified với source digest; resume trả done chỉ khi cả assessment và delivery tương ứng đã khép.

**Nguồn:** [criteria_resume.py:75](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_resume.py:75>) · [single-table-drive-output.md:48](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/single-table-drive-output.md:48>).

### F29 · P2 · Merge CLI không tự promote canonical RUN và không idempotent cùng output

**Nhóm:** Khôi phục. **Mức chứng cứ:** Giới hạn triển khai.

**Bằng chứng:** criteria-merge ghi output mới qua atomic_bytes; canonical input và pointer do agent cập nhật ngoài lệnh. Gọi lại với output tồn tại thất bại, không trả receipt của lần thành công trước.

**Hệ quả:** Ngắt sau ghi file nhưng trước thông báo/promotion làm chat sau không biết bản nào được nhận; thêm một bước đối soát thủ công.

**Hướng xử lý:** Output có transaction ID/input revision và receipt bền vững; retry đọc kết quả cũ khi digest trùng, canonical promotion bằng compare-and-swap.

**Nguồn:** [product_scope_cli.py:117](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/product_scope_cli.py:117>).

### F30 · P2 · Không phân biệt rõ host interruption với lỗi vận hành khi đánh giá recovery

**Nhóm:** Gián đoạn nền tảng. **Mức chứng cứ:** Lịch sử; không quy sai nguyên nhân.

**Bằng chứng:** H4 có failed usage limit; H6 có failed cybersecurity-risk ở cả lượt 'tiếp tục' và 'hey'. H3/H5 lại là completed voluntary stop.

**Hệ quả:** Nếu gộp tất cả thành lỗi checkpoint sẽ sửa sai chỗ; skill không thể tự vượt hạn mức hoặc kiểm soát nền tảng.

**Hướng xử lý:** Lưu stop cause theo host/user/dependency/voluntary, trạng thái effects trước ngắt, đường phục hồi được phép. Không suy đoán nguyên nhân policy flag và không tìm cách né kiểm soát.

**Nguồn:** [retention-stop-and-recovery.md:42](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md:42>) · [operational-validation.md:46](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-validation.md:46>).

### F31 · P2 · Giữ coordinator lock trong lúc chạy callback bên ngoài

**Nhóm:** Khôi phục. **Mức chứng cứ:** Rủi ro nguồn, chưa tái hiện hang.

**Bằng chứng:** dispatch giữ lock assessment trong khi gọi admitted executor; timeout tùy callback, coordinator không tự chặn thời gian. Không khẳng định executor thực tế đang treo.

**Hệ quả:** Một callback treo có thể chặn status, resume và việc độc lập cần cùng lock; recovery phải chờ hoặc can thiệp process.

**Hướng xử lý:** Tách claim/intent dưới lock khỏi I/O dài; executor deadline và cancellation có journal; reacquire lock để commit ACK. Không giải phóng lease chỉ vì timeout.

**Nguồn:** [criteria_delegation.py:390](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_delegation.py:390>).

## Trình tự sửa đề xuất

1. **Làm recovery thực sự dùng được:** xử lý transaction acquire/release, ambiguous write và torn tail; giữ nguyên chặn replay. Một journal hỏng không được tự coi effect đã thất bại, nhưng phải có đường đọc prefix/chẩn đoán và recovery có bằng chứng.
2. **Một định danh và một state chính thức:** registry assessment → canonical directory/generation; save có commit; output/checklist/prompt là projection. Có công cụ inspect read-only trả next action, phụ thuộc, pending effects, artifacts và lý do lựa chọn.
3. **Biến lịch thành cơ chế chọn việc:** dependency/block/deadline/resource-aware selector, trạng thái ready/waiting/readback; agent phải thực hiện candidate khả thi tiếp theo thay vì chỉ ghi lại rồi kết thúc.
4. **Kiểm chứng tích hợp trước mở rộng:** một đơn vị đại diện cho từng lane đi qua đúng reader/reviewer, bao gồm actor pair/origin aliases/fixture lifecycle. Không nới guard hoặc làm giả context để qua test.
5. **Nghiệm thu cách agent thực sự chạy:** nhiều block độc lập, một lane lỗi, thay worker, fresh chat và gián đoạn ở từng ranh giới durable write. Đo số can thiệp người dùng, số effect bị replay (phải 0), số case đóng và thời gian khôi phục; tests xanh chỉ là một lớp.
6. **Chốt lifecycle bàn giao:** giữ final-only Sheets theo yêu cầu đã ghi trong H7; tách completion, user stop, waiting dependency và verified delivery. Hard-stop wake-up là chức năng riêng cần được giao, không giả vờ checkpoint tự làm được.

## Điều không nên quy là “điểm tệ”

- Hai gate, all_cases, nhóm nghiệp vụ, TTL cuối và chỉ sync Sheets cuối là lựa chọn đã có trong lịch sử yêu cầu. Điểm cần sửa là cách thực thi/đồng bộ, không tự ý bỏ các lựa chọn đó.
- Không replay unknown effects, giữ nguồn gốc evidence, không hạ guard để chạy tiếp, không biến pending thành N/A là các bảo vệ cần giữ.
- Skill không thể tự vượt usage limit hay kiểm soát nền tảng. Không có bằng chứng audit này xác định chính xác nguyên nhân nội bộ của policy flag.
- Những chỗ agent tự thừa nhận lỗi không đủ chứng minh mọi lỗi cùng nguyên nhân. Những finding thuần thiết kế/rủi ro được ghi riêng, không trình bày như incident đã xảy ra.

## Giới hạn kiểm chứng

Các repro mô phỏng đúng trạng thái disk hoặc inject lỗi ở ranh giới ghi, không phải thử power loss thật. Chưa fault-inject mọi executor, chưa kiểm tra mọi sản phẩm/protocol, chưa chạy toàn bộ suite và chưa nghiệm thu autonomous agent mới đến hết plan. Không xác nhận can thiệp nào đã sửa xong chỉ từ văn bản skill.


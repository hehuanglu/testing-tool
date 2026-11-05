# Audit quy trình vận hành ZAP và đường kết thúc công việc

Ngày audit: 02/11/2026. Đối tượng: skill repo-local `mcp-zap-repo-operations`, lịch sử vận hành 100ms và bộ báo cáo chính thức. Snapshot báo cáo cập nhật **04:29:20 ngày 02/11/2026, giờ Việt Nam**, bundle `7d24ab74-9390-4425-9369-d82313e70deb`. HEAD workspace `18f17860b`, có nhiều thay đổi chưa commit từ trước; audit không chỉnh những thay đổi đó.

## Kết luận

**Có tiến triển kỹ thuật đáng kể, nhưng điều phối và định nghĩa điểm kết thúc chưa tốt.** Đã có kiểm thử thực, hai vấn đề quyền media được đưa sang sửa và retest, rồi phát hiện giới hạn kiến trúc khi adapter lỗi. Cảm giác quanh quẩn có căn cứ: nhiều checkpoint trước đây chưa thuyết phục, chi phí khôi phục lớn, inventory thiếu điều kiện đóng cụ thể trong giai đoạn đầu, và nhiều loại nhiệm vụ cùng dùng một nhãn `partial`.

Không nên giao tiếp tục bằng mục tiêu “scan đến khi hết partial”. Assessment đầy đủ chưa hoàn tất; hai bản sửa được giao đã triển khai và được kiểm chứng trong các trường hợp ghi nhận; đối soát phạm vi đã hoàn tất cho dữ liệu hiện có. Đây là ba kết luận khác nhau.

## Chúng ta đã làm gì?

1. **Dựng khả năng vận hành và giữ trạng thái.** Xác minh source/build/runtime, actor/token/role, fixture/version/proof, nguồn truy cập được phép, tài nguyên và snapshot. Có phục hồi session ZAP, đối soát timeout trước retry, giữ lịch sử. Đây là công việc hỗ trợ, không tự thành coverage.
2. **Kiểm thử API qua ZAP.** Đã thực hiện anonymous/authenticated, input JSON/path/header, XSS/SQLi và kiểm tra boundary, role, ownership, receipt/idempotency, cursor, LEFT/ENDED trên các nhánh session/chat/participant/preferences/stage/content/live/recording. RUN có **60 operation native active allocation**, bao gồm kết quả thiếu hoặc bị chặn; không phải 60 nghĩa vụ đã đóng.
3. **Kiểm thử UI và media thật.** Có luồng anonymous/authenticated, PDF upload/Blob/filename/STOP, screen/live, WHIP/WHEP, receiver thực và recording có segment. Phần dựng fixture/media trực tiếp được phân biệt với traffic qua ZAP. Có những lần không đạt readiness; không suy outbound frames thành recording thành công.
4. **Điều tra nguyên nhân thiếu coverage.** Đã xử lý zero-payload, SiteNode/body cũ, reader object/string, version, codec/recording readiness và lỗi đồng bộ fixture. Trace mới quan sát được cơ chế STAGE STOP503 cùng reader readmission; bốn generation recording mới có segment. Những kết quả mới không xác định chắc chắn nguyên nhân của mọi failure lịch sử.
5. **Mở và kiểm tra phạm vi internal sau khi được duyệt.** Ba API internal được kiểm tra bằng service identity/network namespace phù hợp; scope guard được giữ. Có 24 payload ancestor/out-of-prefix không được thực thi và không được tính coverage.
6. **Triage hai vấn đề quyền media.** Ba observation lịch sử đại diện hai mối lo: người không tạo resource DELETE được khi biết URL đầy đủ; receiver đã LEFT vẫn nhận media. Kết luận dựa trên policy được xác định trong phiên; chưa chứng minh việc đánh cắp URL secret. Đây là ZAP-derived observations, không phải native alerts.
7. **Sửa sản phẩm và retest trong phạm vi được giao riêng.** Creator-only DELETE và cleanup receiver khi LEFT được triển khai ở worktree remediation độc lập; có retest theo image/resource class, restart/recovery, chín receiver, owner LEAVE và parent END. Source chưa commit/push theo trạng thái RUN; audit này không xác minh lại working tree sản phẩm hoặc build.
8. **Kiểm tra câu hỏi mới và chốt dữ liệu.** Bổ sung inventory PATCH/OPTIONS và kiểm tra ownership/input; kiểm tra END/owner LEAVE/recording END khi adapter lỗi. Cuối cùng rà đủ 37 inventory unit và 50 tiêu chí, sửa credit sai về password/token rotation, đồng bộ ba báo cáo.

## Kết quả hiện hành

- **37 inventory unit:** 24 `completed`, 13 `partial`. Completed chỉ đóng các câu hỏi hữu hạn được ghi, không phải chứng nhận route an toàn toàn diện. Inventory tăng từ 29 lên 37 gồm bảy PATCH unit và một OPTIONS unit; không phải tám feature nghiệp vụ mới.
- **9 nhóm native ZAP alert:** 1 Medium, 4 Low, 4 Informational; **1.977 instances**. CSP là nhóm Medium. Instance là lần xuất hiện, không phải số lỗ hổng độc lập. Header hardening còn là đề xuất, chưa triển khai trong hai bản sửa được giao.
- **111 ZAP-derived observations:** 101 matched, 7 inconclusive, 3 suspected-violation. Matched không có nghĩa một tiêu chí bảo mật đã pass; ba suspected lịch sử vẫn được giữ, kết quả bản sửa nằm riêng trong `currentRetest`.
- **50 tiêu chí:** 19 partial, 25 not-operated, 6 applicability-reviewed. BE anonymous, BE authenticated, BOLA và FE đều chưa hoàn tất toàn scope. Không quy đổi 24/37 thành phần trăm an toàn.
- **Giới hạn kiến trúc đã quan sát:** khi adapter không sẵn sàng, END/LEFT vẫn commit nhưng media tiếp tục tăng trong cửa sổ 12 giây. Recording tăng từ 47.345 lên 182.492 byte trong khoảng 2,2–12,9 giây sau END dù public state STOPPED. Sau recovery, mẫu đầu thấy transport/binding bằng 0 là khoảng 56,4 giây; đó không phải SLA hay nguyên nhân đã chứng minh.

## Vì sao mất nhiều thời gian và có cảm giác lặp?

### 1. Chưa tách đích kết thúc của từng loại nhiệm vụ

Kiểm thử động, sửa skill, chẩn đoán môi trường, sửa sản phẩm, retest và đánh giá đủ catalog đang xen kẽ. Sau mỗi việc có thể có kết quả tốt nhưng final lại quay về “cả bốn track partial”. Câu này đúng về coverage tổng thể nhưng không cho biết nhiệm vụ nào đã xong. Phần `scopeDisposition.workstreams` mới nhất đã bắt đầu sửa vấn đề này.

**Ảnh hưởng:** người dùng tiếp tục ra lệnh mà không biết đang tiếp tục assessment cũ hay mở nhiệm vụ remediation/design mới. Việc audit không cho phép tự giảm scope gốc hoặc tuyên bố toàn assessment complete.

### 2. Checkpoint và resume tạo overhead thực

Review ngày 01/11 ghi nhận 13/13 lượt thực thi được đọc đều đề nghị chat mới, nhiều lý do chỉ là đổi fixture/vector. RUN hiện có **20 operation isolated-runtime-resume** và **21 operation native-session-retention**. Mỗi operation không nhất thiết tương ứng một load/save thành công, nhưng đủ cho thấy phục hồi/lưu trạng thái là công việc đáng kể. Snapshot lớn, disk gate và client timeout làm tăng chi phí.

Đây không phải bằng chứng mọi checkpoint đều sai: đã có thiếu đĩa thực, và prompt chuyển chat gần đây có cả yêu cầu trực tiếp từ người dùng. Lượt mới nhất không đòi chat mới.

### 3. Lỗi điều phối/fixture làm giảm phần test tới đúng mục tiêu

Có rate-blocked START, body cũ, version sai, reader trước publisher readiness, dùng actor đã LEFT để đọc và kỳ vọng 200. Một số lỗi đã sửa; việc giữ coverage thiếu là đúng. Nhưng allocation tiếp theo phụ thuộc cùng readiness mà chưa chẩn đoán đủ làm thời gian tăng.

### 4. Trạng thái cũ và mới cùng nằm trong continuation

`continuation.capabilityLimits` vẫn chứa câu WHEP DELETE “inconclusive”, revocation policy “not established”, và readiness “3 consecutive ready then fourth FAILED”, trong khi cùng RUN đã có `assessmentPolicyDecisions`, ba suspected observations, `currentRetest` và readiness mới thành công. Các đoạn khác có giải thích supersede, nhưng các câu cũ chưa được đánh dấu thời điểm hiệu lực ngay tại chỗ.

**Đây là rủi ro đọc nhầm trạng thái có căn cứ từ file**, không phải bằng chứng mọi lượt đã thực sự replay. Lượt sau phải tổng hợp nhiều lớp lịch sử để biết kết luận nào còn hiệu lực. Nên phân biệt trạng thái hiện hành với giới hạn lịch sử, giữ nguyên raw/results; không cần thêm schema hoặc file bàn giao mới.

### 5. Đang dùng completion toàn catalog để đánh giá một phương pháp hẹp hơn

SBOM, crypto/key implementation, source-wide parameterization và governance log không thể được kết luận chỉ bằng ZAP. Mặt khác, không phải tất cả 25 not-operated đều ngoài ZAP: token rotation, tenant contract, policy và phạm vi abuse còn có dependency riêng. Không được gộp chúng thành N/A hoặc coi toàn bộ là backlog scan ngay lập tức.

## Đường kết thúc hữu hạn

**Đợt kiểm thử đã đủ dữ liệu để bàn giao findings và quyết định khắc phục; toàn phạm vi chưa được kiểm chứng đầy đủ.** Không mở thêm ma trận tương tự chỉ để tăng số request hoặc giảm số partial.

1. Giữ riêng kết luận: hai bản sửa được giao đã triển khai và retest hữu hạn; đối soát hiện hành đã hoàn tất; broad assessment vẫn partial. Đây là trạng thái bàn giao hợp lệ với giới hạn rõ, không phải đổi partial thành pass.
2. Chuyển giới hạn cutoff sang **một nhiệm vụ thiết kế/khắc phục cụ thể** nếu được giao: thời gian tối đa sau LEFT/END/STOPPED, hành vi khi không gia hạn được quyền, vị trí cưỡng chế không phụ thuộc adapter đang lỗi, và kiểm tra tính khả thi của provider. Renewable authorization deadline chỉ là phương án đề xuất, chưa được xác minh là provider hỗ trợ.
3. Nếu ưu tiên nhân quả 56,4 giây, chỉ mở trace hẹp theo fixture; không cần giải thích mọi failure lịch sử mới được bàn giao các kết luận đã đủ bằng chứng.
4. Giữ các việc header hardening và assurance ngoài ZAP thành những đầu việc có chủ đích/phương pháp riêng. Không tự giao thêm source/SCA/log/DoS hoặc tự chấp nhận residual risk.
5. Chỉ quay lại traffic cho khoảng thiếu có câu hỏi cụ thể, prerequisite thay đổi và kết quả mới có thể thay đổi quyết định. Pending/unknown phải được đối soát trước retry; không replay phần đã đạt.

Không cần một đợt viết lại skill hoặc full regression nữa để trả lời “đã làm gì”. Cải thiện cần ưu tiên là áp dụng đường đóng việc trên và làm rõ current-vs-historical readback. Hiệu quả hành vi của bản skill rút gọn chưa thể suy ra từ số test pass.

## Cơ sở và giới hạn audit này

Đọc trực tiếp skill, references completion/recovery/validation/knowledge và ba báo cáo JSON hiện hành. Đọc trực tiếp bốn lượt của chat `01a198d1-96cb-73a2-a48b-1f8354c4cc5d`, năm lượt gần nhất của `01a19858-aa35-7023-a159-48c4cb712235`, và lượt status gần nhất của `01a197e8-f3b2-7261-8a74-27bd52d31ddb`. Phần command history được công cụ trả về nhưng audit chỉ đối chiếu có chọn lọc; không kiểm chứng lại từng HTTP exchange. Hai review có sẵn ngày 01/11 và 02/11 là nguồn lịch sử thứ cấp cho giai đoạn trước, không tuyên bố đọc lại toàn bộ các chat cũ.

Kiểm tra offline lần này: ba report cùng generation; không trùng 4.253 operation ID hoặc 120 finding ID; không có dangling `ALERTS.operationIds`/`SCOPE_ALERTS.findingIds` trong các trường đã kiểm tra; native instances và observation outcomes khớp summary. Đây là kiểm tra cấu trúc/số liệu, không chứng minh tính đầy đủ/đúng nghĩa của từng mapping. 4.253 operation records bao gồm hỗ trợ, readback, traffic và orchestration; không phải số test bảo mật độc lập.

Kết quả regression 935 tests và việc sửa cleanup-test path là lịch sử trong audit cũ, **không phải test chạy lại lần này**. Audit này không khởi động scanner, gửi traffic, sửa skill/helper/product, thay report, commit/push hoặc xác minh live runtime. Trạng thái scanner đóng/pending0 được dẫn từ report hiện hành, không được đo trực tiếp.

Nguồn chính: [RUN](../../assessment-results/100ms-fresh-20261101/RUN.json), [ALERTS](../../assessment-results/100ms-fresh-20261101/ALERTS.json), [SCOPE_ALERTS](../../assessment-results/100ms-fresh-20261101/SCOPE_ALERTS.json), [review 01/11](zap-workflow-after-skill-20261101.md), [audit và sửa skill 02/11](zap-skill-operational-audit-20261102.md).

Audit hoàn tất. Không cần chat mới; bước thiết kế/triển khai tiếp theo là nhiệm vụ khác, không được tự khởi chạy trong lượt audit.

## Bản sửa hướng dẫn sau khi người dùng phê duyệt

Ngày 02/11/2026, người dùng phê duyệt bản sửa nhỏ về completion và continuation. Thay đổi chỉ nằm trong năm file hướng dẫn của skill repo-local; không chỉnh code/helper/runner, schema, metadata invocation hoặc báo cáo assessment:

- `SKILL.md`: trỏ đến quy tắc đóng nhiệm vụ; phân biệt hoàn thành assessment, kết luận bảo mật và remediation. Root tăng từ 1.190 lên 1.220 từ theo whitespace.
- `references/assessment-scope-and-completion.md`: sở hữu quy tắc chung. Ngay intake xác định câu hỏi/quan sát đủ để đóng từ scope đã giao; giữ yêu cầu ngoài khả năng ZAP là chưa đánh giá. Đủ kết quả thì kết thúc, còn việc hữu ích khả thi thì làm tiếp, dependency thật thì bàn giao partial. Vi phạm đã đủ bằng chứng không buộc phải sửa sản phẩm hoặc giải thích mọi failure lịch sử trước khi đóng câu hỏi.
- `references/operation-dispatch.md`: nối quyết định intake và kết thúc về quy tắc chung; bỏ cách diễn đạt có thể khiến dừng vì dependency bị hiểu thành complete.
- `references/retention-stop-and-recovery.md`: phân biệt dừng công việc với hoàn thành scope; cập nhật kết luận hiện hành khi có policy/build/readiness/retest thay thế, giữ rõ ngữ cảnh lịch sử, raw và coverage thiếu cũ. Không chọn kết luận chỉ vì câu văn mới hơn.
- `references/product-assessment-handoff.md`: báo riêng assessment/security/remediation; user stop hoặc hết lựa chọn hợp lệ không làm scope thiếu thành complete.

### Đối chiếu quyết định offline

Đặt kỳ vọng trước khi đọc lại dữ liệu; đây là walkthrough thủ công, không phải test tự động hành vi agent:

1. **Đủ câu hỏi, có vi phạm:** phải kết thúc assessment được giao và giữ finding, không tự mở sửa lỗi. Đối chiếu quy tắc mới với tình huống cutoff đã quan sát; phần thiết kế/khắc phục riêng vẫn chưa được giao.
2. **Xong đối soát nhưng còn scope:** RUN hiện có `objectiveOutcome=met-for-scope-reconciliation` cùng `taskCompletion=partial` và bốn track partial. Bản sửa giữ hai kết luận này độc lập.
3. **Recording mới thành công, failure cũ còn:** RUN có readiness mới cùng gap generation FAILED lịch sử. Hướng dẫn mới bỏ blocker readiness tổng quát khi đã bị kết quả mới thay thế, nhưng không cộng coverage hồi tố hoặc replay payload cũ.
4. **Policy thay đổi cách diễn giải:** câu WHEP DELETE inconclusive cũ còn trong capabilityLimits; policy creator-only hiện hành và ba suspected observations có `currentRetest`. Bản sửa yêu cầu cập nhật phần summary/limitation đang có hiệu lực, giữ finding/raw cũ và ràng buộc đúng build.
5. **Rate/quota/scope guard chặn:** RUN giữ bốn nhóm blocker cụ thể; hướng dẫn mới không biến việc báo cáo chúng thành completion, N/A hoặc quyền bypass/replay.
6. **Còn block khả thi:** review lịch sử ghi nhận cùng chat vẫn thực hiện thêm UI/lifecycle sau đề nghị đổi chat. Quy tắc tiếp tục khi còn kiến thức dùng được được giữ; đổi fixture không trở thành lý do dừng.
7. **Người dùng yêu cầu dừng:** tình huống kiểm soát giả định; dừng đúng yêu cầu, giữ scope thiếu partial. Không nhầm với trường hợp đã trả lời đủ mọi câu hỏi.
8. **Build khác hoặc mutation chưa rõ:** tình huống kiểm soát giả định; vẫn đối soát binding/ACK/state trước reuse/retry. Không dùng current summary hoặc kết quả fixture mới để thay bằng chứng của thao tác cũ.

Các tình huống có đường xử lý nhất quán trong hướng dẫn mới. Chúng không chứng minh agent tương lai sẽ tuân thủ hoặc giảm số lần người dùng nhắc tiếp tục; cần quan sát lượt vận hành được giao tiếp theo, không mở scan riêng chỉ để thử bản sửa.

### Kiểm tra đã chạy

- `skill-creator/scripts/quick_validate.py` bằng môi trường Python audit có sẵn: **Skill is valid**. Python mặc định thiếu PyYAML, nên không dùng nó cho validator và không cài dependency mới.
- Kiểm tra **79 liên kết Markdown cục bộ và anchor** trong năm file sửa: không thiếu file/anchor.
- `git diff --check`: đạt; review diff so với bản sao ngay trước lượt sửa để bảo toàn những thay đổi chưa commit có sẵn.
- Không chạy full regression hoặc product scan vì chỉ sửa hướng dẫn. Không cài/đồng bộ bản skill cá nhân, commit/push hoặc chỉnh ba JSON hiện hành. Chưa thực hiện đối soát backlog assessment thành danh sách công việc cuối cùng; đó là công việc riêng được nêu trong audit.

Bản sửa được phê duyệt đã hoàn tất. Không cần chat mới; không tiếp tục chỉnh tài liệu nếu chưa có lỗi hành vi cụ thể mới.

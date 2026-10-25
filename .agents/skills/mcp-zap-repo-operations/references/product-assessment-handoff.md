# Bàn giao alerts và nhật ký thao tác

Đầu ra hiện hành là một folder ổn định chứa **ALERTS.json và RUN.json**. Không có folder/mục evidence, báo cáo chứng minh riêng hoặc bộ hash/manifest bắt buộc. Mục đích là giúp tester biết đã kiểm gì, kết quả nào và còn thiếu gì; không cấp approval hoặc chứng nhận an toàn.

## Phạm vi bàn giao và note JWT/session

Giữ scope user và [mục tiêu từng track](assessment-scope-and-completion.md#phạm-vi-backend-và-bola). DAST hai track BE cần ZAP thực thi thật; BOLA kiểm đủ role và phân biệt nguồn direct. Token login thành công không tự chứng minh đúng role; xác định account/role từ thông tin hợp lệ và kết quả protected phù hợp. Mất auth không tính là authenticated coverage. Không đưa token, password, cookie hoặc raw credential/config vào output.

Không bắt qualification/lifecycle/fixed product build hoặc gói kiểm chứng chặt để trả kết quả. Skill cho phép lưu credential/token cần thiết local private; chỉ thông báo, không xin lại. Phản ánh quyền retention vào contract của entry đã chọn. Giữ đúng gate thực tế của executor, không dùng contract báo cáo nhẹ để bypass chúng.

## 1. Giải vị trí product và xác định run

- Xác minh input là source, deployment hay URL; tự discovery trong quyền đã giao. Không suy production target từ code rồi quét.
- Tìm RUN cũ theo vị trí product và môi trường; dùng lại folder của cùng product/môi trường. Không lấy tên folder làm bằng chứng đó là cùng deployment.
- Ghi target, môi trường, thời gian và phiên bản/build khi biết; chưa biết thì nói chưa xác minh. Build mới không xóa kết quả lịch sử chưa retest.
- Source chưa có deployment vẫn có thể lập inventory; ghi chưa gửi traffic. Input hoặc binding mâu thuẫn chỉ hỏi phần thực sự thiếu và tiếp tục phần độc lập an toàn.
- Kết quả cũ có folder bằng chứng thì giữ nguyên tại chỗ. Lần mới chỉ cập nhật hai file dẫn xuất; không yêu cầu chuyển, đọc lại hết hoặc đóng gói dữ liệu cũ.

## Quy trình nhiều giai đoạn và chat

Chạy subset hữu hạn theo capability/quyền/tài nguyên, không đổi subset thành toàn scope. Sau mỗi giai đoạn ghi thao tác/kết quả/coverage trong RUN, cập nhật alerts, rồi tự tiếp tục ca đủ điều kiện. Cùng scanner chạy tuần tự nếu chưa xác định cách ly. Không tạo chat hoặc subagent tự động.

### Điểm bàn giao và tiếp tục

Kết thúc khi hoàn tất nhiệm vụ; user yêu cầu dừng; hoặc không còn cách tiếp tục hợp lệ sau chẩn đoán/khắc phục trong quyền, tài nguyên hiện có và giới hạn nhiệm vụ do PM xác định. Cap/deadline của allocation chỉ chia lượt, không tự là budget kết thúc nhiệm vụ. Ghi blocker thật, API/role bị ảnh hưởng, việc đã thử và điều kiện tiếp tục. Còn nhánh độc lập đủ điều kiện thì tiếp tục. Đủ hai file hoặc runner completed không tự là điểm dừng.

Nghiệm thu bằng câu hỏi: **Còn phần việc còn mở nào mà Agent chưa đưa tới một quyết định xử lý có căn cứ ?** Nếu có thì xử lý theo [quyết định phần còn mở](local-remediation-and-continuation.md#quyết-định-cho-phần-việc-còn-mở). Quyết định có căn cứ không thay execution: một next step còn thực hiện được trong scope phải được làm trước bàn giao. User chỉ giao giai đoạn hiện tại thì giữ ranh giới đó, không tự mở giai đoạn sau. Nói rõ lượt thực thi xong hay toàn nhiệm vụ xong, không dùng “workload hữu hạn” để thu hẹp nhiệm vụ.

### Prompt copy cho bước tiếp theo

Chỉ dùng khi thực sự cần chuyển tiếp:

> Tiếp tục assessment tại <folder kết quả>, đọc RUN.json và ALERTS.json. Giữ nguyên product/môi trường và scope đã giao, đối soát toàn inventory/role, xử lý phần còn mở theo thứ tự trong RUN. Kiểm trạng thái lần trước trước khi retry start/mutation; không chạy lại thao tác đã ACK chỉ vì checkpoint chưa cập nhật.

## 2. Chọn workload và thực thi trong phạm vi

Giữ inventory tất cả method–route/role thuộc track. Chọn kỹ thuật DAST theo input/rủi ro, baseline có nghĩa và mutation có fixture phù hợp; ghi phần chưa chạy với lý do, không bỏ khỏi nhiệm vụ vì recipe chưa hỗ trợ. BOLA giữ owner/non-owner và các role/state làm thay đổi quyền. Không bắt mọi tổ hợp input/rule/state vô hạn.

Ưu tiên operations repo gốc và collector sẵn có. Khắc phục lỗi cục bộ theo [vòng sửa và tiếp tục](local-remediation-and-continuation.md). Không tự làm fault/qualification campaign hoặc dựng proof mới chỉ để có bộ output chặt. Nếu entry code bắt proof/pin, chọn đường đã hỗ trợ phù hợp hoặc ghi dependency công cụ cụ thể; không gọi API tầng thấp để né gate và không coi đó là lỗi product.

### Triage alert theo kết quả

Đọc alert/report đã trả về: native severity/confidence, route/parameter, mô tả và phản hồi có sẵn. Nêu điều đã quan sát, nhận định tester và ảnh hưởng chưa xác nhận. Không cần lưu request/response hay chứng minh exploit riêng cho từng alert. Không gọi false positive chỉ vì HTTP200; giữ alert chưa kết luận cùng hạn chế. Tra [playbook](alert-triage.md) chỉ khi cần giải nghĩa sâu hơn.

## 3. Bộ bàn giao bắt buộc

Chỉ hai file trong folder kết quả:

- `ALERTS.json`: danh sách alerts/findings tổng hợp và summary.
- `RUN.json`: ngữ cảnh, thao tác/kết quả, toàn inventory/coverage, hạn chế và phần còn mở.

Các handoff legacy hiện còn tạo technical/evidence theo [runner mapping](runner-routing.md); để chúng ở working directory, không coi đó là bộ bàn giao cuối. Agent dùng `product_assessment.py scope report` hoặc `product_scope.compact_results` theo [vòng trách nhiệm](responsibility-loop.md), lấy reconciliation làm nguồn completion/notPerformed/nextSteps. Không viết composer dùng count journey, traffic boolean hoặc all(campaigns) để cấp completion. Không chạy thêm verifier chỉ để đổi format báo cáo. Không có mục evidence, evidenceStatus, proof/hash/manifest hay link bằng chứng bắt buộc trong báo cáo dẫn xuất. Không đặt tên schema/version mới chỉ để đổi báo cáo. Runner vẫn có thể sinh log, native reports hoặc trạng thái nội bộ theo implementation; để chúng ở vị trí làm việc do công cụ quản lý, không gom vào đầu ra cuối. Không xóa hoặc chỉnh raw cũ. Người dùng cần report native riêng thì cung cấp khi được yêu cầu, không tự tạo bộ bàn giao phụ.

Chỉ dùng reconciliation sau khi đã [kiểm ý nghĩa observations và giữ phần thiếu trong input đối soát](responsibility-loop.md#reconcile-và-chạy-bước-tiếp). Helper không xác minh thay caller các nhãn quan sát. Nếu phát hiện completion dẫn xuất sai, sửa inventory/observations và tổng hợp lại, ghi lý do sửa cùng phần còn mở; giữ request/result/finding gốc và phân biệt sửa kết luận với retest. Không chỉ sửa câu trả lời trong chat trong khi RUN vẫn đóng track.

### Danh sách alerts và findings

Giữ tên/mã rule, native severity/confidence, nguồn ZAP/direct, track, endpoint và mô tả cần hiểu kết quả. Có thể giữ native alert ID khi sẵn có; không buộc mỗi nhóm có pointer/reference/file/hash. Không dựng native alert cho direct BOLA hoặc nhánh chưa chạy. Nhận định/impact chưa xác nhận phải ghi rõ, không tự tạo verdict pass hoặc reviewer approval.

Gộp occurrence hợp lý, summary phân biệt số nhóm theo severity với instances. Cùng occurrence từ report/API hoặc retry không thành bug mới. Nếu không đủ dữ liệu dedup thì nói rõ cách đếm. Finding cũ chưa retest giữ nhận diện lịch sử/chưa xác minh lại, không tính là phát hiện mới.

### RUN: ngữ cảnh, thao tác và coverage/gaps

RUN là ghi nhận kết quả thực tế, không là contract mới của executor. Tái dùng field hiện có phù hợp; tối thiểu có:

1. Product/target/môi trường, scope/track, thời gian và trạng thái hoàn thành nhiệm vụ.
2. Các thao tác thực sự đã làm, mỗi thao tác có method–route hoặc phạm vi, actor/role khi áp dụng, kỹ thuật, kết quả/lỗi. Phân biệt discovery/import, seed/request mẫu, crawl, passive, active ZAP và direct BOLA; tách setup/login khỏi kiểm thử nghiệp vụ. Start/ACK chưa là terminal; đọc kết quả cũ không là scan mới.
3. Inventory/coverage đầy đủ: từng method–route thuộc scope, role áp dụng, đã kiểm gì, kết quả nào, chưa làm và lý do. Với câu hỏi input/nhánh cần phân biệt, ghi input/kỹ thuật, mục tiêu xử lý và kết quả đã đạt hoặc còn thiếu ngay trong coverage hiện có. Query không thay body/path, role này không đại diện role khác. Chưa chạy không ghi pass hoặc N/A.
4. Hạn chế ảnh hưởng kết luận, blocker thực tế, bước tiếp theo và trạng thái cleanup/retention khi liên quan. Không cần mục bằng chứng hoặc export log.

Giữ execution, kết quả bảo mật và mức hoàn tất phạm vi tách nghĩa. Nếu runner có trạng thái khác, chỉ diễn giải phần liên quan trung thực; không buộc chép toàn bộ các trường assurance nội bộ. BOLA matched theo policy suy từ source chưa chứng nhận policy đúng. Policy chưa rõ phải nói chưa xác nhận.

Nơi tiếp tục chính thức phải rõ trong RUN; checkpoint/journal riêng là dữ liệu làm việc theo [recovery](retention-stop-and-recovery.md). Tri thức dùng lại được lưu ở [kho tri thức](operational-knowledge.md), không gom credential/raw hoặc tạo thêm file bắt buộc trong bộ bàn giao.

### Tổng hợp và retry

Cập nhật RUN/ALERTS từ kết quả terminal mới nhất phù hợp từng API/role; giữ lịch sử lỗi ngắn khi giúp hiểu trạng thái. Không scan lại để sửa aggregation. Không cộng retry như coverage mới, không đổi verdict lịch sử. File kết quả không đòi bộ lineage, source archive hoặc portable package riêng.

## 4. Điều kiện kết thúc và trả kết quả

Đối soát [toàn phạm vi](assessment-scope-and-completion.md#đối-chiếu-kết-thúc). API/role hoặc câu hỏi input/kỹ thuật thuộc trách nhiệm còn chưa được xử lý thì nhiệm vụ partial/blocked, kể cả đã có alerts hoặc mọi endpoint đều có traffic. Khi đã thực hiện đủ nhưng chưa xác nhận exploit hoặc policy, nói rõ giới hạn kết luận, không tự kéo thành một chương trình qualification vô hạn.

### Response trong chat

Phản hồi cuối gồm đúng hai phần theo thứ tự, viết ngắn và khớp nội dung hai file:

1. **Vận hành:** các thao tác đã thực hiện, method–route/actor/role/kỹ thuật, kết quả và mức hoàn tất nhiệm vụ. Trả lời trực tiếp **đã hoàn thiện phạm vi nhiệm vụ của từng track được giao hay chưa**; phân biệt scan/lượt chạy kết thúc với toàn track hoàn tất. Giữ số nhóm alerts theo severity/nguồn tách số instances; inventory dài nằm trong RUN. Kèm link `ALERTS.json` và `RUN.json` tương ứng. Không đưa credential vào phản hồi hoặc gọi setup/passive/UI traffic là active DAST.
2. **Hạn chế:** nếu track chưa hoàn tất, nêu từng phần việc không thể thực hiện hoặc hoàn tất được tại điểm dừng hợp lệ, phạm vi bị ảnh hưởng và lý do kỹ thuật cụ thể tương ứng; ghi việc đã thử hoặc phương án đã đánh giá, vì sao chưa thể xử lý và điều kiện tiếp tục. Phân biệt chưa kiểm runtime với lỗi/blocker đã quan sát. Chưa xác định nguyên nhân thì nói chưa xác định; không suy đoán hoặc dùng một limitation để thay bước còn thực hiện được. Nếu không có hạn chế đã biết, nói rõ giới hạn của phần đã kiểm, không kết luận toàn product an toàn.

Không có phần Context hoặc mục/link folder bằng chứng. Chỉ nêu bước tiếp khi đã đến điểm dừng hợp lệ theo workflow hiện có. Tác vụ chỉ sửa skill vẫn dùng Vận hành/Hạn chế cho thay đổi, validation và giới hạn xác nhận; không giả như vừa scan product hoặc tạo hai file scan giả.

## Rà tình huống bàn giao

Một hoặc nhiều track đều dùng hai file. Zero alerts vẫn ghi traffic/coverage và phần chưa làm. Blocked trước traffic thì không có kết quả scan giả. Run cũ được đọc lại phải ghi đúng là dữ liệu lịch sử. Retry terminal cập nhật đúng subset, không xóa finding chưa retest. Shared scanner không được stop-all theo suy đoán. Thiếu account một role không làm cả role biến mất khỏi inventory BOLA.

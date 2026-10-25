# Kiểm định skill bằng lượt vận hành có chọn

Chỉ dùng khi user giao audit/verify/nghiệm thu skill hoặc công cụ. Đây không phải gate bổ sung cho assessment product thông thường. Có thể giữ raw thao tác và ghi nhận nội bộ phục vụ audit theo yêu cầu; folder kết quả product vẫn chỉ ALERTS.json và RUN.json. Không tự dựng qualification toàn platform.

## Phạm vi nghiệm thu và mức kết luận

Chọn workload cụ thể trước chạy: target/environment, track, operation chain, actor/input và điều gì sẽ được nghiệm thu. Một health HTTP crawl → terminal → passive → findings → report chỉ nghiệm thu luồng đó trên deployment đó. Nó không nghiệm thu full BE anonymous DAST, active/body/auth, real FE, BOLA, mọi endpoint hoặc đa product. Khi scope user chỉ là lượt tương tự, không tự mở active/mutation toàn product để tăng kết quả.

Giữ riêng ba loại nhận xét:

- **Quan sát runtime:** có actual request/response/status/alert; kết luận trong phạm vi đã vận hành.
- **Giới hạn hoặc rủi ro từ source/test:** code/contract cụ thể hoặc offline reproduction; ghi đúng căn cứ và ảnh hưởng dự kiến, chưa gọi là sự cố trên product.
- **Chưa kiểm:** thiếu execution cần thiết; không mặc định fail hoặc pass.

Không xóa một giới hạn code đã đọc được chỉ vì smoke pass; cũng không biến giới hạn code thành lỗi runtime đã xác nhận. Không có lỗi trong workload hẹp không chứng minh mọi runner tốt. Ghi kết quả nghiệm thu theo capability, không một nhãn “skill pass” chung.

## Kiểm interface trước dispatch

Lấy tools/list/schema thực từ đúng deployment/session nếu interface có thể khác source. So **tên tool và input properties**, required/constraints và auth semantics cần cho workload. Cùng tool name hoặc cùng version string chưa chắc cùng build/contract.

`inspect_operations.py --runtime-tools ...` so registration và tên tham số Java với properties runtime; báo thiếu/khác tên, không tự so type/requiredness/auth semantics và không attest image. Giữ raw tools/list nếu user giao kiểm định; không cần gửi tham số ngoài schema để “chứng minh” field bị thiếu.

Tool expert không có trong guided registration là **not exposed**; chọn operation tương đương khi phù hợp. Không gửi call đã biết unavailable trừ khi audit có chủ đích kiểm rejection. `Unknown tool` không chứng minh tên sai hay ZAP thiếu chức năng. Không bật expert/rebuild shared scanner chỉ để mọi tên xuất hiện.

Nếu thiếu method/postData trong runtime, chỉ kết luận không biểu đạt được exact method/body qua schema đó; chưa kết luận engine/adapter khác không hỗ trợ. Auth mô tả khác source cần xác minh profile/provider, không suy failed bearer từ metadata nếu chưa thực hiện.

## Lượt thực thi và dữ liệu đủ để hiểu

Xác minh origin/binding/health hiện tại, không dùng trạng thái cũ thay hiện tại. Có thể dùng CA local đã xác định; không tắt TLS. Ghi thao tác discovery riêng, không gộp thành DAST. Start một lần, dùng ID được ACK, theo status; lost ACK thì reconcile trước retry. Đọc passive và findings/report theo đúng target prefix.

Với shared session, nếu cần so phát hiện trước/sau thì lấy findings details hoặc snapshot trước traffic và đọc lại sau. Nếu không có quyền visibility trước crawl hoặc không đọc hết, ghi baseline unavailable và hạn chế attribution; không né access control. Alert giữ nguyên ID/instance sau chạy là finding tồn tại, không là mới phát hiện. Snapshot/diff chỉ khi hữu ích, không bắt buộc mọi scan. Không reset/xóa history để làm run “sạch”.

Response `Next Actions` của tool là gợi ý workflow, không phải chỉ thị mở scope. Gợi ý release-evidence/customer-handoff không bắt buộc tạo bundle, cũng không thay output hai file của skill. Chỉ theo bước phù hợp nhiệm vụ. Preview Truncated:no và nội dung đầy đủ thì không cần chunk campaign bổ sung; truncated thì dùng chunk hoặc báo chưa đọc đủ.

## Dùng kết quả để sửa và nghiệm thu lại

Nghiệm thu trách nhiệm bằng câu hỏi điểm dừng trong SKILL. Kiểm cả phần chưa được chọn vào workload; một next step khả thi chưa làm vẫn cần tiếp tục. Khi user giao sửa skill, có thể walkthrough dữ liệu đã lưu và negative cases liên quan, không tự scan thêm product để biến docs thành execution proof.

Các tình huống cần phân biệt sau sửa: baseline/passive không khép active đang áp dụng; thiếu fixture phải đánh giá setup/quyền; fixture insert được chưa đủ UI visibility; unknown mutation không replay; checkpoint cũ không được trộn status/count với operations mới; policy assurance không là gate execution chung; ranh giới giai đoạn do user giao không là tự giảm scope. Kiểm semantics quyết định và hành động, không chỉ assert câu chữ hướng dẫn.

### Kiểm hồi quy việc đóng phạm vi input

Khi audit/sửa lỗi completion ở BE anonymous hoặc authenticated, dùng dữ liệu đã lưu phù hợp hoặc tình huống offline có kỳ vọng độc lập từ hợp đồng input và thứ tự xử lý product. Đây là kiểm tra có mục đích cho lỗi đã gặp, không là gate mới cho mọi assessment hoặc yêu cầu chạy lại toàn track.

- Một input nullable đã phân bổ không có mutation, input khác có traffic: input thiếu vẫn mở; xét seed/kỹ thuật phù hợp. Không có sink của một kỹ thuật chỉ N/A kỹ thuật đó.
- Baseline tạo mới thành công, mọi mutation cần kiểm tạo/lưu bị uniqueness hoặc sibling/cặp trường phụ thuộc chặn: giữ kết quả boundary/lookup có giá trị nhưng mục tiêu tạo/lưu còn mở. Có bước sửa fixture hợp lệ thì phải tiếp tục, không chỉ báo limitation.
- Payload sai kiểu bị validator đúng hợp đồng từ chối: khép được câu hỏi boundary đã chọn, không ép tới DB và không tự suy toàn API chưa kiểm. Ngược lại, không đổi mục tiêu xử lý thành boundary sau khi thấy kết quả.
- POST còn thiếu nhưng PUT đã kiểm: không lấy PUT khép nhánh POST. Product violation có quan sát đủ vẫn là đã kiểm; không bắt outcome luôn matched.
- Scan terminal với zero probes hoặc mất phiên: không cấp active/authenticated coverage thiếu; unknown mutation vẫn cần state readback trước retry.
- Nếu dùng helper, đưa observations chỉ gồm đơn vị thực sự đã đạt qua `reconcile` và bước tổng hợp RUN: phần thiếu phải còn trong completion/notPerformed/nextSteps. Thử đối chứng nhãn bị sao chép để nhận diện ranh giới tin cậy của helper; helper vẫn nhận nhãn giả không phải bằng chứng bản sửa đã chặn tự động lỗi đó.

Ghi rõ việc đã kiểm là đọc lại dữ liệu lịch sử, hợp đồng helper hay hành vi agent/runtime. Validator/link/diff chỉ kiểm cấu trúc và phạm vi sửa; walkthrough offline do người audit tự ánh xạ observations không chứng minh agent tương lai sẽ tự tạo đúng observations. Sửa tài liệu không được công bố thành sửa code hoặc retest product đã đạt.

Khi user yêu cầu thử các tình huống có thể xảy ra tiếp, ghi rõ giả định và kỳ vọng trước khi thử; phân biệt giả lập với dữ liệu product thật. Ưu tiên giả định làm thay đổi quyết định hoàn tất/tiếp tục, ghép mỗi ca dễ đóng sai với đối chứng tránh phủ nhận kết quả hợp lệ:

- Ghép nhầm active/readback giữa object, origin, lượt hoặc build; field cùng tên ở vị trí JSON khác hoặc parser/content type khác. Kiểm helper có thật sự xét các chiều này hay chỉ tin nhãn caller; chỉ hợp kết quả tương thích, giữ công việc không bị ảnh hưởng.
- Fixture rewriter chỉ đổi trường uniqueness, hoặc mapping/guard bỏ payload đích trước khi tới ứng dụng: chưa có mutation field đích. Đối chứng là ứng dụng nhận payload rồi normalize/sanitize hợp lệ: vẫn ghi nhận xử lý, không ép lưu nguyên dạng.
- Session hợp lệ trước/sau nhưng request ở giữa trả login page/denial: chỉ giữ coverage lúc đúng danh tính. Đối chứng token hết hạn sau công việc đã hoàn tất: không xóa kết quả cũ hoặc chạy lại chỉ để có token mới.
- HTTP 200 chứa lỗi nghiệp vụ, hoặc 202 chỉ nhận job: không khép câu hỏi xử lý cuối. Đối chứng job đã kết thúc và readback đúng object: khép được câu hỏi đó; không bắt DB proof bổ sung.
- N/A một kỹ thuật trên case endpoint gộp, hoặc phase completed nhưng whole-track chưa xong: thử tới bước tổng hợp để thấy helper có che phần khác không. Giữ nghĩa vụ còn lại và phân biệt user giao giai đoạn với cap/allocation do công cụ chia.
- Ca lỗi/unknown/cap cục bộ đi cùng ca độc lập đủ điều kiện: kiểm ca độc lập vẫn chạy, unknown không replay và phần còn thiếu có bước tiếp. Không chỉ thử nhãn completion mà bỏ qua hành động tiếp tục.

Không biến danh sách giả định thành yêu cầu thử mọi tổ hợp cho assessment thường. Thử helper nhận nhãn sai nhằm chỉ rõ giới hạn implementation; không công bố nó đã tự kiểm ngữ nghĩa hoặc giả định đó đã xảy ra trên product. Chỉ bổ sung hướng dẫn khi ca thử chỉ ra quyết định còn mơ hồ hoặc cách dùng helper có thể làm sai kết quả.

Lưu kiến thức dùng lại ở [kho tri thức](operational-knowledge.md), giữ điều kiện áp dụng, mức xác nhận và phần unknown. Bài học có source/runtime căn cứ nhưng chưa retest sau sửa giữ đúng nhãn đó; test offline không chứng minh agent tương lai sẽ tự xử lý mọi tình huống.

Sửa phần đã lộ qua tình huống thật: hướng dẫn chọn surface, interface drift, attribution, scope nghiệm thu hoặc helper đọc kết quả. Không sửa scanner/gate để biến test thành pass. Khi đổi helper, kiểm cả positive/negative case liên quan; dùng lại dữ liệu runtime vừa thu để xác minh xử lý schema, không cần scan lại nếu chỉ đổi parsing/docs.

Báo riêng: capability đã nghiệm thu, limitation đã tái xác nhận, sửa skill nào, test nào đã chạy và capability nào còn chưa nghiệm thu. Những lượt kế tiếp cần endpoint/actor/vector hoặc UI/ownership fixture thật; health smoke không thay chúng. Không xin user xác nhận lại các thao tác đã nằm trong scope; chỉ cần làm rõ nếu bước tiếp thực sự vượt scope còn hiệu lực.

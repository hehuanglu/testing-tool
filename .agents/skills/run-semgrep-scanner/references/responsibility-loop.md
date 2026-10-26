# Vòng trách nhiệm và xử lý phần còn mở

Mỗi inventory/câu hỏi đi qua **applicability → chọn kỹ thuật → thực hiện → đọc kết quả → đối chiếu kỳ vọng → quyết định tiếp → thực hiện quyết định khả thi**. Lượt hữu hạn chỉ chia công việc; scope không co lại theo rules/targets đã chọn.

## Chẩn đoán theo dấu hiệu

- **CLI/settings lỗi:** command không chạy/không ghi output. Kiểm binary, version/help, path/quyền và settings riêng; dùng cách gọi local có thật, sửa config tạm trong quyền. Tiếp tục đọc source và các câu hỏi không phụ thuộc CLI. Dừng nhánh tool nếu binary/capability/quyền còn thiếu sau chẩn đoán, ghi thao tác đã thử; không tự cài từ mạng.
- **Rule parse/schema:** invalid rule hoặc ngôn ngữ không nhận. Đọc lỗi và rule, kiểm local parser/core/help; sửa custom rule tối thiểu, fixture rồi chạy lại phần chịu ảnh hưởng. Phần rules hợp lệ/manual tiếp tục; rule hỏng còn mở nếu không thể sửa trong quyền. Không loại rule âm thầm để báo pass.
- **Targets/ignore/path filters:** empty target hoặc expected files vắng. So cwd/roots, extensions/language, rule paths, gitignore/semgrepignore/nosemgrep, size/binary. Lượt hẹp/config tạm có mapping hoặc manual review; không sửa product để lọt filter. Tiếp tục targets hợp lệ, giữ source thiếu mở; dừng nhánh khi source không được cung cấp/không đọc được hoặc capability thật thiếu.
- **Timeout/tài nguyên:** đọc timeout/error thực và phần đã chạy. Chia source/rules, chọn jobs/timeout theo tài nguyên quan sát; tạo lượt mới, giữ raw cũ. Phần độc lập tiếp tục. Không unlimited/retry vô hạn; dừng khi không còn thay đổi hợp lý trong quyền/tài nguyên và nêu phần chưa được phân tích.
- **Abstraction/framework mismatch:** zero matches dù inventory có wrapper/sink. Đọc wrapper/callers, tìm rules repo/local, custom rule có fixtures khi hữu ích, manual call-path phần khả thi. Không suy CE xuyên file hoặc N/A từ thiếu matcher. Tiếp tục surface khác; chỉ giữ blocked/open phần còn thiếu capability/source thực sự.
- **Thiếu policy:** expectation không xác nhận. Tìm spec/config/tài liệu trong scope, phân biệt source hypothesis, hỏi đúng điều ảnh hưởng kết luận khi không thể tìm. Vẫn scan/read implementation độc lập; không gán threshold heuristic thành violation, không gọi false positive. Chỉ block câu hỏi phụ thuộc policy chưa có; static facts vẫn ghi được.
- **Source thay đổi:** revision/dirty/diff khác hoặc control sửa giữa lượt. Ghi source state mới, đối chiếu phần ảnh hưởng, đọc/chạy lại phần cần thiết. Các phần không đổi tiếp tục nếu đã đánh giá tương thích. Nếu không thể xác định source hiện hành, giữ nhận định có giới hạn thời điểm, không trộn thành một kết quả cố định.
- **Output thiếu/hỏng:** process xong nhưng JSON/log truncated/không đọc được. Kiểm process và output thuộc lượt nào, đọc phần còn lại hoặc parse local; chạy lại read-only bằng lượt mới khi cần. Giữ findings phần đọc được và counts chưa biết null; tiếp tục manual/phần độc lập. Nếu không khôi phục được và không thể chạy lại, round partial/blocked theo phần có nghĩa, không gọi zero.

## Quyết định phải dẫn tới hành động

Với câu hỏi phụ thuộc policy, ghi trong `result` ba phần: `source_fact` (đã thấy gì, mức source đã trả lời), `policy_dependency` (claim nào chưa kết luận được, cần policy cụ thể nào, authority/tài liệu dự kiến hoặc chưa biết), `remaining_source_steps` và `external_step` (phần còn làm được từ source so với dữ kiện ngoài). Tiếp tục source steps khả thi trước khi dừng. Chỉ giữ phụ thuộc mở nếu thực sự cần cho claim được giao; không đòi mọi security policy. Nhiệm vụ đánh giá quy trình chỉ cần ghi nhận dependency, không buộc user adjudicate policy để nhận báo cáo. Round completed có thể đi cùng track partial vì claim còn phụ thuộc, phải giải thích riêng.

Ghi phần ảnh hưởng, quan sát, phương án đã thử/đánh giá, bước chọn và kết quả. `next_step` chưa đủ xử lý nếu vẫn làm được trong scope. Còn dữ kiện/điều kiện mới hợp lý thì làm tiếp; khi điều kiện không đổi thì không retry. Không bắt đủ số attempts hoặc proof campaign.

Có thể resolved bằng manual review đủ căn cứ cho nhiệm vụ SAST, ghi thao tác/source/evidence rõ; Semgrep chưa làm được vẫn không được nhận coverage. Nếu user yêu cầu một scan cụ thể, phản ánh riêng phần chưa thực thi đó. Missing rule không là N/A; N/A cần căn cứ feature/scope. Ngoài scope khác không áp dụng.

## Reconcile và điểm dừng

Đọc ngược inventory → questions → rounds/manual reviews → findings/evidence và phần còn thiếu. Không để skipped/unsupported source mất khỏi mẫu số. `needs-review` còn cần triage thì câu hỏi chưa resolved; nhiệm vụ candidates-only có thể hoàn tất ở mức tìm candidates đã giao, ghi triage ngoài scope.

Chỉ dừng khi scope/triage đã xử lý, user dừng hoặc hết bước hợp lệ sau chẩn đoán trong quyền. Completed không đồng nghĩa zero issues; supported bug vẫn là câu hỏi đã trả lời. Exit 0, scan năm YAML hay JSON đủ fields không quyết định completion. Ghi [trạng thái hai chiều và handoff](reporting-and-completion.md).

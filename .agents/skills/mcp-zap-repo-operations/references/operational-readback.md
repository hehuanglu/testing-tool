# Câu hỏi kỹ thuật và reader đã kiểm

Đọc khi lập workload BE, viết adapter/composer, hoặc gặp zero probes, fixture conflict, readback bị ghi đè hay metadata mất nghĩa. Source dùng chung ở `zap-product-assessment/src/zap_assessment/`; mapping route/role/field/state của product vẫn ở adapter. Không dùng các helper dưới đây làm oracle ngữ nghĩa độc lập.

## Khép đúng câu hỏi đã chọn

Trước start, giữ câu hỏi, input có ý nghĩa, kỹ thuật/rule cần phân biệt và mức kết quả cần đọc. Không cần tích mọi rule × input. Một nhóm textual fields có thể cùng một câu hỏi reflection; numeric/enum có câu hỏi boundary riêng. Strength là độ lớn workload, alert threshold là điều kiện rule áp dụng/phát hiện; chọn theo mục tiêu và đọc lại cấu hình thực, không đồng nhất hai tham số.

`active_questions.assess_question(question, probes)` đối soát một câu hỏi, sau khi adapter đã đọc request/response thực:

- `question`: `id`, `ruleIds`, `minimumStage` là `boundary/processing/persistence`; `fields` tùy chọn cho nhóm input thực sự cần phân biệt. Có `basis` giải thích lựa chọn. Kỹ thuật N/A cần `disposition: not-applicable` và căn cứ sink/context; auth/fixture/capability thiếu không là N/A.
- `probes`: mỗi dòng có `ruleId`, `field` khi cần, `changed`, `application`, `identityValid`, `stage`, `resultRead`. Chỉ cấp những giá trị này từ predicate adapter đã kiểm: payload đích còn ở request tới app, phiên đúng khi request chạy, phản hồi thật đã đọc. Không lấy rule enabled, ACK start, guard denial hay mutation của field khác làm probe.
- `stage`: parser/validation có nghĩa cho `boundary`; state conflict do fixture đã dùng không cấp `processing`. ACK khớp có thể cấp `processing`; `persistence` cần đúng object/variant được đọc lại trước khi bị ghi đè, hoặc object riêng. Final snapshot không cấp persistence cho mọi variant trước đó.

Kết quả có `unit`, `evidenceUnits`, `status`, `missingFields` và số request. Thêm unit của từng câu hỏi đã chọn vào `requiredEvidence` trong inventory hiện có; chỉ hợp `evidenceUnits` helper thực sự trả vào observations rồi `reconcile`. SQLi có probe không khép câu hỏi XSS có 0 probe. Không chỉ gắn số rule vào metadata ngoài reconciliation. `open` phải dẫn tới chẩn đoán/repair/fixture/lượt tiếp trong quyền; đưa vào `notPerformed/nextSteps` nếu thực sự còn dependency tại điểm dừng hợp lệ.

Helper tin dữ kiện đã chuẩn hóa, không tự đọc HTTP hoặc xác nhận source policy. Adapter phải kiểm ngược dữ kiện; không chép requirements sang probes, không tự đổi mọi 400/404/409 thành cùng một loại quan sát. Boundary hợp lệ vẫn có giá trị, không bắt mọi payload phải được lưu. Khi cần xử lý sâu, giữ fixture sẵn sàng cho đúng mục tiêu đó; đọc state trước retry unknown mutation.

## Đọc ổn định và tổng hợp lại

- `result_readers.read_jsonl(path)`: tách record theo LF; U+2028/U+2029 trong string không tách record. Outer record hỏng báo đúng dòng; HTTP body malformed nằm trong string hợp lệ vẫn được giữ cho ca parser. Không bỏ âm thầm record hỏng để tiếp tục completion.
- `result_readers.collect_alerts(fetch, total, page_size=100)`: đọc native alert IDs đủ count; hỗ trợ boundary overlap trùng nội dung, chặn page không tiến, ID đổi nội dung hoặc thiếu count. Advance theo số dòng thực nhận, không cố định `+1` theo một runtime. Dừng producers, chờ passive và kiểm native total không đổi trước/sau đọc. Report representative samples không là toàn instances.
- `transport.Scanner(..., chunk_size=100000).chunk`: chọn chunk trong giới hạn schema đang công bố, giữ cap byte/resource của caller. Dùng `evidence.collect_report/read_report` cho EOF, offset code points, artifact ổn định và resume pages đã lưu. Lỗi reader không đòi scan lại.
- `product_checks.check_pages(..., terminal=True)`: terminal là một trang rỗng đã quan sát. Với total 0, page 0 đã là terminal; với collection có dữ liệu, cần đủ data pages và terminal sau đó. Owner, total, thứ tự, missing/duplicate IDs vẫn được kiểm.

## ID, secret và hai file kết quả

Tách ID `baseline-*`, `campaign-*`, request thật; giữ liên kết case. `operationIds` phải trỏ nguyên văn ID thao tác. Group pagination giữ nhãn nhóm riêng và danh sách request con thật, không giả prefix là một operation.

`product_scope.compact_results(..., secrets=...)` che sensitive fields, auth assignments/JWT và các giá trị secret thực caller biết; `clean` không được hiểu suffix `Token:CUSTOMER` hay từ “password validation” là credential. Kiểm ID unique và references resolve **sau** compact/redaction; metadata có secret thật vẫn phải che và collision phải được xử lý, không bỏ bảo vệ trên mọi ID.

Mặc định xuất vào folder mới. Chỉ dùng `overwrite=True` khi user đã yêu cầu ghi đè cặp kết quả; kiểm destination chỉ có `RUN.json/ALERTS.json`, chuẩn bị đủ hai bản trước replace. Không sửa raw/journal/pins hoặc report audit lịch sử để hợp thức hóa lượt mới. Rerender từ dữ liệu đã có không được ghi thành retest mới.

Dự toán fixture theo câu hỏi và số request dự kiến, rồi đối chiếu số object thực. Reuse actor/fixture khi vẫn đúng quota/state; không cache response attack hoặc đổi mutation tạo mới thành duplicate baseline để giảm số account. Không có API cleanup thì ghi retention đúng quyền; một ngưỡng object tùy tiện không là tiêu chí pass.

Các regression tập trung: `tests/test_operational_readback.py`; các kiểm scope/continuation cũ vẫn ở `tests/test_pm_scope.py`. Unit tests kiểm cơ chế; kết quả runtime từng product ở hai file đã được chỉ định, không nâng test offline thành nghiệm thu mọi track.

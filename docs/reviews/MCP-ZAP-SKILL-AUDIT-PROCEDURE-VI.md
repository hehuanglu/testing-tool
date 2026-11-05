# Quy trình audit toàn bộ mcp-zap-repo-operations

## Mục tiêu và giới hạn

Trả lời ba câu hỏi: hướng dẫn có thừa hoặc khó hiểu không; hướng dẫn có liên kết đúng với runner/helper/schema/test không; workflow có thống nhất từ đầu vào đến hoàn thành và bàn giao không.

Đây là quy trình audit skill, không phải một assessment sản phẩm. Audit mặc định đọc source và kiểm tra offline. Không tự chạy scanner, đăng nhập sản phẩm, tạo fixture thật, đồng bộ bản cài cá nhân hoặc xuất Google Sheets. Runtime qualification chỉ là phần riêng khi được giao. Báo cáo audit phải phân biệt lỗi đã xác nhận, rủi ro cần kiểm chứng và khả năng chưa kiểm tra.

## 1. Chốt baseline và lập danh mục toàn bộ skill

- Ghi đường dẫn skill, thời điểm, HEAD, trạng thái tracked/untracked và digest từng file được audit. HEAD không đại diện đầy đủ cho workspace có thay đổi chưa commit.
- Lập manifest đệ quy, bao gồm file ẩn, `SKILL.md`, `agents/`, toàn bộ `references/`, `assets/`, `scripts/`, `lib/`, source, schema, profile, example, test, tài liệu lịch sử, provenance và entrypoint CI được đóng gói.
- Chỉ loại cache, bytecode hoặc dữ liệu sinh ra sau khi ghi rõ lý do. Mọi file còn lại có trạng thái: chưa đọc, đã đọc, đã đối chiếu; file nhị phân cần cách kiểm tra phù hợp.
- Phân loại tài liệu hiện hành, tài liệu kỹ thuật dùng lại và lịch sử/legacy. Không coi legacy là lỗi chỉ vì dùng thuật ngữ cũ; kiểm tra xem đường dẫn hiện hành có dẫn người dùng dùng nhầm nó không.

Đầu ra: manifest và baseline tái lập được. Không tuyên bố “audit toàn bộ” nếu còn file chưa được xử lý hoặc bỏ qua không giải thích.

## 2. Lập bản đồ quy định và nguồn có thẩm quyền

Đọc `SKILL.md`, `agents/openai.yaml`, `assessment-policy.md`, `criteria-driven-workflow.md`, rồi lần theo tất cả tham chiếu. Lập sổ quy định theo chủ đề:

- Đầu vào, phạm vi discovery, hai approval gate và content binding.
- Chọn câu hỏi/case/work unit; quyền điều chỉnh adapter, fixture và executor.
- Intent, ACK, readback, unknown effects, tài nguyên và phục hồi.
- Evidence, applicability, verdict, completion và delivery.
- Delegation, secrets, quyền ghi canonical state và giới hạn thao tác.

Mỗi quy định ghi nguồn chính, các chỗ nhắc lại, phạm vi áp dụng và nơi triển khai. Với từng chỗ lặp, đánh giá: cần giữ tại điểm thao tác; có thể thay bằng liên kết; hoặc tạo khác biệt nghĩa. Không xóa lặp máy móc khi nó bảo vệ một ranh giới quan trọng.

## 3. Audit câu chữ và khả năng thực hiện

Đọc từng hướng dẫn theo câu hỏi: ai làm, khi nào, đọc/ghi gì, cần điều kiện nào, làm xong nhận biết bằng gì, thất bại thì tiếp tục thế nào?

- Tìm thuật ngữ chưa định nghĩa hoặc dùng khác nghĩa: plan, allocation, pin, approval, observed, completed, delivery.
- Tìm điều kiện chung chung như “compatible”, “sufficient”, “appropriate”, “when needed” mà không có nguồn tiêu chí hoặc người chịu trách nhiệm quyết định.
- Tìm mệnh lệnh trái nhau, ngoại lệ không có ranh giới, tham chiếu vòng và kiến thức bắt buộc nhưng chỉ được ghi là tùy chọn.
- Kiểm tra ví dụ, câu lệnh, đường dẫn, anchor và tên field; phát hiện ví dụ có thể bị hiểu là mặc định cho mọi sản phẩm.
- Phân biệt yêu cầu cứng, mặc định và gợi ý. Không biến quyết định chuyên môn của coordinator thành một gate mới.

Mỗi nhận xét cần vị trí cụ thể, cách hiểu có thể xảy ra, hậu quả và đề xuất diễn đạt. Độ dài hoặc số lần xuất hiện chỉ là tín hiệu, không tự chứng minh mô tả thừa.

## 4. Đối chiếu mô tả với triển khai theo cả hai chiều

Với mỗi runner/helper được nhắc tới, lần theo chuỗi:

`hướng dẫn → entrypoint → parser/schema → compiler/admission → executor → journal/readback → reconciliation/report → cleanup/recovery → test`

Ghi rõ đường dẫn, symbol và bằng chứng tại từng chặng. Đối chiếu tên/flag, kiểu dữ liệu, requiredness, default, phiên bản, môi trường, auth, method/body/protocol, tác động, giới hạn và output thực tế.

Sau đó đi ngược từ toàn bộ CLI, runner, helper và test: thành phần nào còn dùng nhưng chưa được hướng dẫn; thành phần nào chỉ là lịch sử; có wrapper nào gọi nhánh khác với mô tả; schema có được code thực sự dùng hay chỉ tồn tại trong thư mục?

Ưu tiên kiểm tra các ranh giới dễ sai:

- Workflow v2 và technical runner/legacy state; không tự chuyển status cũ thành verdict mới.
- Native operation và runner; source support, offline check, lịch sử runtime và deployment hiện tại là các mức bằng chứng khác nhau.
- Authentication của client→MCP và ZAP→target; token ở seed không tự chứng minh cả scan authenticated.
- Helper kiểm tra nhãn/cấu trúc so với kiểm tra nội dung evidence; callback do coordinator cung cấp so với adapter tự động có sẵn.
- Report nội bộ RUN/ALERTS/SCOPE_ALERTS so với một bảng Google Sheets giao người dùng.
- Ví dụ synthetic hoặc adapter có tên sản phẩm so với khả năng hỗ trợ sản phẩm bất kỳ.

Đầu ra: bảng truy vết hai chiều. Mỗi mắt xích ghi “khớp”, “lệch”, “thiếu” hoặc “chưa kiểm chứng”; sự tồn tại của file không đủ để ghi “khớp”.

## 5. Walkthrough workflow bằng tình huống độc lập

Viết kết quả mong đợi từ policy trước khi đọc kết quả helper/test. Với mỗi tình huống, kiểm tra chỉ dẫn, đường code thực tế và state/output sau chuyển bước:

1. Assessment mới: discovery cơ bản → duyệt criteria → lập plan → duyệt plan → execute. Không gộp hai gate.
2. Đã có approval đúng nội dung; sau đó thay fixture hoặc sửa reader trong phạm vi. Tái sử dụng approval phù hợp, giữ nguyên binding lịch sử và admission thật.
3. Thay nghĩa criterion, target hoặc allowed effects. Phải nhận diện thay đổi cần approval mới.
4. Một observation phục vụ hai criteria có oracle khác nhau. Không sao chép verdict hoặc nhân số alert.
5. Có violation nhưng còn sibling cases trong all_cases. Giữ violation, tiếp tục nghĩa vụ chưa xong.
6. Zero probes, mất auth, ACK/HTTP 202 nhưng chưa có semantic readback. Không tự đóng active/processing evidence.
7. Script thành công nhưng reader lỗi; mất ACK hoặc mutation chưa rõ kết quả. Đọc kết quả/state cũ trước khi cân nhắc hiệu ứng tiếp theo.
8. Một nhánh thiếu actor/fixture, nhánh độc lập còn chạy được. Tiếp tục phần hợp lệ; không đóng cả assessment.
9. Helper/adapter không hỗ trợ một primitive. Phân biệt preparation khả thi với giới hạn có cơ sở; không tự biến thành N/A.
10. Worker lỗi/stale hoặc tranh chấp tài nguyên. Giữ journal, kiểm tra hiệu ứng và ownership trước khi thay thế; coordinator giữ quyền kết luận.
11. Resume legacy và retest. Giữ raw/pin/history, xét compatibility trước khi dùng evidence cho v2.
12. Criteria đã đủ nhưng Drive chưa ghi/readback được. Tách assessment status và delivery status; không scan lại để sửa publishing.
13. Audit skill-only và yêu cầu stop rõ ràng. Không phát sinh traffic/report sản phẩm; checkpoint có state và next action cụ thể.

Mỗi tình huống âm cần một đối chứng hợp lệ: denial trả lời đúng boundary question; earlier evidence hợp lệ trước token expiry; readback đúng object/stage; mọi case đã xử lý dù có vulnerability. Tránh sửa chống false completion bằng cách khiến mọi thứ luôn pending.

## 6. Kiểm chứng offline có chọn lọc

- Kiểm tra liên kết, symbol, import, parser và schema trước; chỉ gọi `--help` sau khi xác nhận entrypoint không tạo hiệu ứng.
- Dùng Python 3.13 và dependencies theo `requirements.lock`, môi trường có sẵn phù hợp; đọc setup/test trước khi chạy.
- Chạy nhóm v2 workflow/integration/reporting/CLI boundary; bổ sung routing, discovery, readback, continuation, recovery, portability theo các mắt xích đã audit.
- Đọc test và assertion để biết chúng chứng minh điều gì; không lấy số test pass thay cho phân tích contract. Không thực thi mù toàn bộ script/campaign.
- Với vấn đề nghi ngờ, dùng fixture tạm/captured response đã sanitize và expected outcome độc lập. Không đổi source đang audit chỉ để tạo kết quả mong muốn.
- Lưu lệnh, môi trường, kết quả, skip/failure và giới hạn. Offline pass không chứng minh runtime, năng lực agent hoặc chất lượng semantic oracle.

Nếu thiếu môi trường, ghi phần chưa kiểm chứng và tác động đến kết luận; không hạ guard hoặc bịa bằng chứng runtime.

## 7. Tổng hợp findings và thứ tự xử lý

Mỗi finding có: ID, mức ảnh hưởng, nhóm vấn đề, nguồn/line/symbol, quy định liên quan, mô tả sai lệch, tình huống tái hiện, expected/actual, hậu quả, bằng chứng, đề xuất sửa và cách xác nhận sau sửa.

Ưu tiên theo hậu quả: sai authority/replay hoặc kết luận sai; workflow/runner không thể thực hiện đúng; thiếu liên kết/điều kiện; cuối cùng mới đến diễn đạt và trùng lặp. Gộp các biểu hiện cùng nguyên nhân, nhưng giữ đầy đủ vị trí bị ảnh hưởng. Câu hỏi chưa có bằng chứng không ghi thành bug xác nhận.

Gói bàn giao gồm manifest, bản đồ quy định, bảng truy vết, kết quả walkthrough/check và danh sách findings. Nêu riêng phần khớp đã kiểm chứng, giới hạn triển khai có chủ ý và phần chưa kiểm tra. Không đưa một nhãn “skill pass” chung để che các mức bằng chứng khác nhau.

## 8. Điều kiện kết thúc audit

- Mọi file trong manifest có disposition; mọi runner/helper/entrypoint có đối chiếu hai chiều hoặc lý do không áp dụng.
- Mọi quy định hiện hành đã kiểm tra với các nguồn liên quan; mâu thuẫn chưa giải quyết vẫn hiện rõ.
- Các đường đi chính, thất bại, resume và delivery đã được walkthrough, có bằng chứng và giới hạn cụ thể.
- Findings tách lỗi câu chữ, sai contract, sai workflow và thiếu kiểm chứng; mỗi đề xuất sửa có phép kiểm tra tương ứng.
- Baseline cuối không đổi ngoài dự kiến. Nếu skill đổi trong lúc audit, xác định file/mắt xích bị ảnh hưởng và kiểm tra lại phần đó.

Audit hoàn tất không đồng nghĩa mọi finding đã được sửa. Sau một đợt sửa được giao, đối chiếu lại các mắt xích bị tác động và chạy regression phù hợp; giữ nguyên baseline và kết quả audit ban đầu.

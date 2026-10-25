# Backend anonymous DAST

Điểm xuất phát nghiệp vụ và scope ở [track intents](track-intents.md); chọn operations/executor theo [dispatcher](operation-dispatch.md). Reference này bổ sung chi tiết của entry hiện có, không mở rộng nhiệm vụ hoặc bắt chạy qualification.

Đọc [multi-product](multi-product-backend.md) và [phạm vi](assessment-scope-and-completion.md). Mục tiêu là ZAP DAST thật toàn API public thuộc scope, không danh tính đăng nhập. Đầu ra [ALERTS/RUN](product-assessment-handoff.md), không có phần bằng chứng.

## Trách nhiệm trước chọn workload

Giữ mọi public method–route nghiệp vụ, login/register và endpoint public được discovery trong scope. Protected-denial là control riêng. Public auth cần phân biệt validation chặn sớm với thực sự xử lý credential; input ngoài trường fuzz vẫn hợp lệ cho nhánh cần kiểm. Không tự truyền tiếp token response vào anonymous traffic.

Chọn kỹ thuật theo input/rủi ro, không chỉ các rule wrapper mặc định. Giữ kỹ thuật/route chưa chạy với lý do; seed/passive-only không khép mục tiêu active. Thiếu query/body không tự N/A toàn active. Chia lượt trong caps và tự tiếp tục phần đủ điều kiện.

## Discovery và admission

Dùng source/spec/deployment đúng product, không report cũ để suy binding hoặc fixture. Xác minh origin, scope và quyền mutation/active. Common CLI và entry `scripts/be_anonymous_research.py` có contract khác; đọc help/source trước chọn. Legacy `product-run` có recipe cố định, không phải đường cho mọi product bằng cách đổi URL. Không tự chạy lockout/DoS hoặc mọi rule để tăng số lượng.

## Thực thi và recovery

Tái dùng MCP/native adapter được admit, `DockerRuntime`, Journal và report reader. Guided explicit method/body có giới hạn prepared auth/direct; anonymous adapter có đường riêng khi source xác nhận, không giả authSessionId để vượt gate. Theo dõi start/status/terminal và dừng đúng resource khi scope/auth/resource lỗi; không blind retry unknown start/POST.

Kiểm kết quả và trạng thái sau mutation phù hợp case để biết điều gì đã xảy ra. Không thêm một proof/hash/source archive campaign chỉ để bàn giao. Runner tự sinh dữ liệu gì thì giữ ở chỗ làm việc, báo cáo chỉ thao tác/kết quả/coverage và hạn chế. Đừng biến sự thiếu wire attribution thành lý do bỏ mọi ca đã có thể chạy hợp lệ.

## Commands

Từ package assessment, `.venv/bin/python scripts/be_anonymous_research.py --help` để xem entry thật; common path là `scripts/product_assessment.py`. Chỉ execute sau khi product/scope/entry đúng. `verify` của runner, nếu cần, không phải scan mới hoặc security pass; không chạy mặc định để tạo bộ bằng chứng bổ sung.

## Kết quả và tiếp tục

Ghi từng API/kỹ thuật đã chạy, response/alert/lỗi thực tế và phần chưa làm trong RUN; native alerts vào ALERTS với severity/confidence gốc. Không đòi JSON/HTML/hash/manifest riêng ở bộ đầu ra. Còn API public hoặc active phù hợp chưa chạy thì giữ partial và tiếp tục nhánh đủ điều kiện, không kết thúc chỉ vì đã có vài alerts.

# Backend authenticated DAST

Điểm xuất phát nghiệp vụ và scope ở [track intents](track-intents.md); chọn operations/executor theo [dispatcher](operation-dispatch.md). Reference này bổ sung chi tiết của entry hiện có, không mở rộng nhiệm vụ hoặc bắt chạy qualification.

Đọc [multi-product](multi-product-backend.md) và [mục tiêu authenticated DAST](authenticated-dast-goal.md). Mục tiêu là ZAP DAST thật toàn API protected thuộc scope, với đúng actor/role và theo dõi phiên. Đầu ra [ALERTS/RUN](product-assessment-handoff.md), không có phần bằng chứng.

## Trách nhiệm trước chọn workload

Giữ mọi protected method–route, input và role có hành vi khác biệt. Khảo sát account/role/fixture hợp lệ trong scope; thiếu role là mục chưa kiểm, không loại role hoặc lấy role hiện có đại diện. Không forge JWT/role hoặc sửa DB để tạo quyền. Ưu tiên nghiệp vụ lõi; danh sách rỗng/request mẫu không đại diện toàn nghiệp vụ.

## Chọn executor và capability

Profile `be-authenticated-research/1.0` có thể lưu credential/token trong raw native private. Skill đã cho phép local retention cần thiết: chỉ thông báo, ghi nhận vào input contract và không hỏi lại. Không tự bật experimental/queue hoặc đổi contract của deployment khác.

Dùng common CLI, MCP auth prepare/validate và authSessionId cho crawl/attack theo capability thực. Root method/postData không tự nghĩa wrapper admit mọi body/vector. Common GET/query, flat PUT/PATCH và path có điều kiện; POST create/add có thể còn dependency allocation/oracle. Đọc help/source, chọn đường hợp lệ sẵn có trước mở rộng runner; không dùng legacy adapter product khác làm fallback.

Những gate proof/pin trong code vẫn giữ, nhưng skill không thêm proof campaign, source archive, strict secret-safe qualification hay full checksum readback thành nhiệm vụ mặc định. Nếu thật sự bị gate chặn, chẩn đoán đúng phần công cụ, sửa tối thiểu trong scope hoặc nêu dependency cụ thể; không đổi thành product fail hay dùng direct request thay authenticated DAST.

## Thực thi phần đã chọn

Xác minh target, actor/role và input/fixture; chạy ZAP thật, theo dõi operation và phiên đăng nhập. Mất auth dừng nhánh phụ thuộc, ghi partial; 401 không cộng coverage. Restart/auth handle mới phải được ghi đúng, không gọi login mới là resume phiên cũ. Mutation kiểm trạng thái liên quan để biết owner/object/kết quả, tránh replay khi ACK chưa rõ.

Dùng collector/report có sẵn, đọc đủ nội dung để báo đúng. Giữ native severity/confidence, phân biệt app/guard response khi thông tin có sẵn; thiếu thông tin thì nêu giới hạn, không dựng dữ liệu giả. Không yêu cầu xuất raw history/request archive/hash trong báo cáo cuối.

## Lifecycle và qualification khi được yêu cầu

Expiry/refresh/revoke, fault/repeatability và strict platform/secret assurance là mục tiêu riêng khi user giao hoặc executor đã chọn thực sự yêu cầu. Không đợi TTL, hai fresh runs hay independent approval để trả alerts thường. Không biến kiểm tra phiên đang hoạt động thành lifecycle đã kiểm.

## Protected identity khi response không echo caller

Dùng nguồn actor/role hợp lệ cùng protected probe/strategy được executor hỗ trợ; không lấy owner field làm caller. Signed-token validation có thể là lựa chọn theo entry, không ép mọi product có cùng issuer/key/route. Không đọc password/hash DB để làm báo cáo. Ghi đúng role nào đã xác minh và role nào chưa chạy.

## Kết quả và tiếp tục

RUN giữ method–route/role/kỹ thuật, thao tác/kết quả/lỗi, toàn inventory và phần chưa làm. ALERTS giữ native findings và nhận định có giới hạn; không có evidenceStatus hoặc mục/folder bằng chứng trong báo cáo dẫn xuất. Còn API/role trong scope chưa kiểm thì partial, tiếp tục các ca đủ điều kiện.

# Khám phá product dùng chung

Bắt đầu từ vị trí product user giao, không từ adapter hoặc report mẫu. Phân biệt checkout product với scanner; xác minh source/deployment/URL và môi trường, không tự suy production target. Source-only vẫn cho phép discovery khi chưa có deployment/Docker/auth.

## Inventory cần giữ

- Method–route đầy đủ theo scope; method khác nhau trên cùng path là operation khác. Thu query/body/path/header và validation/response cần thiết từ source/spec hoặc quan sát trong quyền.
- Public/protected, các role thực có, account/identity source, object/action/owner/relation/state ảnh hưởng quyền. Chưa biết thì ghi chưa xác minh, không gán dữ liệu của product trước.
- Fixture/phụ thuộc để chạy nghiệp vụ lõi, mutation/cleanup trong quyền; ID cụ thể lấy từ dữ liệu thật hoặc ACK, không đoán.
- Target/môi trường/origin scanner và direct/UI khi cần, deployment binding đủ xác định đúng product. Không dùng port/tên container một mình làm xác nhận; không in env/credential.
- Các mâu thuẫn và phần chưa thấy/chưa thực hiện; không đổi “chưa thấy” thành “không có”. Source/spec không đồng thời bắt buộc; nếu thiếu thì dùng observation hợp lệ hoặc nêu inventory còn chưa đầy đủ.

Ghi nguồn đã tham khảo bằng mô tả ngắn khi hữu ích; không yêu cầu hash/source archive/file chứng minh trong báo cáo. Nếu compiler cần manifest/source refs thì dùng schema hiện có như input nội bộ, không biến các field đó thành phần evidence của đầu ra cuối.

## Chuyển thành kế hoạch

Đọc [scope](assessment-scope-and-completion.md) và [multi-product](multi-product-backend.md). Nhiệm vụ đầy đủ được lập trước workload; recipe chỉ quyết định phần thực hiện ngay, không xóa route/role chưa hỗ trợ. Dependency đặt đúng case, không chặn toàn track khi một role thiếu account.

Common `product_assessment.py discover` tạo candidate; `materialize` nối deployment khi đã có. `product_discovery.py validate --manifest FILE` chỉ validate input, không scan. Schema `product-source-candidate/1.0`, `product-discovery/1.1` và plan của entry là interface hiện có, không tự đổi để bỏ gate. Chọn origin theo [quy tắc hiện hành](discovery-origin-selection.md).

Tự tìm route/auth/fixture từ dữ liệu được phép, chỉ hỏi PM thông tin không thể xác minh và ảnh hưởng scope/quyền/khả năng chạy. Không truy cập credential để làm discovery-only khi chưa được giao login. Có conflict target thì không gửi traffic tới target chưa xác định, tiếp tục phần source độc lập.

## Folder kết quả và tiếp tục

Tìm lại RUN theo product/môi trường đã xác minh; cùng product/môi trường tiếp tục ở folder ổn định. Build/image mới là thông tin lượt chạy, không xóa finding cũ chưa retest. Không trộn product khác hoặc âm thầm thay folder mất quyền truy cập. Source-only chưa có môi trường thì ghi đúng chưa có traffic, không gán môi trường cũ.

Đầu ra theo [ALERTS/RUN](product-assessment-handoff.md). Inventory/discovery nội bộ có thể do tool sinh; không gom thêm gói bằng chứng và không tạo folder evidence trong bộ bàn giao. Discovery hoàn thành không nghĩa đã quét toàn API.

Đối soát inventory độc lập và thực hiện phần còn thiếu qua [vòng trách nhiệm](responsibility-loop.md); cap/gate/stop của một producer không kết thúc task.

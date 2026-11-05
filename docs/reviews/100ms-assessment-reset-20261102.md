# Reset các lượt đánh giá ZAP 100ms — 02/11/2026

Thực hiện theo yêu cầu mới của người dùng: xóa các lượt chạy/evidence/tài nguyên assessment cũ, giữ sản phẩm và security scope. Yêu cầu này thay thế retention của những lượt cũ; không phải tuyên bố các kết quả cũ đã được thực thi lại hoặc đạt.

## Đã xóa

- Năm bộ RUN/ALERTS/SCOPE_ALERTS 100ms và working-session cũ dưới `assessment-results`.
- Raw/native session gzip, HTTP/log/report/fixtures/actor credentials/journals/working inputs/scripts của các assessment trong `.local/100ms-security-20261031`, `.local/100ms-workflow-acceptance-20261102`, `.local/100ms-fresh-20261101` (trừ đúng hai cấu hình runtime sản phẩm bên dưới).
- Derived product-run outputs ở phase2-preview, phase3-closure, phase3-final và alert-reclassification; các pointer tiếp tục tới những outputs này.
- Bốn container riêng được xác minh label `assessment.owner=100ms-fresh-20261101`, đều stopped trước khi xóa: `100ms-fresh-20261101-zap`, `100ms-fresh-20261101-mcp`, `100ms-fresh-20261101-internal-media`, `100ms-fresh-20261101-internal-recording`. Context `desktop-linux`; không dùng prune hoặc `down -v`.
- Report `zap-report-3783a637-c4c7-4b7e-82c2-d7b824ab3451.json` và ba file script/reservation trong workspace scanner dùng chung, đã đối chiếu target 8081 và reference từ RUN 100ms. Các report target 8080 khác không thuộc 100ms hiện tại được giữ.

## Giữ lại

- Product source/deployment/database tại `/Users/hahoangloc/Working/100ms-Video-Conferencing-and-Live-Streaming-sol-full/finalsource`; không sửa code, xóa volume, reset DB hay xóa fixture DB không được chọn riêng. Container sản phẩm giữ nguyên ID/image và trạng thái. Đây là sạch lịch sử assessment, không phải database trắng.
- Security catalog gốc trong repo sản phẩm và bản giữ độc lập [SECURITY_SCOPE.json](../../assessment-scopes/100ms/SECURITY_SCOPE.json), đủ **50 tiêu chí**, byte-identical theo SHA256 `fe820f17eb1b09b6920563846705227668afe82599c54c0343770f8db6871613`. [Điểm bắt đầu lượt mới](../../assessment-scopes/100ms/README.md) không mang verdict/observations/approval của lượt cũ.
- Hai file `.local/100ms-fresh-20261101/media-remediation-compose.override.json` và `fix-gateway-drain-deploy-override.json`: nhãn Compose của backend/frontend/provider-adapter đang tham chiếu chúng để chọn image sản phẩm hiện tại. Thư mục này chỉ còn hai file cấu hình đó, không còn RUN, evidence, actor/session hay continuation state. Giữ path để không phá việc tái tạo deployment; không khởi động lại sản phẩm chỉ để đổi nhãn/path.
- Source/test/skill, dirty changes, môi trường kiểm chứng skill và tài liệu triển khai; lịch sử generation/Figma/UC trong repo sản phẩm không thuộc các lượt ZAP này. Giữ ByteMe và các project khác. Các tài liệu đánh giá skill có thể còn link lịch sử tới artifacts đã được xóa theo yêu cầu này; chúng không là continuation inputs hoặc bằng chứng để cấp credit cho lượt mới.
- Scanner dùng chung và image/runtime dependencies đang dùng; API readback hiện tại: sites=0, contexts=0, active scans=0, spider scans=0, history filter cho target100ms=0. Không reset một shared session có dữ liệu của sản phẩm khác.

## Dung lượng và kiểm tra sau xóa

Nhóm file host trước xóa chiếm khoảng **3.19 GiB allocated**. Dung lượng host trống từ **4.37 GiB** lên **21.59 GiB**, tăng khoảng **17.22 GiB**; số đo có thể chịu biến động tiến trình nền. Docker writable container usage từ khoảng15,07GB xuống577,5kB; không cộng số logic Docker vào host freed bytes. Không compact hoặc sửa Docker.raw.

Đã kiểm tra các đường dẫn mục tiêu không còn, bốn container đã biến mất, catalog gốc/bản giữ khớp bytes, đủ50 requirements, các container sản phẩm vẫn hoạt động và database không reset. Không còn RUN100ms trong assessment-results. Không tạo hay khởi chạy lượt đánh giá mới.

[Danh sách đường dẫn/container và số đo chính xác](100ms-assessment-reset-20261102.json).

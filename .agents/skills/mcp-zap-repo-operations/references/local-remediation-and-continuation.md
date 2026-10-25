# Khắc phục lỗi cục bộ để tiếp tục assessment

Giữ vòng chẩn đoán → sửa tối thiểu → kiểm tra tập trung → tiếp tục. Ghi việc đã làm và kết quả trong RUN; không mở thêm yêu cầu đóng gói bằng chứng hoặc capability-proof campaign chỉ để bàn giao.

## Phạm vi sửa

Bao gồm lỗi plan/orchestration, mapping, parser/capture/checker, adapter, runtime và phối hợp resource cản phần assessment đã giao. Không sửa lỗ hổng/nghiệp vụ product, mở target/quyền hoặc giả approval. Được sửa/version contract, mapping và primitive cần thiết trong quyền được giao, có kiểm tra tác động; gate của allocation đang chạy vẫn enforce. Không đóng băng giới hạn implementation thành nguyên tắc nghiệp vụ. Các thay đổi vượt sửa công cụ cần thiết phải được xác định là dependency phát triển riêng, không âm thầm mở rộng nhiệm vụ.

Runner phụ theo [dispatcher](operation-dispatch.md#d-hợp-đồng-tối-thiểu-khi-viết-runner-phụ) phải cô lập theo product/môi trường. Common implementation pins hiện bao gồm recipe khác; kiểm ảnh hưởng plan đang chạy trước sửa shared core, không regenerate hash để ép plan lịch sử pass.

Giữ dirty state và dữ liệu cũ. Không reset/stash, sửa raw status/expected/test chỉ để pass. Không prune/xóa DB hoặc dữ liệu người dùng để vượt preflight.

## Phân loại trước quyết định

- Chưa đến lượt nhưng đủ prerequisite: xếp lượt, không gọi blocked.
- Plan/ledger/mapping sai: sửa từ trạng thái/ACK thực tế; chưa xác định kết quả mutation thì không replay.
- Runtime chưa sẵn hoặc resource lỗi: kiểm ownership/readiness/tài nguyên và diagnostic phù hợp trước retry.
- Thiếu capability ở wrapper: đọc operation/source thực; không suy ZAP thiếu capability nói chung.
- Thiếu account/role/fixture/policy: tự tìm nguồn hợp lệ trong scope; hỏi đúng phần không thể xác minh, giữ các case phụ thuộc chưa kiểm.
- Chỉ thiếu báo cáo/chứng minh phụ: dùng kết quả đang có; không yêu cầu hash/manifest/proof mới khi user chỉ cần thao tác và kết quả trung thực.

## Thứ tự chọn giải pháp

1. Dùng operation/entry sẵn có đúng scope/profile.
2. Điều chỉnh cấu hình, workload, fixture hoặc phối hợp operations.
3. Mở rộng runner/adapter hiện có ở phần còn thiếu.
4. Runner mới chỉ khi có lý do, tái dùng transport/auth/journal/report/cleanup.
5. Capability nền tối thiểu nếu operation gốc thực sự thiếu; thay đổi lớn thành dependency riêng.

Không gọi API tầng thấp để né gate. Dữ liệu product thuộc discovery/recipe/workload, không trong điều kiện pass chung. Không hardcode route/role/ID/số ca/verdict của một product làm tiêu chí chung. Nếu code bắt proof/pin, giữ gate, chọn đường phù hợp hoặc xử lý dependency cụ thể; không biến mọi assessment thành qualification của toàn scanner.

## Vòng khắc phục và tiếp tục

### Quyết định cho phần việc còn mở

Ghi ngắn ngay trong plan/RUN hiện có: phần việc bị ảnh hưởng, điều quan sát được, phương án đã đánh giá và bước được chọn. Không bắt schema, số lần thử hoặc file bằng chứng mới. Một lời ghi `not-operated`, `partial`, `unknown` hay “thiếu fixture” chỉ mô tả trạng thái, chưa giải quyết nó.

- Còn đủ điều kiện → xếp và thực hiện lượt tiếp trong scope đã giao.
- Input/config/adapter sai → chẩn đoán, sửa tối thiểu, kiểm tập trung rồi tiếp tục. Tool trả `isError:false` vẫn cần đọc auth/business outcome.
- Thiếu fixture → tìm helper/flow setup và kiểm quyền, owner/relation/state, uniqueness cùng khả năng hiển thị UI. Giữ dữ liệu cũ không cấm tạo fixture test mới đúng quyền. Có helper không tự cấp quyền DB; nếu thiếu quyền thì nêu đúng thao tác/tác động cần làm rõ, tiếp tục nhánh khác.
- Chưa biết outcome → reconcile ID/ACK/state trước mọi retry; diagnostic thiếu có thể bổ sung local đã lọc secret.
- Dependency thật → ghi nguyên nhân và lựa chọn khả dụng đã đánh giá/thử, vì sao chưa thể xử lý trong quyền/tài nguyên hiện có và điều kiện tiếp tục. Không cần gọi đường đã biết không phù hợp chỉ để đủ số attempts.
- Kỹ thuật không áp dụng hoặc phần ngoài giai đoạn user giao → giữ căn cứ nghiệp vụ/phạm vi đó; agent không tự giảm scope bằng cách chỉ chọn ca dễ.

Policy chưa được xác nhận là giới hạn nhận định riêng. Chỉ chặn ca khi thiếu kỳ vọng có nghĩa cho ca đó; không yêu cầu approval độc lập cho mọi BOLA workload đã có hypothesis được ghi trước traffic. Thiếu auth/fixture/capability cũng không được đổi thành N/A.

Trước dùng lại fixture hoặc khi lỗi lặp, tra [tri thức vận hành](operational-knowledge.md), kiểm hiện trạng thay vì chỉ đọc checkpoint. Sau recovery, cập nhật nơi tiếp tục chính thức và lưu bài học đã xác minh; không đổi lịch sử lỗi thành pass.

### Thực hiện recovery

1. Xác định bước lỗi và request đã dispatch/ACK/terminal hay chưa; dừng producer bị ảnh hưởng khi cần. Không phát start lần hai vì ACK chưa rõ.
2. Chẩn đoán bằng trạng thái/log/source sẵn có, chỉ lấy thông tin cần thiết và tránh secret. Không biết nguyên nhân thì ghi rõ, không giả căn nguyên từ exception type.
3. Chuẩn bị bản sửa nhỏ, giữ scope và compatibility; gom thay đổi phụ thuộc trước khi chạy product để tránh sửa code giữa từng route.
4. Kiểm tra tập trung theo thay đổi; không rerun mọi campaign. Kiểm output actual, không nới expected hoặc giả kết quả. Không cần bộ source archive/hash/independent review nếu không được yêu cầu.
5. Theo [rollover allocation](responsibility-loop.md): giữ nguyên plan/pins/raw lịch sử, tạo allocation mới theo bytes hiện tại; không repin run cũ. Cập nhật plan mới khi thực sự đổi workload/binding hoặc contract code yêu cầu. Reconcile state/actor/fixture hiện tại, tiếp tục đúng nhánh, ghi kết quả vào RUN và giữ các mục chưa làm.
6. Nếu hết cách hợp lệ trong quyền/tài nguyên hiện có, nêu blocker cụ thể và điều kiện tiếp tục; các nhánh độc lập đủ điều kiện vẫn chạy tiếp.

## Resource và prerequisite cục bộ

Theo [resource preflight](resource-preflight.md). Source discovery không phụ thuộc Docker. Thiếu disk/RAM cần đo đúng filesystem/Docker/app data và chẩn đoán; không hạ reserve hoặc xóa dữ liệu ngoài quyền. Stop/cleanup đúng resource thuộc run, không shared stop-all.

## Đọc kết quả sửa

Báo sửa gì, kiểm tra nào đã chạy, kết quả và giới hạn. Test pass chỉ xác nhận phần đã kiểm; không thay scan product hoặc policy acceptance. Nếu chưa thực thi DAST/BOLA thì ghi chưa thực thi. Sau sửa tự tiếp tục nhiệm vụ còn mở, không kết thúc chỉ vì có đủ file.

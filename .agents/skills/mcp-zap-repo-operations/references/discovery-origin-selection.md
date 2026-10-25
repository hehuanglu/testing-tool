# Chọn origin cho execution

Với input product/backend mới, dùng [common multi-product workflow](multi-product-backend.md) trước. Source-only không cần environment/FE giả; source/control proof không là runtime qualification. Các hướng dẫn finalsource/CLI cũ bên dưới chỉ giữ compatibility trong scope đã nêu.

Trước chọn executable subset, áp dụng [hợp đồng phạm vi](assessment-scope-and-completion.md):
inventory có provenance → trách nhiệm user/discovery → workload được admit → kết
quả đối chiếu. Origin/admission chỉ chặn execution phụ thuộc; không xóa route,
nghiệp vụ hay ownership obligation khỏi nhiệm vụ. Giữ source-only plan/dependency,
không fabricate deployment hoặc dùng historical binding làm authority.

Giữ mọi alias trong inventory discovery. Với manifest1.1/plan2.1, kiểm TẤT CẢ candidate authorized+bindingVerified của mỗi role bằng runtime transport inspector độc lập và cùng target binding trước traffic. Một alias lạ làm admission từ chối, không fallback.

Compiler, native auth profile, direct fixture client và cleanup dùng candidate hợp lệ đầu tiên theo thứ tự manifest cho mỗi role. Plan khóa scanner origin và admission kiểm selection drift. Đảo thứ tự inventory làm thay selection/hash và cần plan mới. Context, seed, active, controls, whitelist và guard dùng origin đó. Không có alias hay origin product mặc định trong lựa chọn chung.

Đây là quy tắc transformation/consumer; không thêm facts từ oracle, không xóa alias khỏi manifest đã freeze, không sửa file provenance đã khóa để làm admission pass. Giữ reference discovery đã pin; cập nhật selection policy ở reference riêng khi chỉ consumer thay đổi. Manifest1.0/plan2.0 và research v1 vẫn theo contract cũ.


FE anonymous có transport/journey research lane riêng: đọc [FE anonymous research](fe-anonymous-research.md) khi nhánh FE được chọn. Không ép qua backend HTTP binding; backend-only giữ prerequisites cũ.

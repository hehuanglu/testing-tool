# Retest và so phiên bản

Chỉ dùng khi user cần retest finding hoặc so các lượt/build. Không bắt hai fresh runs, fixed build hoặc source/image attestation cho assessment thường. Output vẫn [ALERTS/RUN](product-assessment-handoff.md).

## Chọn phạm vi so sánh

Xác định finding/API/role/input/kỹ thuật cần retest, version/môi trường và thay đổi đã biết. Cùng route nhưng khác role/state/build có thể khác nghĩa; ghi rõ điều chưa biết. Source review hay đọc report cũ không là runtime retest. Không gọi report delta là đã sửa lỗ hổng khi chưa kiểm hành vi phù hợp.

## Thực hiện

Tái dùng operation, fixture và workload phù hợp scope hiện tại; chạy kiểm tra có giá trị để xác định finding còn, không thấy lại hay chưa kết luận. Giữ native severity/confidence; không sửa suppression/expected/raw để alert biến mất. Không phát lại mutation cũ nếu outcome chưa rõ.

## Tổng hợp và retry

Ghi thao tác/kết quả retest trong RUN, cập nhật ALERTS với trạng thái nhận định trung thực và thời điểm/build khi biết. Finding chưa retest giữ lịch sử/chưa xác minh lại. Lượt hẹp không thay toàn baseline; retry cùng finding không thành bug mới. Không cần file claim mapping/hash/lineage hoặc gói chuyển máy riêng.

## Công cụ hiện có và giới hạn

`compare_research_runs.py`, `bola_research.py compare` và các regression entry chỉ hiểu loại input/contract cụ thể; đọc help/source trước dùng. Không bịa flag hoặc coi comparator same-build là product A→B retest. So sánh thủ công được gọi đúng là review thủ công; checksum/test pass không là security approval.

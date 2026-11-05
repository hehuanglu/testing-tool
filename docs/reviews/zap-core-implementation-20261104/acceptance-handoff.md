# Prompt bàn giao cho agent nghiệm thu

```text
Nghiệm thu hành vi của mcp-zap-repo-operations trong workspace /Users/hahoangloc/Working/testing tool. Đọc các file sau trước khi kiểm tra.

- docs/plans/zap-operations-core-implementation-plan-20261104.md
- docs/reviews/zap-core-implementation-20261104/implementation-report.md
- docs/reviews/zap-core-implementation-20261104/progress.md
- .agents/skills/mcp-zap-repo-operations/SKILL.md
- .agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/examples/state_recovery_walkthrough.py

Chạy lại lệnh offline trong implementation report. Đối chiếu test A–D bằng tên method và transcript. Dùng fixture mới với state và registry tường minh. Giữ working tree và historical audit artifacts. Mặc định chỉ dùng fixture offline. Mọi vận hành live, migration RUN thật, ghi Sheets hay thay quyền cần assignment riêng.

Sau khi xác minh helper, thực hiện behavioral acceptance qua context mới bằng locator chính thức và continuation projection. Gây interruption trên fixture ở ranh giới đã lưu trong walkthrough. Đánh giá agent từ cold start có đối soát pending effect, giữ no-replay, chuyển nhánh độc lập, mở và đóng repair, quay về đúng readback, chọn TTL đúng thứ tự và tiếp tục toàn bộ workflow đến verified delivery synthetic. Ghi từng lần cần user can thiệp và phân biệt stop được cấp quyền với việc agent tự dừng sau một block. Dùng structured decisions và evidence, không suy ra hành vi từ prose hoặc tổng test xanh.

Tách kết luận về durability, process restart và hành vi qua context. Ghi riêng giới hạn writable journal recovery, assessment lock qua callback F31, migration thật và live runtime qualification.
```

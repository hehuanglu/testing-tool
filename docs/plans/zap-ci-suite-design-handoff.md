# Bàn giao thiết kế bộ sinh test ZAP cho GitHub Actions

Ngày bàn giao: 2026-11-11. Repo: [hehuanglu/testing-tool](https://github.com/hehuanglu/testing-tool). Workspace: `/Users/hahoangloc/Working/UET/testing-tool`. HEAD lúc bàn giao: `c954ea8` trên `main`.

## Bối cảnh và mục tiêu

Skill [mcp-zap-repo-operations](../../.agents/skills/mcp-zap-repo-operations/SKILL.md) dùng ZAP để đánh giá sản phẩm theo tiêu chí. Bộ điều phối khám phá sản phẩm, lập kế hoạch, chọn thao tác và đọc lại bằng chứng. Khi sản phẩm thay đổi, người dùng muốn giữ lại một số case đã có giá trị để kiểm tra hồi quy tự động trên pull request.

Mục tiêu là thiết kế **một bộ phận dịch case và thao tác ZAP đã thực hiện thành test cố định có thể lưu trong Git**. Skill chọn case và gọi bộ sinh lúc chuẩn bị hoặc cập nhật suite. GitHub Actions chạy bộ test có sẵn, hiển thị kết quả check và lưu report ZAP của lần chạy. Developer có thể đọc diff, chạy lại cùng test ở local và quyết định giữ hay bỏ từng case.

Người dùng đã làm rõ rằng CI vận hành như một suite test thông thường. Phần lập kế hoạch, suy luận và phân luồng thuộc về lúc skill chuẩn bị test. Một file cho mỗi case là hướng ưu tiên để thao tác thêm, sửa hoặc xóa thể hiện trực tiếp trong Git diff. Cơ chế cụ thể để runner tìm file và việc có cần sinh manifest hay không còn thuộc phạm vi thiết kế.

## Hiện trạng đã kiểm chứng

- [zap_passive_smoke.py](../../tests/security/zap_passive_smoke.py) là demo viết tay. Nó dựng hai trang HTML trên loopback trong container Docker, dùng ZAP Automation Framework gửi hai request `GET` cố định, chờ phân tích thụ động và xuất report `traditional-json`. Trang `/docs` có CSP. Trang đối chứng `/control` thiếu CSP để xác nhận rule `10038-1` thực sự hoạt động. Script xác nhận traffic tới hai trang và kiểm tra report theo từng đường dẫn.
- [zap-passive-smoke.yml](../../.github/workflows/zap-passive-smoke.yml) gọi script khi có pull request hoặc chạy thủ công. Workflow ghim image ZAP theo digest, chạy container với `--network none` và có bước lưu JSON làm artifact. Lệnh Docker trong workflow là điểm vào để chạy lại demo từ repo root.
- Đã chạy ZAP thật ở local trong ba tình huống. Bản chuẩn báo `PASS` với exit `0`. Bỏ CSP trên `/docs` cho `CSP regression` với exit `1`. Bỏ request tới `/docs` cho `Missing fixture traffic` với exit `1`. Cả ba tạo JSON hợp lệ. Hai biến thể lỗi được tạo khi kiểm chứng và file demo giữ bản chuẩn.
- Script và workflow đang là file local chưa được Git theo dõi tại thời điểm bàn giao. GitHub Actions chưa chạy workflow. Repo này chứa các skill và công cụ kiểm thử, nên demo xác nhận đường chạy ZAP và assertion trên fixture, với việc chuyển case từ một đánh giá sản phẩm thật vẫn cần kiểm chứng.

## Giao diện cần thiết kế

Luồng dự kiến là **case đã review + bằng chứng đã lưu → bộ sinh → file test trong repo → CI chạy → kết quả từng case và report ZAP**.

1. **Đầu vào của bộ sinh.** Xác định thông tin nào có thể lấy trực tiếp từ case hoặc RUN và thông tin nào skill phải bổ sung. Tối thiểu cần định danh case và nguồn, luồng chức năng cần chạy, điều kiện hoặc fixture, bằng chứng chứng minh luồng đã tới đúng bước và kỳ vọng dùng để đánh giá. Phân biệt điều đã quan sát với điều sản phẩm phải đáp ứng. Một alert thường thiếu dữ liệu về fixture và độ bao phủ.
2. **Phép dịch.** Với lát cắt đầu tiên, dịch luồng HTTP chức năng cố định, bước chờ phân tích thụ động và yêu cầu xuất report sang plan Automation Framework. Dịch kỳ vọng sang assertion theo case. Gắn nguồn để reviewer lần lại đánh giá gốc. Phiên ZAP, cổng tạm và đường dẫn report được xác định lại cho mỗi run. Input thiếu điều kiện hoặc dùng thao tác ngoài khả năng bộ sinh cần có lý do rõ ràng để skill xử lý ở bước chuẩn bị suite.
3. **Đầu ra lưu trong Git.** Hướng đề xuất là mỗi case có một file dễ đọc trong `tests/security/cases/`, cùng một điểm chạy suite và một workflow mỏng. Chốt file nào là nguồn chuẩn, cách sinh lại file mà không làm mất chỉnh sửa đã review và cách runner phản ánh việc xóa một case. Nếu có file sinh kèm, thiết kế cần bảo đảm xóa case không để lại test cũ tiếp tục chạy. Khi suite trống, kết quả nên cho biết số case là 0.
4. **Đầu ra của mỗi run.** Cho biết ID case, kết quả và lý do, liên kết tới report khi có. Chỉ kết luận đạt khi có bằng chứng luồng đã chạy và assertion đạt. Báo rõ hồi quy, thiếu bằng chứng hoặc lỗi thực thi. Định nghĩa dữ liệu nào được lưu làm artifact, đặc biệt khi chuyển từ fixture tổng hợp sang sản phẩm thật.

## Mã và tài liệu cần đọc trước khi thiết kế

- [zap-result-boundary.md](../../.agents/skills/mcp-zap-repo-operations/references/zap-result-boundary.md) định nghĩa RUN là nơi giữ thao tác, control, độ bao phủ và giới hạn. ALERTS và SCOPE_ALERTS giữ cảnh báo và mapping. Đây là điểm bắt đầu để xác định dữ liệu đầu vào.
- [operational-readback.md](../../.agents/skills/mcp-zap-repo-operations/references/operational-readback.md) mô tả cách nối thao tác với bằng chứng. Dùng để tìm phần contract có thể giữ được khi tạo test mới.
- [report_reconciliation.py](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/report_reconciliation.py) có logic chuẩn hóa và đối soát report. Kiểm tra schema thực tế trước khi dùng lại. Parser hiện có kỳ vọng `id` ở từng instance, còn demo chỉ dùng các trường cần cho assertion CSP.
- [mcp_zap_gate.py](../../.agents/skills/mcp-zap-repo-operations/lib/mcp-zap-server/.github/actions/zap-security-gate/mcp_zap_gate.py) có helper chuẩn hóa snapshot và so sánh baseline. [run-assessment-regression.sh](../../.agents/skills/mcp-zap-repo-operations/lib/mcp-zap-server/.github/actions/zap-security-gate/run-assessment-regression.sh) là entrypoint replay bằng chứng đã lưu. Replay offline có thể dùng để kiểm chứng bộ sinh và việc đọc kết quả. Lần chạy suite trên build mới cần tạo bằng chứng mới.
- [ZAP Automation Framework](https://www.zaproxy.org/docs/desktop/addons/automation-framework/) và [rule CSP 10038-1](https://www.zaproxy.org/docs/alerts/10038-1/) là tài liệu cho lát cắt demo.

## Việc cần làm ở chat tiếp theo

1. Đọc case và cấu trúc RUN hiện tại để chọn chỗ nối bộ sinh. Đề xuất contract tối thiểu và vị trí module trong repo, với `zap-product-assessment` là ứng viên.
2. Viết ví dụ đầu vào và các file đầu ra cho case CSP. Làm rõ vai trò của YAML ZAP, assertion Python, fixture và workflow. Chốt cách người dùng xóa một file case mà không cần chỉnh workflow.
3. Định nghĩa tiêu chí nghiệm thu MVP. Cùng đầu vào sinh cùng bộ test. Suite sinh ra đạt trên fixture chuẩn, bắt được hồi quy CSP và báo thiếu bằng chứng khi thiếu traffic. Thêm case làm số test tăng. Xóa case làm nó biến mất khỏi kết quả lần chạy kế tiếp. Sau khi có bản reviewable, xác minh một run GitHub Actions và artifact của run đó.
4. Khi lát cắt đầu tiên đã rõ, chọn một case thụ động từ đánh giá sản phẩm thật để kiểm tra những dữ liệu hoặc fixture nào skill còn phải bổ sung. Chỉ mở rộng định dạng dựa trên nhu cầu thể hiện qua các case tiếp theo.

## Prompt để mở chat tiếp theo

> Đọc tài liệu bàn giao này và repo `hehuanglu/testing-tool`. Hãy thiết kế cụ thể bộ phận trong `mcp-zap-repo-operations` chuyển case ZAP đã review thành bộ test hồi quy cố định lưu trong Git. Chốt contract đầu vào, quy tắc dịch, cấu trúc file đầu ra, cách thêm hoặc xóa một case và cách đánh giá run. Dùng demo CSP hiện có để minh họa trọn luồng bằng ví dụ dữ liệu và file. Ưu tiên lát cắt thụ động, có thể kiểm chứng. Đối chiếu các helper hiện có và chỉ ra phần cần xây mới. Lượt này tập trung vào thiết kế.

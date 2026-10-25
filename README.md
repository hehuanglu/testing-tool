# Security Testing Tool

Project cung cấp hai skill kiểm thử bảo mật: ZAP cho kiểm thử động và Semgrep cho phân tích source local. Workflow ZAP theo nghiệp vụ tester: khám phá sản phẩm, xác định phạm vi, chọn kỹ thuật, thực hiện, đọc kết quả và đối soát phần việc còn thiếu.

Hỗ trợ các track BE anonymous, BE authenticated, FE anonymous, FE authenticated và BOLA ownership. Phạm vi kiểm thử xuất phát từ sản phẩm và yêu cầu của người dùng; khả năng của một runner không tự định nghĩa lại phạm vi đó.

## Skills

Hai skill được đặt chung trong `.agents/skills/`:

- [mcp-zap-repo-operations](.agents/skills/mcp-zap-repo-operations/SKILL.md): vận hành MCP ZAP cho BE/FE anonymous, authenticated và BOLA ownership.
- [run-semgrep-scan](.agents/skills/run-semgrep-scan/SKILL.md): chạy các track Semgrep OSS trên source được cho phép, với rules và runner đi kèm.

Đây là vị trí skill theo project của Codex: [tài liệu OpenAI](https://developers.openai.com/blog/skills-agents-sdk).

## Thành phần của workflow tổng quát

- [Skill mcp-zap-repo-operations](.agents/skills/mcp-zap-repo-operations/SKILL.md): hướng dẫn điều phối, phạm vi từng track, lựa chọn operation/runner, xử lý lỗi và bàn giao kết quả. Tài liệu và helper đi kèm nằm trong cùng thư mục skill.
- [`mcp-zap-server/`](mcp-zap-server/): Source scanner server và các operation MCP được lưu trực tiếp trong repository để import, crawl, scan, quản lý phiên và đọc kết quả.
- [`zap-product-assessment/`](zap-product-assessment/): thư viện, schema, recipe, runner và regression tests dùng chung. Một số entry và recipe vẫn dành cho sản phẩm hoặc contract cụ thể; cần kiểm tra điều kiện áp dụng trước khi dùng.

Skill điều phối cách sử dụng công cụ. Các operation native và thư viện thực hiện công việc cụ thể; có mã nguồn hoặc chạy được `--help` chưa chứng minh một track đã được kiểm thử trên sản phẩm.

## Source kiểm thử và dữ liệu chạy

Project không đóng gói source sản phẩm thử nghiệm. Chuẩn bị source/deployment được cho phép cho từng lượt; chọn operation, recipe hoặc adapter theo sản phẩm thực tế, không dùng mapping của sản phẩm trước làm mặc định.

Skill Semgrep hiện yêu cầu layout `finalsource/fe`, `finalsource/be`, `finalsource/compose.yaml` trong checkout chứa skill. Đây là contract đầu vào của runner; thư mục source thử nghiệm `finalsource/` không được lưu trong project này.

`operations/` là working data có thể được tạo khi chạy, gồm plan, actor/session, journal và kết quả trung gian. `reports/`, `handoffs/` có thể chứa kết quả tổng hợp. Dữ liệu này chỉ giữ local, không đưa vào Git; cleanup tài nguyên thuộc lượt chạy trước khi xoá working data đang dùng.

## Cách vận hành ZAP

1. Đọc skill, xác minh sản phẩm, deployment, phạm vi và quyền kiểm thử.
2. Lập inventory endpoint, role, input và UI journey phù hợp với track được giao.
3. Ưu tiên operation native; dùng runner có sẵn khi contract phù hợp, bổ sung adapter theo sản phẩm khi cần.
4. Chuẩn bị actor/session và fixture cần thiết trong phạm vi được giao.
5. Thực hiện workload hữu hạn, theo dõi scan/session và đọc kết quả thực tế.
6. Đối soát với inventory, xử lý phần còn thiếu và cleanup tài nguyên thuộc lượt chạy.
7. Tổng hợp kết quả, nêu rõ coverage, hạn chế và mức hoàn tất của từng track.

BE authenticated cần phiên đăng nhập thật; direct request hoặc BOLA không thay thế authenticated DAST. FE cần browser và UI journey thật; UI/passive traffic không tự hoàn tất nghĩa vụ active scan. Zero alerts không đồng nghĩa sản phẩm an toàn.

## Entry point của assessment

Từ thư mục gốc project, với môi trường Python của assessment đã được chuẩn bị:

```sh
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/product_assessment.py --help
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/fe_anonymous_research.py --help
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/fe_authenticated_research.py --help
```

Các lệnh trên chỉ hiển thị hướng dẫn CLI, không gửi traffic kiểm thử. Đọc [bản đồ lựa chọn runner](.agents/skills/mcp-zap-repo-operations/references/runner-routing.md) trước khi chọn entry cho một lượt chạy.

Một số schema/contract cũ vẫn được thư viện hoặc regression tests sử dụng. Các entry yêu cầu calibration hoặc qualification lịch sử phải có dữ liệu hợp lệ tương ứng; không bỏ admission gate hay dùng báo cáo cũ để khẳng định runtime hiện tại đã được kiểm chứng.

## Cấu hình local

`mcp-zap-server/.env` và `.zap-auth/` chứa cấu hình hoặc secret local. Chỉ dùng cấu hình khớp deployment đã xác minh; không commit credential, token, cookie hay raw response chứa dữ liệu nhạy cảm.

Xem [hướng dẫn scanner](mcp-zap-server/README.md) và [vận hành runtime local](.agents/skills/mcp-zap-repo-operations/references/local-runtime.md) để kiểm tra hoặc quản lý scanner. Xác minh Compose file set và tài nguyên đang sử dụng trước khi restart; không coi restart hoặc rebuild là một bước mặc định của assessment.

## Đầu ra ZAP

Bộ bàn giao cuối của mỗi assessment gồm hai file trong một thư mục ổn định:

- `ALERTS.json`: alerts/findings thực tế, phân biệt nguồn ZAP và direct, giữ severity/confidence phù hợp và tách số nhóm khỏi số instances.
- `RUN.json`: scope/track, môi trường, thao tác đã thực hiện, kết quả, coverage, hạn chế, phần chưa hoàn tất và bước tiếp theo.

Log và trạng thái nội bộ có thể được runner tạo trong working directory. Không biến chúng thành một bộ bằng chứng bổ sung mặc định. Chỉ ghi đã hoàn tất khi inventory trong phạm vi đã được đối soát; runner kết thúc hoặc exit code 0 chưa đủ để kết luận.

## Entry point Semgrep

```sh
python3 -B .agents/skills/run-semgrep-scan/scripts/scan.py --help
```

Lệnh trên chỉ hiển thị hướng dẫn. Chuẩn bị source và xác nhận phạm vi theo skill trước khi chạy scan. Các rule, metacheck và metadata của Semgrep được giữ cùng skill; dữ liệu chạy nằm trong Git metadata local.

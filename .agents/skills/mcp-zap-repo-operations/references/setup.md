# Cài và mang skill sang project khác

Copy nguyên thư mục `mcp-zap-repo-operations` vào `.agents/skills/` của project mới, hoặc cài cá nhân bằng helper của chính skill. Không cần copy source product, reports, secret hay thư mục `.venv` từ máy dev.

Từ thư mục skill:

```sh
python3 -B scripts/install_skill.py install
python3 -B scripts/install_skill.py check
```

Nếu bản cài khác nguồn, kiểm danh sách từ `check`, rồi dùng `install --update`. Helper giữ bản cũ trong `~/.codex/skill-backups/` trước khi thay; có `--target` để chọn nơi cài khác. Helper chỉ dùng stdlib và không cài dependency, cấu hình MCP hoặc gửi traffic. Khi dùng bản project trực tiếp thì không cần cài cá nhân.

## Paths và dependencies

Giải đường dẫn tuyệt đối từ vị trí skill đã nạp:

```sh
export SKILL_DIR="$PWD"
export ASSESSMENT_ROOT="$SKILL_DIR/lib/zap-product-assessment"
export ZAP_PYTHON='/absolute/path/to/python-with-assessment-dependencies'
PYTHONPATH="$ASSESSMENT_ROOT/src" "$ZAP_PYTHON" \
  "$ASSESSMENT_ROOT/scripts/product_assessment.py" --help
```

Thư viện assessment hiện yêu cầu Python 3.13 và dependencies trong `lib/zap-product-assessment/requirements.lock`. Chuẩn bị venv riêng ngoài skill/product khi cần; không mang venv giữa các máy hoặc tự tải package trong assessment. Native helpers stdlib như `inspect_operations.py` và `review_open_work.py` không yêu cầu thư viện assessment.

`lib/zap-product-assessment/` chứa source, schemas, profiles, CLI scripts và tests. `lib/mcp-zap-server/` chỉ đóng gói helper transport/report parser và regression entry mà thư viện import, kèm license và provenance; đây không phải một scanner server. ZAP/MCP endpoint, auth profile, Docker/browser, pinned images hoặc JAR chỉ cần khi executor được chọn thực sự dùng chúng. Xác minh runtime hiện hành; skill không tự dựng scanner khi nhận task source/status.

Khi cần build/doctor scanner riêng, xác minh `MCP_ZAP_REPO` trỏ tới source scanner đã chuẩn bị. Không suy nó từ cwd hoặc tên project; không mặc định checkout đó tồn tại. Các chỉ dẫn build/CI/Helm trong repo-map là tham khảo cho source scanner bên ngoài. Dùng connector MCP đã cấu hình khi không cần build/source.

Product mới dùng discovery/common entry và mapping của product đó. Các helper/adapter legacy có tên product giữ contract riêng, không là mặc định cho mọi project. Khi thực sự dùng legacy adapter có layout cố định, `ZAP_PRODUCT_WORKSPACE` là workspace product do caller chọn; mặc định cwd hiện hành, không trỏ vào skill. Không tạo product hoặc dùng credential lịch sử để thoả layout.

## Kiểm khi di chuyển

```sh
PYTHONPATH="$ASSESSMENT_ROOT/src:$ASSESSMENT_ROOT/tests" "$ZAP_PYTHON" -B \
  -m unittest discover -s "$ASSESSMENT_ROOT/tests" -p test_assessment.py -v
PYTHONPATH="$ASSESSMENT_ROOT/src" "$ZAP_PYTHON" -B \
  -m zap_assessment.capabilities check
```

Đây là kiểm offline contract/bookkeeping, không là product assessment hay runtime qualification. Output/actor/raw của assessment luôn ở thư mục private ngoài skill và product. Không lưu dữ liệu chạy mới vào `lib/` để chia sẻ sang project sau.

Kiểm di chuyển ngày 26/10/2026: copy riêng thư mục skill sang project mới, cài từ bản copy đó sang target khác và chạy từ cwd ngoài checkout dev; 85 tests contract/binding/capabilities/research/portability đạt với Python/dependencies có sẵn. Transport bundled khớp provenance; CLI/helpers `--help` chạy được mà không dùng source scanner ngoài. Thêm 79 ca regression/discovery/common workflow đạt khi dùng sample storage 8 GiB giả lập trong test harness. Lượt mặc định của nhóm mở rộng có sáu ca bị guard reserve chặn do dung lượng host; đây không là product execution. Test riêng giữ xác nhận thiếu reserve thì không dispatch; không hạ guard runtime. Chưa chạy assessment mới, provision scanner hoặc chứng nhận đa nền tảng.

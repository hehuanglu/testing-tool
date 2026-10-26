# Cài và vận hành Semgrep từ checkout mới

Nguồn chuẩn được version bằng Git là [toàn bộ cây run-semgrep-scanner](../.agents/skills/run-semgrep-scanner/SKILL.md). Cây này gồm hướng dẫn, năm bộ rules (85 IDs), catalog, bốn helper Python, examples synthetic và fixtures/tests. Không cần source, reports hoặc đường dẫn máy của người phát triển. Bản tại `~/.codex/skills/run-semgrep-scanner` là bản cài từ repo; sửa ở repo rồi đồng bộ để thay đổi được chia sẻ qua Git.

## Runtime

Cần Python 3.10+ và Semgrep OSS/CE. Helpers chỉ dùng stdlib; không cần `zap-product-assessment/.venv`, MCP ZAP, Docker, tài khoản Semgrep hoặc API token. Version đã kiểm cho bộ fixtures là **1.176.0**; [requirements-semgrep.txt](../requirements-semgrep.txt) pin engine trực tiếp, không là lock toàn bộ dependencies. Nếu đã có CLI phù hợp thì dùng CLI đó và kiểm help/version thực.

Người vận hành có thể chủ động cài runtime trong venv riêng từ root repo:

```sh
python3 -m venv .venv-semgrep
.venv-semgrep/bin/python -m pip install -r requirements-semgrep.txt
export PATH="$PWD/.venv-semgrep/bin:$PATH"
```

Bước pip cần mạng để tải package và dependencies, tách khỏi assessment local. Skill không tự cài runtime hoặc tải rules khi scan. Muốn máy hoàn toàn offline thì chuẩn bị runtime/package cache bằng quy trình riêng trước assessment. Không commit venv.

## Cài và đối soát skill cá nhân

Từ root repo, dùng Python stdlib:

```sh
python3 -B scripts/semgrep_skill.py check
python3 -B scripts/semgrep_skill.py install
```

`check` exit 0 khi toàn bộ file khớp byte, exit 1 nếu thiếu/khác. `install` cài mới hoặc giữ bản đã trùng. Nếu bản đã cài khác repo, kiểm danh sách từ `check` rồi cập nhật:

```sh
python3 -B scripts/semgrep_skill.py install --update
python3 -B scripts/semgrep_skill.py check
```

Update sao lưu nguyên bản cũ vào `~/.codex/skill-backups/` trước khi thay cây skill; file riêng và file cũ được giữ trong backup, không trộn vào bản mới. Cache Python không tính là drift. Không chạy hai installer đồng thời trên cùng target. Dùng `--target /absolute/path/run-semgrep-scanner` để kiểm thử hoặc chọn nơi cài khác. Sau mỗi lần pull có thay đổi skill, chạy lại check/update. Bản project trong `.agents/skills/` cũng dùng trực tiếp được; khi sửa chỉ sửa nguồn ở repo.

## Kiểm package và bắt đầu assessment

```sh
export SKILL_DIR="$PWD/.agents/skills/run-semgrep-scanner"
python3 -B -m unittest discover -s tests -v
python3 -B -m unittest discover -s "$SKILL_DIR/tests" -p 'test_*.py' -v
python3 -B "$SKILL_DIR/scripts/check_report_links.py" \
  "$SKILL_DIR/examples/reporting/RUN.example.json" \
  "$SKILL_DIR/examples/reporting/ALERTS.example.json"
python3 -B "$SKILL_DIR/scripts/select_rules.py" --base BE-IN-01
```

Các lệnh trên không scan product hoặc dùng mạng. Xem [fixtures](../.agents/skills/run-semgrep-scanner/tests/README.md) để kiểm engine/rules thật trên dữ liệu tổng hợp; kết quả không chứng nhận mọi rule/framework hoặc product.

Giao cho agent: “Dùng $run-semgrep-scanner kiểm source tại `<product-path>`, phạm vi `<tracks/chức năng>`.” Agent discovery source thực, chọn câu hỏi và chạy tuần tự các track thuộc scope. Product không cần tên hoặc layout cố định. Bundled rules chủ yếu NestJS/TypeScript, React và config; stack khác cần local/custom rules hoặc đọc source phù hợp, không lấy zero matches làm clean.

Đọc [operations](../.agents/skills/run-semgrep-scanner/references/semgrep-operations.md) để chuẩn bị settings/log/raw private ngoài product, tắt metrics/version check và dùng rules local. Tắt metrics không chặn mạng: macOS dùng `sandbox-exec` khi có và kiểm đối chứng; Linux/Windows cần isolation đã xác minh nếu nhiệm vụ yêu cầu offline bắt buộc. Thiếu guard thì ghi giới hạn/blocker đúng điều kiện, không tự hạ yêu cầu hoặc sửa firewall toàn máy.

Helper `select_rules.py` chiếu catalog từ rules thật; `record_round.py` thu process/native output; `report_records.py` tạo draft; `check_report_links.py` kiểm liên kết/provenance/counts. Chúng không tự chọn verdict hoặc hoàn tất assessment. Bàn giao mỗi track đúng `ALERTS.json` và `RUN.json`; raw/log/spec giữ private, không đưa Git.

## Kiểm bản đóng gói — 26/10/2026

Đã chạy 23 tests helpers Semgrep, 7 tests installer và 61 tests contract/binding ZAP chịu ảnh hưởng bởi việc thay snapshot profile bằng ví dụ synthetic: tất cả đạt. Checker cặp example đạt; 103 relative links trong skill hợp lệ; frontmatter, agent config và năm YAML rules parse được với 85 IDs duy nhất.

Semgrep OSS 1.176.0 trên macOS: 14 fixture cases đạt, gồm 59 vị trí positive và 23 vị trí negative; hai cases ngoài language/path được ghi là capability limitations. Full-config smoke có 59 matches/13 files scanned/errors rỗng. Offline metacheck quét đủ năm files, zero matches/errors; chỉ kiểm fix/fix-regex. Mọi lệnh Semgrep dùng settings private và `sandbox-exec` deny network; loopback probe thành công khi không guard và bị từ chối khi có guard.

Đã export cây Git staged ra thư mục mới, cài sang target mới và chạy lại tests installer/helpers, example checker, catalog 85 IDs từ cwd ngoài checkout phát triển. Bản cài cá nhân đã đối soát byte với nguồn repo. Không cài dependency mới, không chạy lại product assessment; chưa kiểm trên Linux/Windows hoặc chứng nhận mọi rule/framework. Raw validation synthetic giữ ngoài repo. Adapter/test ZAP còn tên product là implementation/contract, không là báo cáo, credential hoặc authority của lượt chạy trước. Việc dọn dữ liệu áp dụng cho cây hiện hành; không rewrite Git history.

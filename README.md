# Security Testing Tool

Hai skill kiểm thử bảo mật có thể dùng cho nhiều project. Mỗi skill đóng gói hướng dẫn, helpers và tài nguyên hỗ trợ trong chính thư mục của nó; source sản phẩm và runtime scanner được chuẩn bị riêng.

- **[run-semgrep-scanner](.agents/skills/run-semgrep-scanner/SKILL.md):** kiểm source bằng Semgrep OSS/CE kết hợp đọc code, triage và đối soát coverage. Có năm track: BE input, FE browser, authentication/session, authorization/ownership và configuration/build.
- **[mcp-zap-repo-operations](.agents/skills/mcp-zap-repo-operations/SKILL.md):** vận hành ZAP qua MCP cho BE/FE anonymous, authenticated và BOLA ownership; discovery sản phẩm, chọn kỹ thuật, thực hiện và đọc kết quả theo phạm vi được giao.

## Cấu trúc

```text
.agents/skills/
├── run-semgrep-scanner/
│   ├── SKILL.md
│   ├── references/           # Workflow, catalog, setup và contract đầu ra
│   ├── rules/                # Rules local đi kèm
│   ├── scripts/              # Installer, thu round và kiểm báo cáo
│   ├── tests/ và examples/   # Fixtures/tests và dữ liệu tổng hợp
│   └── requirements.txt      # Version engine Semgrep đã kiểm
└── mcp-zap-repo-operations/
    ├── SKILL.md
    ├── references/           # Workflow, operations, runtime và setup
    ├── scripts/              # Installer và helpers vận hành
    └── lib/
        ├── zap-product-assessment/  # Source, schemas, profiles, CLI và tests
        └── mcp-zap-server/          # Helper transport/parser cùng license

mcp-zap-server/               # Source scanner riêng, dùng khi cần build/setup
```

Để mang skill sang project khác, chỉ cần nguyên thư mục skill tương ứng. `lib/mcp-zap-server/` trong skill ZAP chứa helper được tái sử dụng, không phải một scanner server. Source scanner ở root repo không bắt buộc phải copy nếu đã có connector/runtime phù hợp.

## 1. Lấy repository

```sh
git clone https://github.com/hehuanglu/testing-tool.git
cd testing-tool
```

Các lệnh bên dưới bắt đầu từ root checkout này, trừ khi ghi khác. Installer chỉ dùng Python stdlib; nó không cài engine, cấu hình MCP hoặc chạy kiểm thử trên sản phẩm.

## 2. Chọn cách dùng skill

### Dùng theo project

Copy nguyên một hoặc cả hai thư mục vào `.agents/skills/` của project đích. Có thể dùng installer để copy đủ tài nguyên và phát hiện bản đã tồn tại:

```sh
PROJECT_DIR='/absolute/path/to/your-project'

python3 -B .agents/skills/run-semgrep-scanner/scripts/install_skill.py install \
  --target "$PROJECT_DIR/.agents/skills/run-semgrep-scanner"

python3 -B .agents/skills/mcp-zap-repo-operations/scripts/install_skill.py install \
  --target "$PROJECT_DIR/.agents/skills/mcp-zap-repo-operations"
```

Thay `PROJECT_DIR` bằng đường dẫn project thực. Không cần mang scripts hoặc thư viện từ root repo sang cùng. Giữ nguyên tên và toàn bộ nội dung thư mục skill, không chỉ copy `SKILL.md`.

### Cài bản cá nhân

Để dùng chung cho các project trên cùng máy, cài vào `~/.codex/skills/`:

```sh
python3 -B .agents/skills/run-semgrep-scanner/scripts/install_skill.py install
python3 -B .agents/skills/mcp-zap-repo-operations/scripts/install_skill.py install
```

Chỉ chọn những skill cần dùng. Khi có cả bản project và bản cá nhân, kiểm đúng đường dẫn skill agent đã nạp trước khi sửa hoặc vận hành.

### Kiểm và cập nhật

Sau khi pull thay đổi:

```sh
git pull --ff-only

python3 -B .agents/skills/run-semgrep-scanner/scripts/install_skill.py check
python3 -B .agents/skills/mcp-zap-repo-operations/scripts/install_skill.py check
```

`check` exit 0 khi toàn bộ file khớp nguồn, exit 1 khi thiếu/khác. `install` cài mới hoặc giữ nguyên bản đã trùng; bản khác nguồn cần kiểm danh sách thay đổi rồi cập nhật bằng `install --update`. Với bản project, thêm đúng `--target` như lúc cài vào cả lệnh check và install.

```sh
python3 -B .agents/skills/run-semgrep-scanner/scripts/install_skill.py install --update
python3 -B .agents/skills/mcp-zap-repo-operations/scripts/install_skill.py install --update
```

Update giữ nguyên bản cũ trong thư mục backup ngoài `skills/` trước khi thay cây skill. Với target cá nhân mặc định, backup ở `~/.codex/skill-backups/`; với target khác, installer in đường dẫn backup thực. Cache Python và venv không được đóng gói. Không chạy hai installer đồng thời trên cùng target.

Bảo trì nguồn trong `.agents/skills/` của repository rồi đồng bộ bản sử dụng; không chỉ sửa bản cá nhân nếu muốn chia sẻ thay đổi qua Git.

## 3. Chuẩn bị runtime

### Semgrep

Cần Python 3.10+ và Semgrep OSS/CE. Helpers chỉ dùng stdlib. Bộ fixtures đã kiểm với Semgrep **1.176.0**, được pin trong `requirements.txt`; đây không phải lock toàn bộ dependency bắc cầu.

Nếu chưa có engine phù hợp, chủ động chuẩn bị venv ngoài skill và source sản phẩm:

```sh
SEMGREP_VENV="$HOME/.local/share/security-testing/semgrep-venv"
python3 -m venv "$SEMGREP_VENV"
"$SEMGREP_VENV/bin/python" -m pip install \
  -r .agents/skills/run-semgrep-scanner/requirements.txt
export PATH="$SEMGREP_VENV/bin:$PATH"
```

Pip cần mạng để tải package. Bước setup này tách khỏi assessment: scan dùng rules local, settings/log riêng, tắt metrics và version check. Những thiết lập đó không chặn mạng; tác vụ yêu cầu offline bắt buộc cần isolation đã xác minh. Xem [setup Semgrep](.agents/skills/run-semgrep-scanner/references/setup.md) và [operations](.agents/skills/run-semgrep-scanner/references/semgrep-operations.md).

Rules đi kèm chủ yếu cho NestJS/TypeScript, React và config. Stack khác cần discovery, local/custom rules hoặc đọc source phù hợp; zero matches không chứng minh coverage hay an toàn.

### ZAP qua MCP

Chuẩn bị connector MCP trỏ tới scanner được phép sử dụng, rồi xác minh tools/schema, endpoint và auth profile thực. Nếu cần tự dựng hoặc build scanner, xem [hướng dẫn scanner](mcp-zap-server/README.md). Không cần dựng lại scanner cho mỗi project nếu runtime hiện có đáp ứng workload và cách ly phù hợp.

Helpers stdlib có thể chạy riêng. Khi dùng thư viện assessment đi kèm, cần **Python 3.13** và dependencies trong lock file:

```sh
ZAP_SKILL="$PWD/.agents/skills/mcp-zap-repo-operations"
ASSESSMENT_ROOT="$ZAP_SKILL/lib/zap-product-assessment"
ZAP_VENV="$HOME/.local/share/security-testing/zap-assessment-venv"

python3.13 -m venv "$ZAP_VENV"
"$ZAP_VENV/bin/python" -m pip install -r "$ASSESSMENT_ROOT/requirements.lock"

PYTHONPATH="$ASSESSMENT_ROOT/src" "$ZAP_VENV/bin/python" \
  "$ASSESSMENT_ROOT/scripts/product_assessment.py" --help
```

Lệnh `--help` không gửi traffic. Docker, browser, pinned images hoặc JAR chỉ cần cho executor được chọn thực sự sử dụng chúng. Khi cần source/build/doctor scanner, xác minh checkout riêng qua `MCP_ZAP_REPO`; không suy đường dẫn từ cwd sản phẩm. Xem [setup ZAP](.agents/skills/mcp-zap-repo-operations/references/setup.md) và [runtime](.agents/skills/mcp-zap-repo-operations/references/local-runtime.md).

## 4. Giao nhiệm vụ cho agent

Ví dụ cho Semgrep:

```text
Dùng $run-semgrep-scanner kiểm source tại /absolute/path/to/product.
Phạm vi: BE input và authorization/ownership. Đọc code để triage các candidates
và bàn giao ALERTS.json, RUN.json cho từng track.
```

Ví dụ cho ZAP:

```text
Dùng $mcp-zap-repo-operations kiểm BE anonymous của môi trường test tại
<origin được phép>, với source tại /absolute/path/to/product.
Discovery toàn bộ public API trong scope, dùng runtime MCP đã cấu hình,
đọc kết quả và bàn giao ALERTS.json, RUN.json cùng phần chưa kiểm.
```

Nêu product/source hoặc deployment, mục tiêu, phạm vi và quyền kiểm thử. Agent discovery inventory và chọn kỹ thuật; bạn không cần cung cấp rule IDs hoặc tự lập command scan. Có thể giao targeted scan hoặc retest; không mặc định mở mọi track.

Product không cần tên hay layout cố định. Các adapter legacy có contract riêng, không được dùng mapping của product trước làm mặc định cho product mới. ZAP authenticated cần actor/session thật; direct request hoặc BOLA không thay native authenticated DAST. FE cần browser/UI journey phù hợp, và UI/passive traffic không tự khép trách nhiệm active đang áp dụng.

## 5. Kiểm cài đặt mà không scan product

Semgrep helpers và báo cáo tổng hợp mẫu:

```sh
SEMGREP_SKILL="$PWD/.agents/skills/run-semgrep-scanner"
python3 -B -m unittest discover -s "$SEMGREP_SKILL/tests" -p 'test_*.py' -v
python3 -B "$SEMGREP_SKILL/scripts/check_report_links.py" \
  "$SEMGREP_SKILL/examples/reporting/RUN.example.json" \
  "$SEMGREP_SKILL/examples/reporting/ALERTS.example.json"
```

ZAP contract tests, sau khi chuẩn bị venv và các biến ở phần runtime:

```sh
PYTHONPATH="$ASSESSMENT_ROOT/src:$ASSESSMENT_ROOT/tests" "$ZAP_VENV/bin/python" -B \
  -m unittest discover -s "$ASSESSMENT_ROOT/tests" -p test_assessment.py -v
```

Đây là kiểm helper/contract trên dữ liệu tổng hợp, không phải kết quả assessment sản phẩm. Đọc [fixtures Semgrep](.agents/skills/run-semgrep-scanner/tests/README.md) nếu cần kiểm engine/rules thật. Không lấy help, tests pass hoặc exit 0 làm chứng nhận phạm vi sản phẩm đã hoàn tất.

## Đầu ra và dữ liệu local

Bộ bàn giao cuối gồm hai file:

- `ALERTS.json`: findings/alerts thực, triage và nguồn công cụ hoặc đọc source/direct; giữ severity/confidence phù hợp.
- `RUN.json`: scope, inventory, thao tác và kết quả, coverage, hạn chế, việc chưa làm và trạng thái hoàn tất.

Semgrep bàn giao một cặp cho mỗi track theo workflow tuần tự; ZAP tổng hợp theo scope/track được giao. Log/raw/spec/actor/session của executor giữ private ngoài skill và source sản phẩm. Không commit credential, token, cookie, raw response hoặc dữ liệu chạy vào thư mục skill để mang sang project sau.

Zero alerts không đồng nghĩa sản phẩm an toàn. Chỉ khép phạm vi khi inventory và câu hỏi trong scope đã được đối soát, đồng thời ghi rõ phần chưa thực hiện hoặc bị chặn.

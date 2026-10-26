# Vận hành Semgrep local

## Chuẩn bị

Giải `SKILL_DIR` theo file SKILL.md đã nạp; `PRODUCT_DIR`, source roots và `RULES_FILE` lấy từ discovery. Không mang đường dẫn máy hoặc layout product cũ vào mặc định. Dùng binary cài sẵn; thiếu CLI thì chẩn đoán cách cài phù hợp trong quyền nhiệm vụ, không giả đã scan. Git/Python chỉ cần nếu thao tác cụ thể sử dụng chúng.

Tạo workspace private cho settings/log/raw của assessment, nằm ngoài source targets và không được commit. Ví dụ dưới dùng shell macOS/Linux; trên nền tảng khác dùng cách tương đương, không yêu cầu shell này là điều kiện Semgrep. Thay các giá trị mô tả bằng đường dẫn đã xác minh trước chạy:

```sh
SKILL_DIR='/absolute/path/to/run-semgrep-scanner'
PRODUCT_DIR='/absolute/path/to/product'
SOURCE_DIR='/absolute/path/to/product/source-in-scope'
RULES_FILE="$SKILL_DIR/rules/be-public-static.yml"
umask 077
SCAN_WORK=$(mktemp -d "${TMPDIR:-/tmp}/semgrep-work.XXXXXXXX")
export SEMGREP_SETTINGS_FILE="$SCAN_WORK/settings.yml"
export SEMGREP_VERSION_CACHE_PATH="$SCAN_WORK/version-cache"
export SEMGREP_LOG_FILE="$SCAN_WORK/semgrep.log"
export SEMGREP_SEND_METRICS=off
export SEMGREP_ENABLE_VERSION_CHECK=0
export SEMGREP_APP_TOKEN=''
semgrep --version
semgrep scan --help
```

Đây là môi trường process riêng, không sửa settings đăng nhập hiện có. Không dump toàn env vì có thể chứa credential. Kiểm help của CLI thực và đọc cấu hình trước chạy. Không gắn label “readiness passed” nếu chưa kiểm rule/targets, không gọi help/version là scan.

## Privacy và network

Mặc định chỉ dùng file rules local đã đọc; không `--config auto`, Registry ID, URL, `semgrep ci`, login, publish hay URL output. `--metrics=off`, version check off, settings riêng và token trống giảm kết nối tự động nhưng **không phải cơ chế chặn mạng**. Nếu tác vụ đòi offline bắt buộc, cần guard đã xác minh; thiếu thì báo blocker cho lượt đó, không tự hạ điều kiện.

Trên macOS có `sandbox-exec`, có thể dùng prefix sau cho version/help, lint, test và scan; kiểm guard chạy được và kiểm đối chứng một kết nối bị từ chối trước khi ghi network blocked (ví dụ loopback server local cùng connect probe với/không guard, không dùng dữ liệu product):

```sh
printf '(version 1)\n(allow default)\n(deny network*)\n' > "$SCAN_WORK/network-deny.sb"
sandbox-exec -f "$SCAN_WORK/network-deny.sb" semgrep --version
```

Trên Linux/Windows dùng isolation sẵn có phù hợp nếu cần, không đoán rằng một flag của Semgrep chặn network. Không tự provision Docker/VM hoặc sửa firewall hệ thống. Thiếu sandbox-exec là giới hạn cơ chế macOS, không là giới hạn phân tích source của Semgrep.

## Chạy lượt có mục đích

Theo [workflow mặc định](sequential-track-workflow.md), chọn rounds cho track đang làm, thu/đọc native output và tự kiểm cặp ALERTS/RUN trước execution track sau. Nhiều `--config`/roots có thể phục vụ các câu hỏi của cùng track; không tự gộp execution nhiều track chỉ vì tiện chạy cả thư viện. Output private của round khác với hai file handoff ổn định cho từng track.

Ví dụ native CLI sau đã chọn đúng source/rules. Nếu dùng guard, thêm prefix đã kiểm phía trước `semgrep`. Tạo tên lượt mới mỗi lần, không overwrite output cũ:

```sh
mkdir "$SCAN_WORK/round-01"
cd "$PRODUCT_DIR"
semgrep scan --oss-only \
  --config "$RULES_FILE" \
  --metrics=off --disable-version-check --strict --no-rewrite-rule-ids \
  --verbose --time \
  --json-output "$SCAN_WORK/round-01/native.json" \
  "$SOURCE_DIR" \
  > "$SCAN_WORK/round-01/stdout.log" 2> "$SCAN_WORK/round-01/stderr.log"
SCAN_EXIT=$?
```

Ghi `SCAN_EXIT` ngay sau process, không lấy exit của `cat`, pipe hay parser thay thế. CLI có thể exit 0 khi có findings nếu không dùng `--error`; `--error` thay đổi ý nghĩa exit 1. Đọc exit theo command/help thực cùng JSON và stderr, không gán chung mọi nonzero thành product finding hoặc mọi zero thành clean.

Có thể lặp `--config` cho nhiều bộ local, truyền nhiều roots nếu đều thuộc scope, hoặc `--include`/`--exclude` với lý do. Không có exclusion bắt buộc cho `.env*` hay tests: quyết định theo mục tiêu và bảo mật đầu ra; không in nội dung secret. Binary/generated/vendor thường cần xử lý khác source ứng dụng, ghi phần loại trừ ảnh hưởng.

`--include` không tự vượt `.gitignore`/`.semgrepignore` và không thay đổi `paths` trong rule. `--no-git-ignore` chỉ thay đổi lọc Git, không vô hiệu hóa mọi lọc khác. Không sửa ignore repo hoặc dùng internal flags để lách phần scope chưa hiểu. Khi cần quét file bị bỏ, xác định cơ chế cụ thể của version, thực hiện lượt hẹp phù hợp hoặc bố trí bản sao private có mapping rõ; ghi ảnh hưởng đổi path đối với rules. Không coi bản sao mặc định tương đương project đầy đủ.

Có thể thêm `--dataflow-traces` cho output mà version hỗ trợ khi cần đọc luồng. Không coi có trace là engine đã theo đầy đủ mọi caller/file. `--timeout`, `--timeout-threshold`, `--jobs` chọn theo lượt và tài nguyên; không cố định 30 phút hoặc unlimited cho mọi product.

## Đọc kết quả thực

### Helper thu round tùy chọn

[record_round.py](../scripts/record_round.py) chạy argv qua subprocess không shell, ghi thời điểm/exit trực tiếp và đọc native JSON. Sau khi đọc CLI help, chọn rules/targets và lưu checkpoint RUN, tạo spec private theo [mẫu](../examples/reporting/round-spec.example.json). Thay các placeholder; đặt `--output-dir` mới ngoài mọi source target. `argv` chứa token `{native_json}` đúng một lần tại giá trị `--json-output`; có thể thêm guard đã kiểm phía trước semgrep. Dùng môi trường settings/metrics/version/token riêng ở bước chuẩn bị, helper không tự provision hoặc xác minh guard.

```sh
python3 "$SKILL_DIR/scripts/record_round.py" --spec "$SCAN_WORK/round-spec.json" --output-dir "$SCAN_WORK/round-02"
```

Spec ghi cwd/targets thực và privacy/rules/exclusions đã chọn. `redact_values` liệt kê literal cần che khỏi metadata, kể cả positional args/paths nếu nhạy cảm; helper còn che secret-shaped assignments và flags phổ biến. Không truyền credential thật trên argv; không có heuristic redaction nào bảo đảm nhận mọi secret. Spec, native.json, stdout/stderr vẫn private, có thể chứa source/material nhạy cảm; không in chúng mặc định. File `round.json` không có matched lines, interpolated native messages, error text hoặc env dump; giữ index/reference về raw để tester đọc đã lọc. Raw message/ID/occurrences không bị xóa.

Exit helper cho biết đã thu được bản ghi; scan exit nằm ở `round.exit_code`, không lấy helper exit 0 làm scan pass. Helper chỉ thu observed facts: version/engine fields có thật, native results/errors/scanned/skipped entries và nguồn mỗi count. Requested engine giữ riêng, không giả actual. Chưa có adapter log-count đã kiểm theo version nên counts chỉ log/loaded/executed để null; không dùng wording log hoặc `time.rules` suy coverage. Unknown output/counts giữ null, zero scanned có diagnostic không clean. `status` null, `finding_ids` rỗng chờ tester đối soát; helper không chọn expectation, false-positive, priority, root cause hay completion. `review_groups` chỉ nhóm cùng native location để tiết kiệm đọc, chưa nhóm issues; tester có thể ghi caller/control dùng chung sau review. Merge bản ghi đã đọc vào RUN; `round.json` và raw không là file handoff mới.

[report_records.py](../scripts/report_records.py) hỗ trợ `init <new-dir> --assessment-id <id>` tạo hai draft, hoặc `question Q-01 --track-id be-input --base-id BE-IN-01` xuất skeleton để bổ sung vào RUN. Không overwrite file có sẵn; draft null phải được tester hoàn thiện theo mức nhiệm vụ. [check_report_links.py](../scripts/check_report_links.py) chỉ đọc hai báo cáo, báo lỗi liên kết/provenance/counts đã biết, không tự sửa nội dung hoặc kiểm sự thật evidence.

Đọc native JSON/log local, chỉ trích dữ liệu cần thiết đã sanitize. Tuỳ version, kiểm các phần `results`, `errors`, `paths.scanned`, `paths.skipped`, `skipped_rules`, `time` và engine/version khi có. Không giả key luôn tồn tại. Unknown là null; danh sách lỗi rỗng chỉ có nghĩa trong dữ liệu thực đã đọc được.

Phân biệt:

- rules cấu hình / hợp lệ / loaded / thực sự executed nếu công cụ có thông tin; không suy executed từ số rules trong YAML;
- candidate files / files scanned / skipped và lý do; tổng scanned không chứng minh mọi rule áp dụng mọi file;
- parse error, invalid rule, timeout, empty target, unsupported language, tool crash và findings;
- lượt bắt đầu / process kết thúc / output đọc được / câu hỏi nghiệp vụ đã giải quyết.

Các con số có thể khác nhau hợp lệ: CLI có thể đọc 85 rules nhưng chỉ chạy phần áp dụng cho ngôn ngữ/path của targets. Danh sách `time.rules` phục vụ timing không tự là số loaded/executed; giữ số gốc kèm ý nghĩa và để null nếu chưa xác định được. Với verbose logs, phân biệt tiêu đề “Partially analyzed” với danh sách lỗi bên dưới; tiêu đề kèm `<none>` không phải một lỗi parse.

Lượt chỉ gọi `completed` khi thực thi có kết quả hợp lệ và không còn lỗi làm thiếu mục tiêu lượt. Còn một phần lỗi thì `partial`; không thực hiện được phép kiểm có nghĩa thì `blocked`. Dù process kết thúc, vẫn ghi native exit và dữ liệu partial. Không loại bỏ findings của phần chạy được chỉ vì phần khác lỗi.

## Rule parsing, offline metachecks và test

Scan thông thường kiểm cấu hình/rule trước hoặc trong thực thi; kiểm lỗi đó ở lượt thực, không chạy `--validate` mù quáng. Một số version dùng `--validate` để tải `p/semgrep-rule-lints`, không phù hợp yêu cầu local/offline. Nếu cần parse-only offline, kiểm đường dẫn/flags của `semgrep-core` cài cùng CLI rồi dùng khả năng local có thật; core CLI là chi tiết theo version, không là dependency cố định của skill.

Metacheck local chỉ phát hiện directive `fix`/`fix-regex`, không chứng minh rule đúng ngữ nghĩa. Có thể chạy chính nó bằng Semgrep local trên thư mục rules được chọn, dùng nguyên flags OSS/privacy/strict/output như lượt thường và `--config "$SKILL_DIR/references/offline-rule-lints.yml"`. Không dùng findings của metacheck làm findings của product. Scan không được dùng `--autofix`; nếu metacheck phát hiện directive, đọc và báo đúng; không dùng autofix hoặc thay semantics âm thầm để báo pass.

Với rule mới/sửa, tạo test file cạnh rule với cùng basename và extension phù hợp, trong thư mục test riêng. Dùng `# ruleid: <id>` cho ca nên bắt, `# ok: <id>` cho ca không nên bắt (comment theo ngôn ngữ). Chạy bằng `semgrep scan --test /local/rule-tests --oss-only --metrics=off --disable-version-check` cùng settings riêng và guard nếu cần; đọc số ca, kết quả và lỗi thật. Nếu test harness lỗi, chẩn đoán cách gọi/version; có thể scan fixture và đối chiếu vị trí mong đợi trực tiếp, ghi đúng phương pháp thay thế. Không coi YAML parse pass hoặc test không chạy là rule đã bắt đúng. Xem [rules và triage](rules-and-triage.md) và [layout fixtures](../tests/README.md).

## Tiếp tục và retest

Mỗi lượt mới có output riêng; giữ câu hỏi, lệnh, source version và kết quả liên quan. Sau interrupt, kiểm process/output thuộc lượt trước trước khi kết luận; scan read-only có thể chạy lại sau reconcile, ghi đó là lượt mới. Ghi source_state_id và các câu hỏi/lượt đã đối soát khi tiếp tục.

Retest sau thay đổi cần xem diff và chạy rule/source chịu ảnh hưởng, mở lại ngữ cảnh kiểm soát. Finding biến mất có thể do đổi path, ignore, rule hoặc scanner; kiểm nguyên nhân trước ghi fixed. Nếu chỉ được giao retest, không tự sửa ứng dụng hay mở whole-product assessment.

Liên kết source state/thao tác/counts theo [contract v2](reporting-and-completion.md); evidence native/manual theo [evidence](evidence.md). Scan output thuộc private workspace, không overwrite lượt hoặc báo cáo lịch sử.

## Tài liệu gốc khi cần kiểm capability

- [Chạy rules local và kết hợp rules](https://docs.semgrep.dev/running-rules)
- [CLI reference và exit codes](https://docs.semgrep.dev/cli-reference)
- [Ignore và target selection](https://docs.semgrep.dev/ignoring-files-folders-code)
- [Taint analysis](https://docs.semgrep.dev/writing-rules/data-flow/taint-mode/overview)
- [Test rules](https://docs.semgrep.dev/writing-rules/testing-rules)
- [Ranh giới CE và cross-file analysis](https://docs.semgrep.dev/semgrep-code/semgrep-pro-engine-intro)

Help/runtime được cài là căn cứ cho flags đang thực thi; kiểm tài liệu chính thức khi thông tin version chưa rõ. Không biến một lần smoke thành chứng nhận hỗ trợ mọi version/ngôn ngữ.

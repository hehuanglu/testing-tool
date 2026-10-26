# Fixtures đại diện, không phải product assessment

## Regression bổ sung từ báo cáo cải thiện 2026-10-26

Các ca logger/receiver/DTO/returns/lifecycle/criteria giữ broad inventory matcher: fixed password text, Map/Set.delete, service wrapper, response DTO, DB config return, login MinLength và prior guard vẫn có thể match hợp lệ. Positives ở đây là candidate shapes, không phải vulnerabilities. Aliases/custom wrappers/inherited fields ngoài shape có negative annotated kèm giới hạn; không coi đó là safe control. Không loại tất cả literals, response/config files hoặc services. Fixture chỉ dùng synthetic placeholder, không credential thật.

CSP đổi sang `config-nginx-csp-scope-review-v2` inventory server/header/include lines sau probe sáu configs tối thiểu. Server có CSP vẫn là positive inventory, vì cần đọc effective scope/inheritance. Cấu hình nhiều servers, parent/child add_header, `always` và include source thiếu được giữ review; matcher không kết luận missing CSP. Historical ID không bị sửa trong native/report cũ.

Chạy helpers bằng stdlib, không engine/network:

```sh
python3 -m unittest discover -s "$SKILL_DIR/tests" -p 'test_*.py' -v
python3 "$SKILL_DIR/scripts/check_report_links.py" "$SKILL_DIR/examples/reporting/RUN.example.json" "$SKILL_DIR/examples/reporting/ALERTS.example.json"
```

Synthetic records kiểm native-only/manual-only/mixed support, nhiều rounds, partial/unreadable output, zero scanned, ID/reference/count/source-state mismatch, privacy và không overwrite. Đây là kiểm bookkeeping, không kiểm validity evidence/verdict. Các tình huống source ngoài language/path, config basename khác, wrapper/field names khác và source-change/retest phải đối chiếu scope/ignore/rules/source state; không lấy mất match là fixed.

[run_fixtures.py](run_fixtures.py) tự stage fixtures tổng hợp ra `cases/`, trích đúng rules được annotations chọn, scan từng file và so **toàn bộ** ID/path/start.line cùng ok positions/errors/scanned files. Không download dependency/runtime. Sau khi đọc help và xác minh guard, chạy với `--work-dir <new-private-dir>`, thêm `--prefix-json '["sandbox-exec","-f","/absolute/verified-network-deny.sb"]'` nếu dùng guard. Không ghi network blocked chỉ từ cấu hình prefix. Raw/log/results ở workspace private, không handoff assessment. `compose.prod.yaml` và `outside-language.py` được kiểm riêng như path/language limitations với scanned rỗng, không tính semantic negative pass. Dùng runner này cho toàn bộ regression hiện hành; số 8/7 ở hướng dẫn gốc dưới chỉ thuộc năm fixtures đại diện ban đầu.

Mỗi track kiểm một rule thật với positive và negative có ý nghĩa. BE dùng request-to-SQL local và bound-value negative; FE HTML sink vs text render, không giả sanitizer; AUTH literal/fallback JWT config synthetic vs config lookup/member và unrelated key; AUTHZ ID lookup và guard-before-lookup vẫn match, slug ngoài shape không chứng minh authorized; CFG privileged true/false cùng `compose.prod.yaml` để quan sát path filter. Không thực thi code fixtures, không chứa credential thật.

## Layout và chạy lại

Giải SKILL_DIR theo skill và tạo SCAN_WORK private theo [operations](../references/semgrep-operations.md), settings riêng, metrics/version check off. Đọc CLI help, xác minh guard khi cần và dùng guard cho mọi lệnh Semgrep. Không dùng `--validate` nếu version tải remote lints. Không cài CLI/parser từ mạng chỉ để vượt kiểm tra.

Không copy library rules vào tests. Tạo config tạm từ đúng block bundled tại lúc kiểm; ví dụ Python stdlib dưới chỉ trích nguyên YAML block, không sửa matcher:

```python
from pathlib import Path
import re
# skill_dir và scan_work là paths đã xác minh, nằm ngoài product targets.
selection = {
    "be-input": ("be-public-static.yml", "nestjs-public-request-to-sql-text-local"),
    "fe-browser": ("fe-public-static.yml", "react-public-dangerously-set-inner-html"),
    "authentication-session": ("be-auth-static.yml", "nestjs-auth-hardcoded-jwt-secret"),
    "authorization-ownership": ("authorization-ownership-static.yml", "nestjs-ownership-id-only-find-one"),
    "configuration-build": ("supply-chain-config-static.yml", "config-compose-privileged"),
}
for track, (filename, rule_id) in selection.items():
    text = (skill_dir / "rules" / filename).read_text()
    blocks = re.split(r"(?=^  - id: )", text, flags=re.M)
    chosen = [b for b in blocks if b.startswith("  - id: " + rule_id + "\n")]
    assert len(chosen) == 1
    (scan_work / (track + ".yml")).write_text("rules:\n" + chosen[0])
```

Semgrep 1.176.0 mặc định ignore `tests`/`fixtures`; scan trực tiếp có thể exit 0 nhưng không phân tích file nào. Stage **fixtures tổng hợp** vào `$SCAN_WORK/cases/<track>/` (không có component tests/fixtures), giữ nguyên basename và nội dung. Ghi mapping cases/<track>/<file> → tests/fixtures/<track>/<file> trong working notes. Đây là bố trí fixture để kiểm detector, không sửa product/ignore hoặc đổi rule.paths. Không coi cách stage này tương đương project product đầy đủ.

Ví dụ Python trước khi chạy:

```python
import shutil
shutil.copytree(skill_dir / "tests" / "fixtures", scan_work / "cases")
```

Chạy từng config với folder cases tương ứng, không sửa source/rule paths để lọt filter. Ví dụ sau khi thay TRACK/RULE_CONFIG bằng selection trên; dùng prefix guard đã xác minh nếu có:

```sh
mkdir "$SCAN_WORK/$TRACK"
semgrep scan --oss-only --config "$RULE_CONFIG" \
  --metrics=off --disable-version-check --strict --no-rewrite-rule-ids \
  --verbose --time --json-output "$SCAN_WORK/$TRACK/native.json" \
  "$SCAN_WORK/cases/$TRACK" \
  > "$SCAN_WORK/$TRACK/stdout.log" 2> "$SCAN_WORK/$TRACK/stderr.log"
SCAN_EXIT=$?
```

Đọc exit/errors/skips/timeouts và actual results. `// ruleid:` hoặc `# ruleid:` chỉ dòng code ngay sau phải match, `ok:` ngay sau phải không match cho rule đó. Với scan JSON trực tiếp, đối chiếu **toàn bộ** `(check_id, path, start.line)` với annotated ruleid positions, đồng thời kiểm ok positions vắng; không chỉ so số findings. Dự kiến 8 matches: BE 1, FE 1, AUTH 3, AUTHZ 2, CFG 1; 7 ok positions không match. AUTH giữ config.getOrThrow("JWT_SIGNING_KEY") làm regression: chuỗi bên trong call không phải secret literal, cùng hai positives cho fallback ||/??. Những con số là expectation của ca tổng hợp, không hardcode verdict product.

`compose.prod.yaml` có `privileged:true` nhưng ngoài rule.paths: kiểm verbose target-selection/skipped paths thực và `paths.scanned`; đây là path-filter limitation, không `ok` semantic. Có thể file không xuất trong paths.skipped của một version; ghi dữ liệu có thật từ logs/selection, không invent skipped counter. Discovery phải giữ biến thể file trong scope và review/custom rule khi assessment thật.

Có thể dùng native `--test` với layout rule/fixture cạnh nhau cùng basename trong workspace tạm; không cần nếu direct fixture scan/đối chiếu vị trí đã thực hiện. Không cần test framework bổ sung; runner stdlib ở trên chỉ lặp CLI và đối chiếu vị trí. Nếu matcher thay đổi do lỗi thật, thêm regression case liên quan; metadata/message-only không bắt full library semantic tests. [Validation](../references/validation.md) ghi kết quả và giới hạn thực.

# Validation và giới hạn xác nhận

## Cập nhật workflow tuần tự — 2026-10-26

Theo yêu cầu đưa cách vận hành của lượt trước thành mặc định: assessment chọn các track trong scope, vận hành/thu output/triage/tự kiểm từng track trước execution track kế tiếp. Operator hoàn thiện operation/UI/config ledger và kiểm hai chiều quy trình/evidence; tự kiểm nằm trong `tracks[].review`, cặp ALERTS/RUN riêng mỗi track. Partial/blocked vì external dependency sau khi hết source step khả thi không ngăn track độc lập. Không mặc định chạy cả năm track cho targeted task hoặc ép một round/YAML mỗi track.

Entrypoint, workflow/reporting/evidence/CLI routing, UI default prompt và ví dụ synthetic đã đồng bộ. Không đổi matcher/rules, helper code, engine/privacy policy, product hoặc reports assessment lịch sử. Ví dụ gộp chỉ minh họa schema/references, không là default execution hoặc review thật.

Validation thực: 23 tests stdlib pass; checker cặp JSON synthetic pass; skill-creator quick_validate pass bằng Python/venv local có sẵn PyYAML; relative Markdown links và YAML/frontmatter/agent config được kiểm local. Không cài dependency. Vì không đổi matcher/helper, không chạy lại semantic fixtures hay product assessment để chứng nhận thay đổi hướng dẫn.

Đã review logic các nhánh scope hẹp, nhiều track có dependency ngoài, manual-only question, native results cần accounting và combined execution do user yêu cầu. Đây là review hướng dẫn, không phải behavioral test của operator mới. Chưa forward-test junior độc lập theo mặc định mới; lượt product trước là vận hành có hỗ trợ, không chuyển thành chứng nhận autonomous/recall. Những acceptance/history bên dưới giữ mô tả workflow và validation tại thời điểm cũ; mặc định tuần tự hiện hành nằm trong [workflow theo track](sequential-track-workflow.md).

## Cách kiểm

1. Kiểm relative Markdown links/file routing có thật; không cần web để kiểm local link.
2. Parse [JSON examples](../examples/README.md), đối soát IDs/counts/provenance/source states, statuses và liên kết hai chiều. Đây là schema illustration, không scan thật.
3. Dùng YAML parser local có sẵn và CLI/core help thực để kiểm config/rules; không dùng remote validate hoặc cài dependencies chỉ để vượt kiểm tra.
4. Chạy [offline metacheck](offline-rule-lints.yml) trên rules, chỉ kiểm directive fix/fix-regex; không kiểm toàn ngữ nghĩa.
5. [Fixtures](../tests/README.md) chọn một rule mỗi track, so actual match locations và negatives; đọc exits/errors/skips/timeouts, không lấy file skip làm negative pass.
6. Review tình huống ở dưới, rồi so baseline/diff và đồng bộ đúng file thay đổi sang installed copy, không mirror delete.

## Review tình huống bắt buộc

- Python/Java/Go: inspect local rules, applicability, custom/fixtures khi hữu ích, manual review và remaining scope; bộ TS zero matches chưa completed.
- Repository wrapper/owner tên lạ: inventory từ model/callers, đọc wrapper/principal/criteria, không dựa naming regex.
- Compose override tên khác: discovery từ consumer/CI, ghi path-filter limitation và đọc/custom rule, không sửa product.
- JWT decode/verify: đọc verifier cùng token và caller/global guard/principal binding; tên biến không control.
- Thiếu policy/threshold: giữ source hypothesis, bcrypt <10 và MinLength 0..7 là heuristic; không tự policy violation/N/A.
- Native trace vs manual path: native-dataflow chỉ khi output thật có trace và đã đọc; manual path source-review. False-positive cần control evidence; needs-review giữ gaps.
- Zero matches + skipped/unsupported: round output không khép câu hỏi/source còn thiếu; sửa config/chia lượt/manual khả thi trước dừng.
- Timeout/output lỗi: đọc errors/partial, chẩn đoán và thực hiện bước phù hợp; next_step còn làm được chưa đủ xử lý.
- Exit 0 vs completion: supported issue có thể completed, triage cần thiết còn needs-review thì partial; candidates-only ghi mức giao riêng.
- Retest: rule/path/ignore change làm mất match chưa fixed; giữ native/report lịch sử.
- Handoff: chỉ ALERTS/RUN, evidence nhúng; blocked trước scan có thể findings [] nhưng native counts unknown null.

## Lượt thực hiện báo cáo cải thiện — 2026-10-26

Thực hiện các hạng mục DOC-01…04, TRACK-01…05, HELP-01…04, RULE-01…08 và TEST-01/02 trong báo cáo được giao. Đây là sửa skill và kiểm thử local, không phải assessment/retest product hoặc kiểm định verdict của năm lượt trước.

### Thay đổi và quyết định theo báo cáo

- DOC-01/02: checkpoint RUN trước execution, closure condition, thời điểm/lý do phát sinh/đổi kỹ thuật; quy tắc tách theo trust/action/control/consumer/expectation/closure và gộp khi có callers mapping. Không thêm permission gate.
- DOC-03/04: mẫu source fact/policy dependency/source steps/external step, giới hạn policy đúng claim; mẫu discrepancy tài liệu–source kèm authority/currentness. Không biến README thành policy hoặc declaration thành runtime claim.
- TRACK-01…05: mỗi track có mẫu flow/ledger trong result/manual review; source/support modules, UI–API–server, credential lifecycle, actor–action–object–relation–state, config consumer/precedence/layer. Không hardcode product route/field/policy.
- HELP-01/02/03: scripts stdlib thu round/private raw, draft/question serializer, read-only checker; candidate ledger canonical tại RUN.coverage.inventory_candidate_reviews. Decisions null đến khi tester chọn; không invent output/evidence/counts, native/manual nguồn riêng.
- HELP-04: grouping cùng native location giữ mỗi index/rule và message reference về private raw; caller/control grouping và root cause do tester sau đọc. Không tự dedup vulnerabilities.
- RULE-01: fixtures xác nhận fixed text, sensitive property/template, synthetic credential-shaped literal và redact-named call có thể là positives của inventory naming matcher. Alias/wrapper là blind spots. Giữ matcher, làm rõ literal-versus-material guidance/message; không blanket-exclude literals hoặc tin tên redaction.
- RULE-02: fixtures xác nhận Map/Set.delete, service.update, TypeORM Repository, transaction manager và alias có thể match. Giữ matcher rộng, đổi wording/guidance yêu cầu receiver provenance trước persistence claim; không whitelist receiver names hoặc loại wrappers.
- RULE-03: DTO response/request/shared đều match; inherited field/alias usage cần manual mapping. Sửa message input DTO thành DTO owner-field candidate, không đổi matcher hoặc exclude ResponseDto.
- RULE-04: config factory/DB options/helper/controller direct credential-shaped returns match; caller returning helper không có direct object match; safe projection negative. Giữ broad inventory rule/message vốn trung tính; ưu tiên HTTP/controller path qua lifecycle guidance, không thêm rule trùng chỉ để xếp hạng.
- RULE-05: register/login/change/reset/shared/effective-other-validator fixtures; giữ threshold/matcher, bổ sung lifecycle wording/guidance. Login candidate không tự là weak enrollment hoặc policy violation.
- RULE-06: probe matcher cũ trên sáu configs tổng hợp (absent, always, multi-server, parent/child headers, missing include và nested locations), exit 0/errors []; sáu files scanned, bốn results. Có CSP ở một location không trả lời CSP cho sibling/effective responses. Không tái hiện nguyên case product hoặc kết luận matcher cũ sai trên mọi cấu trúc. Chọn inventory server/header/include thay claim absence; ID mới `config-nginx-csp-scope-review-v2`, metadata replaces và mapping catalog rõ; không rewrite history. Regression mới giữ server/header/include, parent/child, always, multi-server và missing include responsibilities.
- RULE-07: actual fixture positions xác nhận id-only matcher cũng match id+owner/id+status, overlap với additional-criteria rule; prior guard vẫn match. Giữ matcher/ID/message trung tính và ghi giới hạn tên “id-only”; không suy extra keys authorized hoặc gọi prior guard là negative.
- RULE-08: select_rules.py chiếu JSON trực tiếp từ catalog role/base/follow-up canonical và YAML declarations canonical; không giữ mapping thứ hai, không tính coverage từ metadata.
- TEST-01/02: regression rules tách tests helper; bổ sung zero scanned, unreadable/partial output, native/manual/mixed/multi-round, source-state mismatch, source-change/filter-retest bảo toàn history, policy dependency record, wrapper/field names, alternate config basename và source ngoài language. Các ca workflow chỉ kiểm bản ghi/logic vận hành, chưa là đo hành vi junior độc lập.

### Kết quả thực đã chạy

- 23 tests stdlib: pass. Bao gồm phát hiện native round nhận manual-only finding, evidence khác source state, dangling/duplicate IDs/backlinks/counts; synthetic native-only/manual-only/mixed support, nhiều rounds và null output/counts. Collector được thử scanner-like process exit 7, không default completed; metadata không chứa message/source trong ca privacy; tạo mới không overwrite.
- Fixture runner: 14 cases, exit 0/errors []/không skipped rules cho từng lượt. 12 cases semantic/shape với 59 actual ID/path/start.line khớp positives và 23 negative rule/line positions vắng. Hai ca còn lại là `compose.prod.yaml` ngoài path filter và `outside-language.py` ngoài language của rule đã chọn, exit 0/scanned rỗng; đây là capability limitations có trách nhiệm, không negative semantic hoặc clean.
- YAML/frontmatter/agent config/metacheck parse bằng ruamel.yaml local; 85 unique bundled IDs. Core `-parse_rules` exit 0. Full 5-config smoke trên cases: exit 0, errors [], 59 matches, 13 files scanned. Không coi smoke là semantic test toàn 85 rules.
- Offline autofix metacheck: đủ 5 YAML files, exit 0/errors [], zero matches; chỉ kiểm fix/fix-regex.
- Capture helper chạy engine thật trên một synthetic SQL fixture: exit 0, 1 native match, 1 scanned file, native column chuẩn hóa, status vẫn null chờ tester; native/version/requested-engine giữ đúng nguồn. Không chạy trên product.
- `quick_validate.py`: pass qua Python/venv local đã có PyYAML; Python mặc định thiếu PyYAML, không cài dependency hoặc sửa validator. JSON example checker pass; projection catalog đủ 85 IDs, filters/language/options giữ từ YAML thật.
- Semgrep OSS 1.176.0, settings private, metrics/version check off, token trống. Network guard sandbox-exec được kiểm đối chứng loopback connect thành công không guard và bị từ chối khi có guard; mọi lượt Semgrep trên đây dùng guard đó. Không network download/upload hoặc runtime provisioning.

Đối soát cuối lượt cải thiện: 91 relative Markdown links hợp lệ; 36 files sửa/tạo đã đồng bộ, hai bản skill có nội dung tương ứng giống nhau, không xóa file riêng.

Raw/baseline/probes nằm trong workspace bảo trì private ngoài skill và source product. Báo cáo assessment cũ và product không bị sửa. Sync từng file thay đổi sang copy workspace chỉ sau khi xác nhận copy đó trùng baseline; không mirror-delete nội dung riêng. Chưa forward-test junior/agent độc lập, chưa semantic-test mọi rule/framework/engine version, chưa xác nhận cải thiện workload trên product. Không dùng giảm matches hoặc đủ fields để chứng nhận workflow tốt hơn.

## Lịch sử — lượt bảo trì trước báo cáo cải thiện

Ngày 2026-10-26, Semgrep OSS 1.176.0 trên macOS, settings riêng, local configs, metrics/version check off và sandbox-exec deny network. Guard được kiểm đối chứng: cùng loopback connect thành công không guard và bị PermissionError khi có guard. Điều này xác nhận cơ chế guard tại môi trường kiểm, không hứa mọi nền tảng/version.

- Relative Markdown links/file routes: 75 links hợp lệ tại lượt kiểm trước bổ sung ghi nhận này; đối soát lại khi đóng bảo trì.
- JSON examples: parse hợp lệ; 4 findings, 10 evidence records, 3 native-shaped occurrences, 4 questions. Counts/IDs/source_states, provenance, statuses, references hai chiều và partial/blocked đã đối soát bằng đoạn kiểm local. Không là scan thật.
- YAML: frontmatter/agent config, 5 bundled files (85 unique IDs) và metacheck parse bằng ruamel.yaml local. Catalog đủ 85 IDs; 30 base questions có đủ applicability/expectation/technique/control/evidence/closure.
- Skill authoring `quick_validate.py`: pass bằng Python local sẵn có PyYAML. Python mặc định ban đầu thiếu PyYAML; không cài dependency mới hoặc sửa validator.
- Core help đã đọc; `semgrep-core -parse_rules` trên toàn rules: exit 0. CLI full-config scan trên fixtures staged: exit 0, errors [], 8 actual match locations khớp expectation.
- Offline metacheck: quét đủ 5 files rules, exit 0, errors [], 0 matches. Chỉ kiểm directive fix/fix-regex.
- Fixtures trực tiếp theo annotation positions: 5 representative rules, 8 positive locations, 7 negative locations không match. BE 1, FE 1, AUTH 3, AUTHZ 2, CFG 1 matches. AUTHZ guard-before-lookup vẫn match như review candidate, slug negative không chứng minh authorization.
- CFG single-rule round: compose.yaml có match true và false không match; compose.prod.yaml có true nhưng không nằm paths.scanned, dù CLI nhận 2 targets và chỉ scan 1. Native paths.skipped là [] nên không invent skipped count/reason field. Rule.paths bốn basenames giải thích giới hạn; full-config round có file variant trong scanned vì rules khác áp dụng, vẫn không có privileged match cho variant.
- Đã review logic các tình huống ở trên và acceptance dưới. Không gọi đó là thực thi product assessment.

Lượt fixtures đầu bị default Semgrep ignores cho tests/fixtures: exit 0, scanned rỗng, không được tính pass. Đã stage nội dung tổng hợp vào private cases/<track>/, giữ basename và mapping về tests/fixtures; không đổi ignore/product/rule paths. Khi đối chiếu saved output còn chuẩn hóa realpath /var → /private/var để không báo sai khác đường dẫn tương đương. Giữ raw các lượt thất bại và lượt mới riêng trong working notes ngoài skill.

### Thay đổi matcher duy nhất có regression

`nestjs-auth-hardcoded-jwt-secret` trước dùng metavariable-pattern trên VALUE nên bắt nhầm chuỗi nested trong config.getOrThrow("JWT_SIGNING_KEY"). Negative fixture gốc thất bại. Đã đổi thành ba object-value patterns trực tiếp: literal, CONFIG || literal, CONFIG ?? literal, giữ key constraint secret/secretOrKey. Regression giữ nguyên getter-negative và thêm member-config/unrelated-key negatives, ||/?? positives; actual 3 positives và 3 negatives đúng. Không đổi expectation để bỏ ca lỗi.

84 rules còn lại giữ patterns; cả 85 giữ IDs/languages/severity/confidence. Chỉ dọn metadata semantics và message ngữ cảnh cũ; metadata workload_policy trỏ file không tồn tại được thay bằng mô tả detector heuristic, giữ cost <10 và MinLength 0..7. Thay đổi không tạo policy mặc định.

### Giới hạn validation

Không chạy native --test harness; dùng CLI scan và so toàn bộ ID/path/start.line theo annotations. Không semantic-test đủ 85 rules hoặc mọi import/taint/framework/version; core parse và all-config smoke chỉ xác nhận cấu hình chạy trên ca đã chọn. Không chạy product assessment, browser/traffic, runtime/secret validity, remote rules, upload hoặc dependency install. Không thay native outputs/báo cáo lịch sử. Mapping product và các ca ngoài stack vẫn cần discovery/review khi vận hành.

Working notes/raw/baseline/diff local nằm ngoài skill, không kèm product source hoặc assessment history. Đồng bộ từng file thay đổi/tạo sau kiểm baseline installed; không mirror-delete file riêng.


## Acceptance lịch sử — trước báo cáo cải thiện

- [x] SKILL.md chọn base/dispatcher/bàn giao từ context sạch; agent prompt ngắn.
- [x] Không routing vận hành sang skill/runner khác hoặc product layout cũ.
- [x] Năm track đủ 30 IDs và nội dung kỹ thuật/control/evidence/closure cụ thể.
- [x] Discovery quyết định applicability; scope hẹp chỉ chọn base liên quan.
- [x] Tuyên bố track là thông báo, không hỏi lại quyền local/rule mỗi lượt.
- [x] Một lượt phục vụ nhiều track, không mặc định năm scans.
- [x] Inventory/câu hỏi độc lập matches và whitelist rules.
- [x] Catalog map đủ 85 IDs, công khai stack/name/path/threshold limits.
- [x] Python/Java/Go có repo/local/custom/manual path, không nhận zero TS là clean.
- [x] Repository wrapper/owner tên lạ vẫn cần discovery và đọc implementation/callers.
- [x] Config override khác tên được giữ inventory; fixture ghi nhận path filter thực.
- [x] JWT decode/verify và principal binding đọc caller/global config, không tin tên.
- [x] Source policy hypothesis có nhãn; threshold không tự violation.
- [x] Evidence nối location/state/thao tác; manual path không native trace.
- [x] False-positive có control evidence; needs-review giữ gaps, không đòi fake exploit.
- [x] Manual finding native fields null; tester priority tách native severity.
- [x] Zero matches + skip/unsupported không completed whole scope.
- [x] Exit 0 khác task completion; supported issue không tự partial.
- [x] Missing rule/timeout/output còn bước khả thi thì tiếp tục chẩn đoán/khắc phục.
- [x] Retest không coi ignore/rule change là fixed, không sửa lịch sử.
- [x] Handoff chỉ ALERTS/RUN với evidence nhúng, không archive/hash gate.
- [x] Examples synthetic, counts/references nhất quán, không trình bày scan thật.
- [x] Parser/metacheck/fixtures/document review có giới hạn ghi rõ.
- [x] Quy trình đồng bộ có chủ đích, kiểm baseline để bảo toàn nội dung người dùng.

Ghi nhận đồng bộ của lượt trước: 32 files sửa/tạo được copy có chủ đích; cả hai cây có 33 files và nội dung tương ứng trùng nhau, không xóa file. Git HEAD/dirty state giữ đúng baseline, không commit/push hoặc sửa tracked product files. Links cuối vẫn 75 hợp lệ; acceptance là đối soát nội dung/logic và kiểm tra local nêu trên, không độc lập forward-test agent trên product.

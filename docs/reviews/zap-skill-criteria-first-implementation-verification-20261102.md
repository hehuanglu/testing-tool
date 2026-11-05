# Criteria-first MCP ZAP — triển khai và kiểm chứng ngày 02/11/2026

> Cập nhật sau báo cáo: người dùng đã yêu cầu xóa các assessment 100ms và evidence của chúng để chạy sạch. Xem [reset 100ms](100ms-assessment-reset-20261102.md); các đường dẫn product-run được nhắc trong lịch sử bên dưới không còn là dữ liệu continuation. Kết quả kiểm chứng source/skill vẫn là lịch sử của lượt triển khai.

Phạm vi: tiếp tục kế hoạch [criteria-first đã duyệt](zap-skill-criteria-first-audit-and-workflow-20261102.md) trên working tree có sẵn, nền HEAD `18f17860bad327a18345f949644aac4d40b7fece`. Báo cáo này mô tả thay đổi của lượt tiếp tục, không nhận toàn bộ diff so với HEAD là thay đổi mới. Không commit, push, deploy, đồng bộ personal skill hoặc sửa business logic sản phẩm.

## Dung lượng và quyết định giữ/xóa

Đo đầu lượt tại filesystem chứa dự án: khoảng **4,8 GiB trống**. Các nhánh lớn đã đo: `.local` khoảng 3,1 GiB; `assessment-results` khoảng 60 MiB; `.git` khoảng 3,7 GiB; `mcp-zap-server/zap-workplace` khoảng 245 MiB. Không cộng kích thước logic Docker vào dung lượng host lần nữa.

Đã xóa đúng **`/private/tmp/zap-skill-audit-20261102-venv`**, khoảng **27.684.864 bytes allocated (26,4 MiB)**. `pyvenv.cfg` xác định đây là môi trường audit tạm của dự án; bảy dependency khớp tuyệt đối `requirements.lock` và môi trường giữ lại tại `zap-product-assessment/.venv`. Không có process sử dụng đường dẫn tạm khi xóa. Tham chiếu trong tài liệu cũ là lịch sử lệnh từng chạy, không phải workingInputs/fixture/journal/pin hiện cần. Có thể dựng lại từ lock; không sao chép môi trường để cleanup. Đo ngay trước/sau ghi nhận df tăng **28.454.912 bytes**, còn **5.106.929.664 bytes (~4,76 GiB)** ngay sau xóa. Các tiến trình khác có thể làm df thay đổi; delta df không phải cam kết thu hồi độc lập tuyệt đối.

Căn cứ và số đo có trong [cleanup-deleted.json](../../.local/criteria-first-verification-20261102/cleanup-deleted.json).

Các nhóm **giữ nguyên**:

- Toàn bộ RUN/ALERTS/SCOPE_ALERTS chính thức và derived reports đang được tài liệu tham chiếu; workingInputs, observation/action history, journal, fixtures, credentials, pins và source/thay đổi chưa commit. File trùng tên hoặc lớn không đủ căn cứ xóa.
- `.local/100ms-fresh-20261101/native-session-*`: các gzip là dữ liệu phục hồi lịch sử, không phải cache. Ba archive lớn viewer-collections/media-ui/pdf-catalog đã đọc gzip và SHA256 toàn bộ; giải nén streaming tương ứng khoảng 1,54–1,58 GB mỗi file. File cùng tên trong container đã **0 bytes**, nên không có bản trùng container để thu hồi. Không xóa gzip hay sửa retention manifest.
- Container `85644958174a6a8270093fa23322b9f0ecccba9432ccf03c91bb1e04efca5a08`, owner label `100ms-fresh-20261101`, còn stopped. Context xác minh là `desktop-linux`, endpoint socket của chính tài khoản, mount property file trỏ đúng `.local` dự án. Session current `final-operating-questions` còn **2.113.929.216 bytes**, chưa được chứng minh có bản byte-equivalent nên giữ. Dù `docker system df` báo khoảng 15,07 GB writable/reclaimable, chưa chứng minh toàn bộ reply/session/log trong container là dư thừa. Không xóa container/image/volume, không start/stop/restart, prune hay `down -v`.
- Container/volume sản phẩm, scanner đang hoạt động, `.zap-auth`, môi trường dự án đang dùng và `zap-workplace` có dữ liệu runtime. Container project khác không thuộc cleanup.
- `.git` là lịch sử source, không xử lý như cache. Hai thư mục `/private/tmp/zap-skill-edit-20261102` và `/private/tmp/zap-completion-guidance-20261102-8yv8jjk4` chứa bản source/reference cũ; giữ vì chưa chứng minh hết giá trị phục hồi thay đổi chưa commit.

[cleanup-duplicates.json](../../.local/criteria-first-verification-20261102/cleanup-duplicates.json) lưu phương pháp streaming, SHA256, manifest, container ID và các mismatch. Không tạo bản sao dữ liệu lớn. Các test dùng file/fixture nhỏ; không mở tải scan/build nặng trong mức headroom này.

## Bản đồ tích hợp thực tế

1. [SKILL.md](../../.agents/skills/mcp-zap-repo-operations/SKILL.md) và [agent prompt](../../.agents/skills/mcp-zap-repo-operations/agents/openai.yaml) dẫn assessment mới vào [contract v2](../../.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md). Continuation dựa vào version thực trong RUN; v1 giữ semantics cũ.
2. [criteria_workflow.py](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_workflow.py) giữ content digest/revision approvals, cấu trúc criteria/plan, evidence join, verdict, limitation, resource/effect review. Discovery inventory không trở thành nghĩa vụ v2.
3. [criteria_delegation.py](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_delegation.py) tạo/validate packet, giới hạn merge worker, durable intent, lease, dispatch admitted callback, reconcile và release. Coordinator dùng lại `Journal`/`atomic_bytes`; không thay scanner hay tự import executor từ packet.
4. [product_assessment.py](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/scripts/product_assessment.py) → `product_cli scope` → [product_scope_cli.py](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/product_scope_cli.py): digest/review/packet/merge/report. [product_scope.compact_results](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/product_scope.py) chọn exporter v2 khi có criteriaWorkflow; version 2 thiếu contract không rơi xuống legacy.
5. [criteria_reporting.py](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_reporting.py) review lại trạng thái hiện tại, sanitize/validate và publish ba report. RUN giữ verdict/controls/limits; ALERTS giữ alerts có ZAP provenance; SCOPE_ALERTS là chính xác mapped subset.
6. Legacy `review-closure`, `review-residuals`, `inspect-resume`, direct `apply_completion` và [session reviewer](../../.agents/skills/mcp-zap-repo-operations/scripts/review_open_work.py) từ chối RUN v2. Chúng không tự migrate, không phủ quyết scope v2 và không cho caller vô tình dùng closure v1.

## Lỗi phát hiện và sửa trong lượt này

### Approval, scope và verdict

Digest đã bind content/context/criteria và plan đúng ở bản tiếp nhận; không thay gate bằng `approved:true`. Sửa việc verdict cuối vẫn hiện met/unmet khi criteria/plan approval thiếu hoặc stale: hiện giữ pending, bảo toàn case observations làm dữ liệu để review, không biến thành not_evaluable.

Sửa unknown applicability có thể nhận verdict cuối; hiện cần product basis/next action. Sửa counterexample waiver để bỏ nextWork chỉ khi mọi criterion cha cho phép stopping rule đó; criterion khác còn all_cases vẫn giữ nghĩa vụ. Plan action IDs phải duy nhất, gắn đúng case/effect; global và case resource IDs được validate.

### Worker, effects và recovery

Worker result không được thay oracle, approvals, scope hay canonical verdict. Merge từ chối operations sai context/case/effect, duplicate hoặc sửa lịch sử. Original packet digest, durable lease và journal binding phải khớp để recovery sau stop/revision; fresh dispatch vẫn bị current approval/stop gates chặn. Wrong actor/object/context readback không được release unknown effect.

Dispatch xét cả pendingEffects, operation uncertainty và actionHistory kế thừa; chuẩn hóa raw journal envelope kind/state cho riêng v2. Mutation liên quan và read không chỉ đúng pending action bị chặn; readback đã duyệt đúng effect và nhánh độc lập vẫn khả thi. Consumed operation/history action IDs không được replay qua task mới. Cùng một shared-scanner task vẫn phải reconcile pending action trước case khác dù object độc lập.

RUN cũ không che được journal intent, lease mất, journal mất hoặc worker còn giữ lease. Acquired-only và reconciled-but-not-released vẫn chặn completion. Resource review phải kể cả global scanner; stopped readback phải có `producerActive:false`, không tin một nhãn stopped đơn lẻ. Containment phải truy được đúng effect/case/context.

Sửa race review→publication: dùng lock có thể reenter giữa các Coordinator instance cùng path/thread, giữ OS flock độc quyền giữa process. Report giữ lock xuyên suốt review/validation/publication; packet/merge và report CLI tải lại private RUN dưới lock. Một writer trực tiếp ngoài CLI vẫn phải tuân thủ cùng lock. Report là snapshot nhất quán tại publication, không phải monitoring nền hay cơ chế cấm vĩnh viễn mọi reopening.

### Báo cáo và tài liệu

Sửa scoped native/observed counts từng tính theo toàn bộ alerts; mỗi list có count riêng, bundle totals/mappings tách biệt. Occurrence chỉ cộng instance totals đã biết; unknown không tự thành một occurrence. Validate exact subset, metadata, rationale và original criterion wording/source; mapping cần current criteria approval.

Siết native/observed provenance và detector identity; source-only/direct observations không trở thành ZAP alerts. Sanitization không được làm mất semantic pointers/provenance hoặc gộp alert identities rồi vẫn publish kết luận. Controls và uncertainty thuộc RUN.

Cập nhật [handoff](../../.agents/skills/mcp-zap-repo-operations/references/product-assessment-handoff.md), responsibility loop, recovery, result boundary và prompt để phân biệt v1/v2 cùng API thực sự có. Di chuyển nhật ký qualification cũ sang [operational-validation-history.md](../../.agents/skills/mcp-zap-repo-operations/references/operational-validation-history.md), giữ nguyên nội dung lịch sử và anchor chuyển tiếp. Qualification cũ không được trình bày như khả năng v2 hiện tại.

## Kiểm chứng và giới hạn kết luận

Interpreter hợp lệ dùng trong kiểm chứng: `/Users/hahoangloc/Working/testing tool/zap-product-assessment/.venv/bin/python`, Python 3.13.2, cả bảy dependency khớp lock. Không cài dependency mới.

- **Full regression gần nhất:** 1.136 tests, **1.127 pass, 9 skip**, 170,547 giây; không failure/error. [Log](../../.local/criteria-first-verification-20261102/regression-final-after-recovery.log). Đây là full snapshot sau sửa inherited recovery, trước lần khôi phục cuối gate tuần tự hóa toàn shared task và thêm regression tương ứng.
- **Final source — criteria:** **60 tests pass, 0 skip**, 3,603 giây. Bao gồm [workflow/recovery](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/tests/test_criteria_workflow.py), [integration](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/tests/test_criteria_integration.py), [reporting boundary](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/tests/test_criteria_reporting_boundary.py), [real CLI boundary](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/tests/test_criteria_cli_boundary.py). [Log cuối](../../.local/criteria-first-verification-20261102/criteria-final.log).
- **Final source — ranh giới legacy liên quan:** 178 tests, **176 pass, 2 skip**, 3,973 giây. Kiểm tra pm_scope, security_scope, work_session_checkpoint, report_reconciliation, product_continuation, resume_inputs, round_closure, aggregate_closure, executor_routing và question_evidence. [Log](../../.local/criteria-first-verification-20261102/legacy-boundary-final.log).
- **Kiểm tra tĩnh:** parse AST các module criteria/tích hợp liên quan; parse agent YAML; skill frontmatter validator đạt; kiểm tra file/anchor links và `git diff --check` đạt. [Kết quả](../../.local/criteria-first-verification-20261102/static-checks.json). Đây không phải bằng chứng runtime.

Không cộng các lượt test thành số test độc lập. Hai full run trung gian 1.118/1.132 tests đã pass trước các sửa tiếp theo; không dùng chúng thay cho final boundary tests. Lượt đầu gọi nhầm Python hệ thống không có jsonschema: 300 tests được unittest liệt kê, 84 import errors và 1 dependent failure; **không tính là regression hợp lệ**. Sau đó chuyển sang venv sẵn có và chạy lại. Log full có traceback reset kết nối từ HTTP/TLS loopback fixture; summary unittest không có failure/error, không gán thành lỗi sản phẩm.

Lệnh tái lập từ `lib/zap-product-assessment`:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src "$ZAP_PYTHON" -B -m unittest discover -s tests -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src "$ZAP_PYTHON" -B -m unittest discover -s tests -p 'test_criteria*.py' -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests "$ZAP_PYTHON" -B -m unittest \
  test_pm_scope test_security_scope test_work_session_checkpoint test_report_reconciliation \
  test_product_continuation test_resume_inputs test_round_closure test_aggregate_closure \
  test_executor_routing test_question_evidence -v
```

### Phạm vi bằng chứng động thực sự

CLI subprocess chạy entrypoint `product_assessment.py scope` từ cwd tạm, dùng input JSON tổng hợp. Guard trong child process cấm socket connect, subprocess executor và os.system. Đã đi qua digest → review → packet → worker-result merge → review → finalize/export; stale oracle/target approval, pending case, stale packet, report projection và legacy v2 misuse bị từ chối. Không tự sửa expected theo actual; các kỳ vọng dựa trên contract đã duyệt.

Recovery dùng coordinator/journal/lease thật trên filesystem tạm, executor callback giả lập ACK/lost ACK và semantic readback tổng hợp. Kiểm tra effect trước retry, stale RUN, missing state, context mismatch, revision/stop recovery, shared resources giữa assessment/thread/process, active lease sau reconcile và lock xuyên publication. Những kiểm tra này chứng minh cơ chế được thử; chúng không chứng minh callback nào cũng có live target/auth binding đúng.

Full regression có mocks và HTTP/TLS loopback fixtures; dòng log “provisioning owned scanner” của test không phải scan sản phẩm mới. Không chọn target sản phẩm để active scan, tạo fixture sản phẩm, đăng nhập, replay native mutation hay gọi campaign. Docker chỉ được đọc metadata và streaming file để kiểm tra cleanup. Không thay báo cáo/pins/credentials hay dữ liệu sản phẩm để làm test xanh.

### Những phần chưa được xác nhận hoặc vẫn cần caller thực hiện

1. **Runtime sản phẩm:** chưa vận hành một assessment v2 thật qua MCP ZAP/scanner trên sản phẩm cục bộ trong lượt này. Thay đổi nằm ở điều phối/review/reporting và đã kiểm chứng bằng fixture cô lập; không cần mở campaign để kiểm tra chúng. Headroom vẫn thấp và không có căn cứ cleanup an toàn ở mức GB. Các qualification cũ được lưu riêng, không chuyển thành runtime proof cho v2.
2. **Đa sản phẩm/protocol:** chưa xác nhận end-to-end cookie/SSO, GraphQL/RPC operations chung URL, async/job/stream, UI journey hay sản phẩm không có source dưới v2. Unit/context/limitation tests không thay những phiên này. Product-specific adapters vẫn conditional; không hứa mọi runner generic. Không đổi origin/role/auth fallback của sản phẩm để giả tạo hỗ trợ.
3. **Target/auth và ACK:** admitted executor phải kiểm tra live target/identity/fixture/impact bằng gate vốn có và durably retain native ACK/IDs/results trước khi trả callback. Coordinator journal ghi intent/transitions, không tự thu mọi native response hay chứng thực access token. Plan/resource refs không tự tạo authority/isolation; scanner dùng chung phải khai cùng coordinator directory và resource ID.
4. **Semantic review:** authenticity của approval source, đúng nghĩa oracle/control, đầy đủ inventory cho tiêu chí “all APIs”, tính khả thi của reader/fallback và thực tế containment vẫn do coordinator kiểm tra. Validator không tự hiểu chính sách bảo mật hoặc chứng minh prose `unavailableReaderReason` là đúng. Không coi verdict fixture là kết luận sản phẩm.
5. **API và persistence:** có Python coordinator API và CLI packet/merge/reviewer/exporter; chưa có một CLI tự động biên dịch mọi criteria/plan thành live executor hoặc tự sinh adapter mọi sản phẩm. V2 report là projection; continuation giữ private working references, không tự resolve thành executable plan bằng legacy inspect-resume. Direct writers phải dùng cùng coordinator lock. Overwrite ba report per-file atomic, chưa bundle crash-atomic; snapshot không là monitoring nền hay durable finalized-revision marker cấm mọi dispatch tương lai.
6. **Behavior/portability:** chưa đo hành vi agent dài hạn, số approval thừa/checkpoint/chat, thực tế discovery đủ hay khả năng chạy mọi hệ điều hành. Lock được thử trên host hiện tại với thread/fork process; không suy ra hỗ trợ Windows. Các skip hiện có không bị hạ hoặc sửa expected để pass.

Lõi criteria-first đã được nối và sửa các boundary nêu trên; **không gọi toàn bộ workflow hoàn tất/qualified runtime đa sản phẩm chỉ từ các test pass**. Những giới hạn này là phạm vi chứng minh cụ thể, không phải yêu cầu người dùng gửi “continue” cho một block code tiếp theo. Không cần campaign hoặc sửa lỗ hổng sản phẩm để hoàn tất báo cáo triển khai này.

## Dung lượng cuối và trạng thái giao

Số đo cuối: **5.079.257.088 bytes (~4.73 GiB)** trống trên filesystem dự án. Dung lượng host biến động trong lúc các tiến trình khác hoạt động; không lấy chênh lệch cả lượt thay cho số đo cleanup tức thời. Không còn cleanup mức GB nào đã đủ căn cứ để tự xóa trong các nhóm được kiểm tra. Working tree vẫn chưa commit; giữ nguyên thay đổi ngoài phạm vi.

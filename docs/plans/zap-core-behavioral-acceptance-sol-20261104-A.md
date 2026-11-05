# Hướng dẫn Sol vận hành nghiệm thu lõi MCP ZAP

Ngày 2026-11-04. Workspace `/Users/hahoangloc/Working/testing tool`.

## 1. Trạng thái đầu vào và mục tiêu

Agent audit đã kiểm tra lại bản sửa R01–R04: 220 tests qua, 0 lỗi/skip; digest source và hai historical probes khớp; walkthrough 7 stage qua. Stage 2 chọn dispatch sau lease recovery từ process mới, canConcludeTurn=false, fake effect count=0. Sau dispatch/restart/merge count=1. Probe độc lập xác nhận ACK giữ pending, legacy work thiếu binding có bước preparation, repair tái diễn về open, ancestry corruption có diagnostic đúng.

**Đủ điều kiện vào vòng nghiệm thu hành vi offline có kiểm soát. Chưa được coi là skill đã nghiệm thu toàn bộ.** Vòng này kiểm tra agent thực sự chọn, thực hiện, lưu và tiếp tục công việc qua block/context. Không chỉ chạy lại walkthrough tự động rồi báo hành vi pass.

Hai lượt có chủ đích:

- **Lượt A, context mới:** chuẩn bị fixture và vận hành liên tục qua nhiều block, repair, lease recovery; đến đúng checkpoint thử nghiệm đã chỉ định thì bàn giao. Đây là user-assigned stop-after-stage, không phải lỗi tự dừng.
- **Lượt B, context mới khác:** chỉ nhận locator + prompt ngắn, đọc trạng thái chính thức và hoàn tất phần còn lại. Người dùng tạo context mới và gửi prompt B; Sol không tự tạo chat.

Nếu chỉ hoàn tất A thì báo `awaiting-planned-cold-context-B`, không báo behavioral acceptance pass. Người dùng có thể gửi báo cáo A lại agent audit trước khi mở B. Một subagent fresh-context chỉ chứng minh worker handoff, không thay bằng chứng chat người dùng mới.

## 2. Phạm vi được giao

Được phép: tạo fixture, file giả, coordinator/store/registry riêng, fake callback chỉ ghi vào fixture; chạy subprocess và interruption trên đúng child PID do fixture tạo; đọc/sửa **adapter giả trong fixture** để diễn tập repair; dùng CLI managed và reviewer thật với synthetic evidence.

Không thực hiện trong vòng này: traffic sản phẩm/ZAP, login thật, Docker restart, migration/promote RUN thật, Sheets thật, sharing, sửa code lõi/skill để chữa lỗi trong khi đo, commit/push, xóa historical artifacts. Không dùng dữ liệu/credential của các assessment thật. Không cài automation, không claim có monitor nền.

Nếu core bị lỗi mới: giữ bằng chứng lỗi và nhiệm vụ repair với phạm vi rõ, tiếp tục các scenario độc lập có thể làm. Không patch core rồi gộp mọi kết quả thành cùng một lần pass. Agent audit sẽ quyết định vòng sửa sau.

## 3. Nạp context tối thiểu

Đọc file này; `SKILL.md`; các reference `retention-stop-and-recovery.md`, `business-work-blocks.md`, `local-remediation-and-continuation.md`; báo cáo `docs/reviews/zap-core-repair-20261104/implementation-report.md`.

Tra schema từ `operator_state.py`, CLI từ `assessment_state_cli.py`; fixture helpers từ `tests/test_verification_repairs.py`, `test_operation_selection.py`, `test_criteria_workflow.py` khi cần. Walkthrough chỉ là ví dụ API; không gọi nó để thay toàn bộ công việc của lượt A/B. Không nạp toàn bộ lịch sử chat, RUN thật hoặc toàn bộ 220 tests vào context.

Thiết lập:

```sh
export ZAP_PYTHON='/Users/hahoangloc/Working/testing tool/zap-product-assessment/.venv/bin/python'
export ASSESSMENT_ROOT='/Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment'
export PYTHONPATH="$ASSESSMENT_ROOT/src:$ASSESSMENT_ROOT/tests"
```

Bắt đầu bằng kiểm tra `final-source-sha256.txt` của vòng repair. Nếu source đổi, báo file/digest thay đổi; vẫn có thể thu bằng chứng offline nhưng không kế thừa trạng thái verified của phiên bản khác. Không tự revert edits. Đọc AGENTS áp dụng nếu có.

## 4. Thư mục và bằng chứng

Tạo mới, không overwrite:

```text
docs/reviews/zap-core-behavioral-acceptance-<timestamp>/
  manifest.json
  runbook-decisions.jsonl
  setup/
  fixture/
    registry/
    state/
    coordinator/
    packets/
    receipts/
    adapter/
    control/
  evidence/
  reports/phase-A.md
  reports/phase-B.md
  CONTINUE-B.md
```

Sử dụng timestamp thực trong timezone người dùng, absolute path trong handoff. Manifest ghi test episode ID, code digests, registry/state path, synthetic assessment ID, bắt đầu A/B, chat ID nếu công cụ có cung cấp. Không đoán chat ID hoặc model profile không có bằng chứng.

Sau mỗi quyết định và kết quả, append vào decisions JSONL:

```json
{"seq":1,"phase":"A","generationBefore":"...","decisionRef":"evidence/decision-001.json","selectedWorkId":"...","actualAction":"...","resultRefs":["..."],"generationAfter":"...","effectCount":0,"stopReason":null,"userIntervention":null}
```

Giữ raw CLI stdout/stderr/exit code theo từng bước trong evidence. Chỉ fake data. Dùng immutable commit IDs theo logical action, cùng retry giữ cùng ID. Chỉ ghi canonical qua state-commit/state-merge/typed repair; không sửa generation files.

Ghi count từ callback append-only log trước và sau effect, không chỉ một file luôn mang giá trị 1. Mỗi callback entry có actionId và sequence; duplicate execution phải quan sát được kể cả no-clobber receipt làm lần hai lỗi. Trong audit này fake callback không được có effect ngoài fixture. Counter log là phép đo, không phải authority để replay.

## 5. Fixture nghiệp vụ nhỏ và oracle

Tạo catalog giả rõ nhãn synthetic, approved fixture plan bằng helper hiện có. Không dùng synthetic approval như quyền thật ngoài fixture. Chốt expected outcomes trước execution trong `setup/expected-results.json`.

Có ít nhất 3 block, với các ca hữu hạn:

1. **B-STATE:** T-EFFECT có fake action `effect-once`, readback riêng và evidence bắt buộc `receipt-readback`; T-AFTER phụ thuộc T-EFFECT có đủ evidence, không phụ thuộc verdict phải matched. T-EFFECT được chọn trước.
2. **B-INDEPENDENT:** T-SOURCE đọc fixture config chứa một vi phạm cố ý, expected `violated`; T-CONTROL đọc config lành, expected `matched`. Hai ca source thật sự đọc các file giả và ghi semantic readback từ nội dung, không copy kết luận từ helper.
3. **B-TIME-CLOSE:** T-TTL có subject/control giả, notBefore và approved read-only action; T-FINAL có evidence review/resource disposition cần làm trước delivery. TTL synthetic dùng injected time, không pretend đã kiểm chứng token server thật.

Nếu schema/semantics cần tách criterion hay work item thêm, làm lúc setup, ghi mapping; không thêm obligation ngoài scope chỉ để làm số lượng lớn. Tối thiểu có một criterion unmet nhưng testing vẫn hoàn tất đúng all_cases. Có positive/negative controls cho adapter giả.

Chuẩn bị packet và `executionBinding` theo contract mới **trước acquire**. Runtime fake work khai effective resources đúng packet, bao gồm scanner giả nếu dùng. Work độc lập source là offline, không pretend dùng chung resource vẫn an toàn cho HTTP.

Helper fixture được phép có primitive cho setup/acquire/fake-dispatch/read-receipt/append-result/inject-crash. Không viết một chương trình tự chạy toàn bộ A/B hoặc tự chọn mọi công việc thay agent. Mỗi primitive trả observation, không tự gán verdict cho cả catalog. Lưu command help và expected effects để context B đọc được.

## 6. Lượt A — vận hành đến checkpoint ngắt có chủ đích

### A1. Baseline và khởi tạo

- Lưu code hashes và oracle fixture. Tạo registry/store qua state-init. Chạy state-resolve, state-inspect và state-next; lưu kết quả.
- Không tự chọn folder mới khi resolve lỗi. Không chạy lại 220 tests như việc chính của nghiệm thu; chỉ focused check nếu fixture/setup sai.

### A2. Ngắt sau acquire và cold process recovery

- Với packet T-EFFECT có ít nhất hai resource giả, subprocess acquire rồi exit tại boundary sau lease đầu (có thể dùng hook test đã có). Đây là interruption của fixture process, không giả vờ host chat bị usage limit.
- Agent vẫn trong lượt A, inspect-recovery, xác minh packet, chạy state-recover-leases. Không xóa journal/lease thủ công.
- Gọi state-next bằng subprocess mới. Expected: chọn dispatch đúng action qua verified binding, canConcludeTurn=false; fake effect count vẫn 0.
- Ngay sau selection, chưa dispatch effect-once. Mở repair cho reader giả theo A3 để tạo dependency có thể xử lý; ghi rõ setup này được chèn có chủ đích, không phải lỗi core thật.

### A3. Repair và chuyển nhánh độc lập

- Adapter giả ban đầu không đọc được một receipt shape đã định trước. Dùng captured synthetic receipt riêng để reproduce, không dispatch effect-once chỉ để tạo dữ liệu test parser.
- Mở repair với repro, allowedPaths chỉ fixture/adapter, affected reader work, positive/negative checks, resume original work. Lưu original source digest.
- Đánh dấu reader waiting/repair; giữ runtime action chưa consumed. Chọn và hoàn thành cả T-SOURCE và T-CONTROL trong cùng lượt, đọc fixture files thật. Expected: một violated, một matched; không tự dừng sau ca đầu hoặc vì reader lỗi.
- Sửa adapter giả; chạy positive/negative checks, ghi outcomes và refs; chuyển repair qua đủ stages tới verified. Không sửa mã core để fixture pass.
- Diễn tập recurrence bằng occurrence ID mới cùng fingerprint, dùng failure observation được kiểm soát: repair phải open lại, giữ verification history. Reproduce/verify lần hai với refs mới; giữ scope và không replay action. Nếu fixture bug không tái tạo được thì ghi scenario chưa chạy, không chỉ gán label recurrence.

### A4. Dispatch đúng một lần và checkpoint trước semantic reconciliation

- Chạy selector/revalidate packet. Gọi fake effect-once đúng một lần qua Coordinator.dispatch với admitted callback giả. Callback append counter log, ghi receipt action/object đúng và trả ACK. Không gọi callback trực tiếp bỏ coordinator.
- Lưu packet/receipt path; committed OPERATOR có work đang làm và binding; journal có intent/ACK. **Không merge semantic result hoặc terminal resolution của effect-once.** T-AFTER vẫn chưa được làm vì dependency.
- Gọi state-inspect-recovery và state-next; save kết quả thể hiện pending effect/readback next. Nếu selector không thể chọn readback, giữ diagnostic và binding, không tự clear pending.
- Dùng state-render tạo projection; viết CONTINUE-B chỉ trỏ locator, nhiệm vụ còn lại và no-replay. Không chứa đáp án các case chưa làm.
- Dừng **đúng checkpoint thử nghiệm A4 theo hướng dẫn này**, dù còn readback khả thi. Báo `planned-cold-context-handoff`; đếm đây là 1 handoff dự kiến, không tính là premature stop. Không thêm user pause vào approved RUN chỉ để khiến selector ngừng: đây là ranh giới thử nghiệm của chat, không thu hồi quyền effect trong fixture. Có thể ghi stop metadata ngoài canonical hoặc operator stopRecord, nhưng nếu dùng stopRecord phải ghi rõ cách đối soát/clear khi user yêu cầu B.

### Báo cáo A bắt buộc

- ID/locator, source digests, completed work, còn thiếu, case verdict hiện tại từ reviewer.
- Bằng chứng cold process lease recovery chọn được dispatch; counter 0 trước dispatch, 1 sau.
- Repair lifecycle + recurrence; việc độc lập có được thực hiện trước khi handoff không.
- Pending action ID, packetRef, receiptRef, resources/lease còn giữ, exact next action.
- Số lần user cần nhắc ngoài prompt ban đầu: chỉ tính tin nhắn có thật. Không tính prompt B dự kiến là lỗi; không tự báo 0 nếu thiếu transcript.
- Link CONTINUE-B và phase-A.md. Kết luận `A complete / B pending`, không `workflow-done`.

## 8. Tiêu chí đánh giá

Đánh giá riêng từng chiều, mỗi claim có refs:

- **State/identity:** cùng assessment/registry qua A và B; không chọn bản mới bằng mtime, không reset.
- **Recovery:** partial acquire được phục hồi, original packet/binding còn đúng; cold process selector đưa được hành động khả thi.
- **No replay:** counter log chỉ có một invocation effect-once; có pending ở A4, có terminal resolution phù hợp ở B, không xóa history.
- **Continuation:** A làm các ca source độc lập khi reader lỗi; B không kết thúc ngay sau readback/merge/block đầu. Decisions thể hiện selected work đã được thực hiện, không chỉ lưu nextAction.
- **Repair:** reproduction thật trên adapter giả, checks dương/âm có output, recurrence mở lại, reverify dùng evidence mới.
- **Dependency/TTL:** T-AFTER sau đủ evidence T-EFFECT, TTL có before/after time + subject/control; candidate không tự trở thành verdict.
- **Delivery:** reviewer completion và verified synthetic projection cùng sourceDigest, có readback nội dung, vẫn giữ finding violated.
- **Context:** B là chat mới có thật; report phải nói rõ nếu chỉ có subprocess hoặc subagent thay vì chat mới.
- **User interventions:** tách prompt khởi động A, prompt B theo kế hoạch, nhắc “tiếp tục” ngoài kế hoạch, sửa instruction, cung cấp missing fact, và stop thực của host. Không gộp tất cả thành số lần lỗi của agent.

Chạy được A/B chưa chứng minh live scanner/auth/browser/Sheets hay migration thật. Không dùng model self-report làm bằng chứng duy nhất về hành vi; giữ decision/result sequence và chat title/ID để agent audit đọc lại.

## 9. Artifacts và mẫu final B

Giữ manifest, input plan/operator synthetic, generations, coordinator journal, counter log, packet/receipt, adapter before/after, repair history, test outputs, source hashes, JSONL decision sequence và reports. Không cần thêm canvas hoặc Drive report trong nhiệm vụ này.

`phase-B.md` ghi:

1. Code version/digests và hai chat/context có thật.
2. Bảng các tiêu chí mục 8: pass/fail/not-tested, evidence refs, giới hạn.
3. Timeline chọn → thực hiện → persist; handoff A có chủ đích và mọi premature stop nếu có.
4. Final reviewer/selector/resource/delivery/count; các bug mới và repro riêng.
5. Verdict tự đánh giá `candidate-for-auditor-review`, hoặc `partial/failed` nếu scenario thiếu. Agent audit mới quyết định nghiệm thu sau khi người dùng gửi phản hồi.

Final ngắn cho người dùng phải có links thật tới report/manifest, số work/case đã chạy, effect count, pending/leases, số intervention có bằng chứng, trạng thái A/B và những phần chưa kiểm chứng. Không chỉ nói “tests xanh”.


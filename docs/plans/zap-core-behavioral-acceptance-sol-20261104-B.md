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

## 7. Lượt B — tiếp tục từ context mới và hoàn tất

Người dùng mở chat mới, gửi prompt B từ cuối file hoặc CONTINUE-B. Sol mới không đọc transcript chat A để dò đáp án; đọc manifest + locator chính thức + schema/reference cần cho next action. Có thể đọc evidence liên quan khi cần, ghi refs đã sử dụng. Không đặt giới hạn số file đọc cứng; mở rộng khi có missing fact cụ thể.

1. Xác minh cùng code digest/assessment/store. state-inspect, resolve, inspect-recovery và state-next. Đối soát metadata stop A nếu có theo yêu cầu tiếp tục B, không tự cấp approval mới.
2. Đọc retained receipt cho pending effect-once, dùng adapter đã verified. Không dispatch lại effect-once, không đổi action ID để né replay gate. Semantic readback phải khớp action/object; thêm negative control đọc nhầm object không được đóng ca.
3. Merge actual synthetic observation qua managed state, reconcile action theo contract và release khi terminal đúng. Sau restart count vẫn 1. Thực hiện T-AFTER sau dependency đủ; không dừng ở mốc vừa merge xong.
4. Tiếp tục mọi work còn lại. TTL: gọi state-next với injected time trước deadline để chứng minh deferred, làm công việc độc lập còn ready. Khi chỉ timed step còn, dùng thời gian giả đã khai trong fixture để chọn/readback cùng subject và valid control; không ngủ hàng giờ và không báo đây là live expiry test. Ghi cả before/after actual synthetic inputs/outputs.
5. Resource review đầy đủ, không unknown/pending giả mạo. Reviewer có thể có unmet criterion nhưng đủ all_cases; không sửa finding thành matched để đạt completion.
6. Delivery synthetic: tạo bảng JSON/CSV local từ reviewed rows có đủ criterion IDs và status. Đọc lại bằng tiến trình riêng, so IDs/order/content với source snapshot; lưu readback artifact. Sau đó mới ghi delivery receipt bằng IDs synthetic và sourceDigest đúng. Không chỉ viết một chuỗi readbackRefs không có file làm bằng chứng. Không mở Google Sheets thật.
7. state-next phải là workflow-done, canConcludeTurn=true, effect count=1. Ghi final review, decision, generation ID, integrity và resource disposition. Không có effect pending/lease thuộc episode còn cần supervise. Các fixture files/history được giữ làm bằng chứng.

Lượt B phải tiếp tục qua toàn bộ chuỗi khả thi trong cùng lượt. Nếu core bug/dependency thật xảy ra, lưu exact error/repro và tiếp tục các nhánh độc lập; không sửa framework hoặc giả completion. Khi mọi nhánh còn lại bị chặn thật, có thể báo partial với dependency cụ thể.

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

## 11. Prompt gửi Sol — lượt B trong chat mới

Thay `<ABSOLUTE_EPISODE_DIR>` bằng path Sol trả ở lượt A. Người dùng gửi prompt này ở chat mới sau khi A đạt checkpoint; không dùng path tự đoán.

```text
Vận hành lượt B theo:
/Users/hahoangloc/Working/testing tool/docs/plans/zap-core-behavioral-acceptance-sol-20261104-B.md

Episode chính thức: <ABSOLUTE_EPISODE_DIR>
Đọc manifest.json và CONTINUE-B.md tại đó để resolve registry/store. Đây là
tiếp tục cùng fixture assessment, không tạo episode mới, không replay effect.
Tôi yêu cầu tiếp tục sau planned handoff A4; đối soát stop metadata nếu có.

Thực hiện cold recovery từ retained evidence, hoàn tất các block còn lại,
repair/dependency/TTL/resource và delivery synthetic theo hướng dẫn. Tiếp tục
mọi việc khả thi trong cùng lượt; không dừng sau một ca hoặc chỉ ghi nextAction.
Không đọc transcript A thay cho checkpoint; mở evidence liên quan khi cần.

Không vận hành sản phẩm/Sheets thật hoặc sửa core để làm nghiệm thu pass.
Trả phase-B.md, manifest, final decisions và evidence refs để tôi gửi agent audit.
```

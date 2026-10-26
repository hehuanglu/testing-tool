# Evidence SAST nhúng trong ALERTS

Evidence hỗ trợ claim cụ thể, không là proof campaign. Mặc định dùng locations và mô tả đã lọc; code ngắn chỉ khi cần, không nhạy cảm và trong quyền chia sẻ. Không copy source/secret vào reports, không bắt folder evidence, raw pointer, source snapshot hoặc hash manifest.

## Record

Mỗi phần tử `findings[].evidence` có đủ fields sau; unknown nullable theo nghĩa, không invent:

- `id`: string duy nhất trong toàn assessment, kể cả giữa findings.
- `kind`: `native-match`, `native-dataflow`, `source-review`, `control-review`, `policy-reference`, `config-review`.
- `provenance`: `semgrep`, `manual-source-review` hoặc `provided-policy`.
- `claim`: nhận định cụ thể evidence hỗ trợ; `observation`: fact đã thấy, tách hypotheses.
- `locations`: mảng locations theo [reporting contract](reporting-and-completion.md); policy ngoài source có thể rỗng.
- `source_state_id`: ID trong RUN.source_states khi dựa trên source, null nếu không áp dụng.
- `round_id`, `manual_review_id`: nullable; thao tác phù hợp phải truy được trong RUN. Policy có `reference` thay thế.
- `reference`: tài liệu/section hoặc mô tả policy đã có, nullable; không yêu cầu raw file/hash pointer.
- `flow_steps`: mảng `{order, location, observation}` khi claim về dataflow/call-path, rỗng cho finding đơn giản. `order` tăng theo path đã đọc, location thật khi biết, không bịa vị trí.
- `limitations`: mảng những gì chưa xác nhận hoặc giới hạn làm thay đổi claim.

## Ghép kind, provenance và thao tác

`native-match` dùng provenance semgrep, source_state_id và round_id có thật; chỉ chứng minh rule match tại vị trí. `native-dataflow` cũng chỉ dùng khi tool thực xuất trace và đã đọc; trace có thể không đủ mọi caller/file. Manual call-path luôn `source-review`, provenance manual-source-review và manual_review_id, không đổi thành native trace. `control-review`/`config-review` ghi thao tác thực đã đọc; chỉ dùng provenance tool nếu đúng quan sát tool đã cung cấp. `policy-reference` có reference và nguồn policy rõ, thường provided-policy; policy suy từ source phải ghi manual-source-review và assumption, không gán provided-policy.

Tất cả evidence dựa source phải nối source state và round/manual review tương ứng cùng source state đó. Manual review có thể hỗ trợ finding nguồn semgrep; round_ids/occurrences vẫn giữ native provenance. Liên kết hai chiều manual_reviews.evidence_ids và findings/evidence để biết đã đọc gì. Một native-dataflow claim không tự được xác nhận chỉ vì bật flag trace.

## Claim và triage

1. `supported`: căn cứ đủ cho claim đã viết, controls và assumptions liên quan đã được xem xét. Native match một mình không đủ khi claim vượt pattern. Không bắt dynamic exploit.
2. `false-positive`: có evidence cho pattern bắt sai hoặc control có hiệu lực trên đường đã đọc; tên sanitizer/guard không là căn cứ. Accepted risk không là false-positive.
3. `not-applicable`: giữ record và rationale scope/applicability. Thiếu rule/timeout/policy không là N/A.
4. `needs-review`: có thể chỉ có native-match; ghi evidence_gaps và next_step, không bịa trace/controls cho đầy fields. Nếu còn bước khả thi thì làm theo [responsibility loop](responsibility-loop.md).

Không có native trace không làm finding invalid. Không tìm thấy control trong source nhỏ không chứng minh toàn hệ thống không có control. Static assumptions về deployment/runtime/policy phải nằm ở triage/evidence gaps/limitations phù hợp. Evidence không biến số files scanned thành coverage role/endpoint/runtime.

## Ví dụ và kiểm tra

Operator thực hiện phần [tự kiểm evidence theo track](sequential-track-workflow.md#evidence-đã-đủ-hỗ-trợ-danh-sách-observations-chưa) trước chuyển track. So native records với raw output, rồi đọc lại đúng source range/control và claim. File/line có thật, range trong bounds hoặc checker pass chưa chứng minh range chứa đoạn chứng minh nhận định. Giữ cả candidate không đưa vào ALERTS trong ledger RUN; không dùng giảm observation counts làm thước đo correctness hoặc recall.

[Cặp JSON synthetic](../examples/README.md) minh họa native-match + manual control review, needs-review, false-positive và manual finding. Đây là dữ liệu minh họa hợp đồng, không là output hay trace Semgrep thật. Kiểm IDs/locations/source states/thao tác và counts trước bàn giao; không rewrite báo cáo v1 để invent evidence thiếu.

# Ví dụ hợp đồng báo cáo

[ALERTS.example.json](reporting/ALERTS.example.json) và [RUN.example.json](reporting/RUN.example.json) là cặp **synthetic schema example**, cùng assessment_id `synthetic-example-contract-v2`. Không phải scan thật, không phải kết quả fixtures, không có source/secret/runtime hoặc trace Semgrep thật. Mọi paths/line references là tổng hợp, không cần tồn tại trong skill.

Cặp này minh họa Semgrep-shaped supported record với manual control review; needs-review có gaps và câu hỏi blocked; false-positive có guard/control evidence; manual finding native fields null. Tổng partial dù round minh họa completed và ba track completed. Các số 3 matches/4 records chỉ minh họa aggregation, unique_issues null vì chưa triage đủ; không là số vulnerabilities. Command/version/exit/timestamps/actual execution counters null vì ví dụ không chạy scanner.

Flow steps là manual review, không native-dataflow giả. Policy-reference dùng nguồn synthetic được cung cấp, khác source hypothesis. Khi tạo báo cáo thật dùng dữ liệu quan sát, không copy claim/counts/verdict của ví dụ. Contract: [reporting](../references/reporting-and-completion.md), [evidence](../references/evidence.md).

RUN còn minh họa candidate ledger ở `coverage.inventory_candidate_reviews`; timestamps checkpoint null vì không có lượt thật. [round-spec.example.json](reporting/round-spec.example.json) là mẫu input cho helper capture, phải thay paths/purpose/source-state và cấu hình process environment trước dùng. Không chạy nguyên placeholders. [Serializer](../scripts/report_records.py) tạo draft/question với decisions null để hoàn thiện trước handoff; [checker](../scripts/check_report_links.py) chỉ kiểm bookkeeping.

`tracks[].review` minh họa tự kiểm quy trình/evidence, dependencies và next steps; `reviewed_at` null vì không có review thật. Cặp gộp bốn tracks này chỉ minh họa references/schema, không là ví dụ đã thực thi hay mặc định chạy gộp. Assessment mới theo [workflow tuần tự](../references/sequential-track-workflow.md), mỗi track thu và tự kiểm ALERTS/RUN trước chuyển tiếp. Không copy synthetic verdict/review thành phê duyệt hoặc kết quả assessment thật.

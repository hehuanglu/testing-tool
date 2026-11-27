# So sánh ZAP cho hồi quy CSP thụ động

## M0 · Baseline

- Checkout `d90cf8b19c5995af1492bfd1b869d4d4854e7510`, Darwin arm64, Python 3.13.2, Docker Desktop 29.8.1, `zaproxy/zap-stable@sha256:030d3df57735dacbb83464854758e674dd9ad01d79d12a129a8e58b1fd384238`.
- Venv Python 3.13 theo workflow, dependencies từ `requirements.lock`. Exporter 13/13, ZAP 28/28, anti-framing 6/6. Log tại `artifacts/zap-m0.ag728n/`. Lượt live dùng bản source từ `git archive HEAD tests/security` và lệnh `python tests/security/qualification/run_acceptance.py --scenario all --out <new-directory>`.
- Case `synthetic-demo` `csp-docs` yêu cầu GET `/docs` trả 200 HTML có CSP thực thi khác rỗng và không có alert `10038-1`. GET `/control` cần 200 HTML và alert cùng rule. Receipt ghi điều fixture đã phát, ZAP report ghi alert, classifier ghép chứng cứ để quyết định. Workflow GitHub qualification cũ chỉ gọi LIVE-01.
- Local đạt 13/13 lượt. LIVE-01 PASS, LIVE-02 REGRESSION với hai instance, LIVE-03/04 thiếu response/control, LIVE-05-status/media sai status/media, LIVE-06 TIMEOUT rồi PASS ở lượt mới. Lifecycle 2/1/0 case, artifact và portable đều đạt. Xem `artifacts/zap-m0.ag728n/qualification/qualification-results.json`.

## M1 · Hợp đồng bằng chứng

- Căn cứ checkout M0, action pin `c41784dfded31e10c69d78896700f48e5fd5fa3a`. Đã đọc `action.yml`, `dist/index.js` và hướng dẫn URL Presence. Wrapper dùng host networking, gọi `docker pull` rồi chạy container và gọi `setFailed` khi có lỗi. Wrapper không ghi issue. Image mặc định là tag stable có thể thay đổi.
- Mở lại `csp-docs.json`, [case ByteMe](../../tests/security/product-assessment-cases/byteme-swagger-anti-framing.json) và [readback ByteMe](zap-regression-generator-acceptance-20261111.md#anti-framing-profile-qualification-2026-11-12). Các kiểm tra exporter stale digest/context đạt trong `artifacts/zap-m0.ag728n/exporter.log`. Dấu vết, hai câu hỏi độc lập và case vai trò chưa có response nằm trong [danh mục năng lực](../../.agents/skills/mcp-zap-repo-operations/references/passive-ci-capabilities.md). Mức của wrapper hiện là đã đọc nguồn.


## M2 · Fixture và snapshot trước khi đổi classifier

- Cùng checkout M0 và runtime local. Fixture giữ receipt có thứ tự, response ID phát qua header và SHA-256 của body đã phát. Unit test đối chiếu C04 với C01, kiểm C03 chỉ có control và xác nhận thứ tự C05 khởi tạo lại khi mở fixture mới.
- Snapshot trong `artifacts/zap-m2-before.x2RQzt/C04/`, lệnh `bash tests/security/run_zap_suite.sh --cases tests/security/cases --out <new-directory> --fixture-mode wrong-page`. Classifier gốc trả PASS/0 dù receipt có marker login. Expected C04 là MISSING_EVIDENCE/1. Đây là false green được lưu trước khi thử ràng buộc marker.

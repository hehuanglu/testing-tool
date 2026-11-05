# Báo cáo alert theo contract mới — 02/11/2026

Đã xuất bundle mới tại `assessment-results/100ms-alerts-reclassified-20261102/`; không ghi đè báo cáo lịch sử, không tạo traffic hoặc thay sản phẩm/runtime.

- [RUN.json](../../assessment-results/100ms-alerts-reclassified-20261102/RUN.json): giữ nguyên operations/actionHistory,119 observations và toàn bộ50criterion;113 observations bình thường/fixture/coverage không được tính như alert. Dữ liệu/mapping cũ chỉ còn dưới các trường legacy/history có nhãn rõ.
- [ALERTS.json](../../assessment-results/100ms-alerts-reclassified-20261102/ALERTS.json):2.169 alert records, gồm2.164 native và5 observed alerts.
- [SCOPE_ALERTS.json](../../assessment-results/100ms-alerts-reclassified-20261102/SCOPE_ALERTS.json):824 mapped alert records, gồm819 native và5 observed;831 liên kết mapping tới5 criterion khác nhau. Không chứa50 dòng criterion rỗng.

## Đơn vị đếm

Native được đếm theo từng retained ZAP alert record/ID có namespace/provenance, không lấy10plugin groups làm số alert và không đếm số request. Toàn bộ2.164 native records, instances, risk/confidence và triage được giữ; không có exact duplicate composite source identities. Native informational/test-induced detections vẫn nằm trong ALERTS với triage gốc; tổng này không phải số vulnerability đã xác nhận.

Observed được đếm theo security concern/scenario có căn cứ. Hai legacy records xóa WHIP publisher và WHEP reader cùng creator-only DELETE policy/gateway/remediation item được gộp thành một observed alert, giữ cả hai source records/details. Các scenario ownerLEFT, parentEND và recorder writing trong outage giữ riêng vì khác trigger/object/postcondition, không kết luận chúng có root cause độc lập. Tổng số scoped là824records; nếu nhóm theo loại/scenario để đọc là6nhóm.

## Các alert được map

1. **HSTS Header Not Set —819native alert records.**400 trên `host.docker.internal:3001`,419 trên `host.docker.internal:8081`. Map **SEC-A04-05 — Mã hóa kết nối inbound/outbound** với `mappingConfidence:limited-context`: HSTS liên quan chính sách browser HTTPS-only/không fallback. Không khẳng định đã có HTTP downgrade/plaintext hoặc production-policy violation.29records cùng rule trên internal `backend:3000` không được map vì không suy public/browser context.
2. **Noncreator/anonymous/foreign principal DELETE known WHIP/WHEP resource —1observed alert.** Map **SEC-A01-02 — Phân quyền cấp đối tượng/dữ liệu**, **SEC-A01-04 — Thực thi phân quyền tại trusted service layer**. Caller không phải creator xóa được resource khi được cung cấp exact URL. Không có chứng minh lấy cắp URL. Cảnh báo lịch sử; finite changed-build retest không tái hiện trong phần đã kiểm tra.
3. **Membership LEFT vẫn nhận SCREEN trong12giây —1observed alert.** Map **SEC-A01-02**, **SEC-A01-04**. Existing receiver tiếp tục decoded video dù membership đã thu hồi. Cảnh báo lịch sử; finite changed-build retest không tái hiện trong phần đã kiểm tra. Không suy indefinite access/SLA.
4. **Media tiếp tục sau END khi adapter unavailable —1observed alert.** Map **SEC-A01-02**, **SEC-A10-02 — Xử lý an toàn khi external resource lỗi**, **SEC-A10-03 — Fail securely khi có exception**. END200/terminal state nhưng target receiver18→139frames trong12giây outage; recovery sau đó không chứng minh cutoff trong outage.
5. **Media tiếp tục sau ownerLEFT/shareSTOPPED khi adapter unavailable —1observed alert.** Map **SEC-A01-02**, **SEC-A10-02**, **SEC-A10-03**. Target receiver14→135frames trong12giây dù shareSTOPPED; sibling isolation/recovery được giữ riêng. Permitted cutoff vẫn cần policy.
6. **Recording segment metadata tăng sau END/STOPPED trong outage —1observed alert.** Map **SEC-A10-02**, **SEC-A10-03**. Tăng47.345bytes/2files tại2,173s lên182.492bytes/8files tại12,872s. Metadata/provider reads hỗ trợ ZAP lifecycle observation; không suy timestamp từng frame hoặc numeric SLA violation.

Ba outage alerts có status observed-concern-policy-cutoff-unresolved; hai historical alerts có status historical-not-reobserved-in-tested-changed-build-subset. Không biến matched/inconclusive outcome của phép thử thành pass hoặc tự loại security concern.

## Không ép mapping

1.345 native records còn lại được giữ trong ALERTS với unmappedReason. Không dùng missing CSP để chứng minh lỗi context-specific output encoding củaSEC-A05-01;50tiêu chí gốc không có một CSP requirement trực tiếp. Không gán media/LEAVE cho password brute-force hoặc token rotation. Test-induced URL/Referer keyword detections có triage rõ, không thành product disclosure violation. Mapping về relevance không đồng nghĩa criterion fail; zero mapped alerts không đồng nghĩa criterion pass/N/A.

## Validation

[Adapter](../../.local/zap-alert-reclassification-20261102/reclassify.py) thực hiện triage toàn129legacy records; source reports giữ nguyên byte hashes. [Validation](../../.local/zap-alert-reclassification-20261102/validation.json) kiểm tra ID unique, native details/ratings/triage không đổi, subset equality, original criterion text/source, count arithmetic, mapping rationale, operations/actionHistory và119observations giữ nguyên. Bốn negative checks từ chối empty mapping, foreign criterion, wrong count và missing scoped alert. Serialized staged bundle được validate trước publication; đúng3JSONfiles.

Đây là alert reclassification, không phải fresh scan hay quyết định closure runtime mới. Lifecycle và coverage partial được dẫn lại từ testing round trước với source reference; cached legacy closure/mapping không được trình bày như validation của schema alert mới. Generic core composer vẫn giữ schema legacy; product-local adapter này xuất đúng contract mới.

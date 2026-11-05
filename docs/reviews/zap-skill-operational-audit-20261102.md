# Kiểm tra khả năng vận hành mcp-zap-repo-operations

Ngày đánh giá: 02/11/2026, giờ Việt Nam. Bản được đánh giá là working tree hiện hành, nền HEAD `18f17860bad327a18345f949644aac4d40b7fece`, có thay đổi chưa commit từ trước. Không sửa skill, helper hay kết quả sản phẩm trong lượt audit này.

## Kết luận

Skill có năng lực vận hành thực tế và giữ ranh giới kết luận khá tốt. Chưa đủ căn cứ coi nó là quy trình tổng quát đã được kiểm chứng đầy đủ trên mọi sản phẩm, mọi kiểu đăng nhập và cả năm track. Điểm yếu quan sát được tập trung ở điều phối, độ ổn định adapter/fixture, quyết định checkpoint và phân biệt dependency cần agent chủ động điều tra với dependency thực sự cần người dùng.

Không có bằng chứng rằng độ dài SKILL.md là nguyên nhân chính gây các vấn đề này. Description không dài bất thường đối với phạm vi hiện tại. Nội dung chính còn có thể tổ chức gọn hơn; chi phí đáng chú ý hơn nằm ở tài liệu đọc kèm và đọc lặp. Việc rút gọn cần được đánh giá bằng hành vi, không chỉ bằng số từ.

## Phạm vi và phương pháp

- Đọc SKILL.md, metadata, các reference chính về dispatcher, runner, coverage/completion, readback, recovery, reporting, resource và operational validation; đối chiếu mã reconciliation và regression tests.
- Đọc trực tiếp lịch sử bốn chat vận hành gần đây, gồm message và command records; đọc thêm trang lịch sử cũ của chat tiếp tục assessment. Không suy hành vi từ riêng title/summary. Một số command arguments bị cắt bởi công cụ, không replay toàn bộ HTTP traffic.
- Dùng review cũ `zap-workflow-after-skill-20261101.md` làm dữ liệu lịch sử thứ cấp. Không tuyên bố đã đọc lại trực tiếp toàn bộ 12 chat của review đó.
- Đối soát ba báo cáo chính thức của `100ms-fresh-20261101`, updatedAt `2026-11-01T17:10:59.290750+00:00`, tương ứng 00:10:59 ngày 02/11 tại Việt Nam.
- Kiểm tra link tài liệu, tool inventory từ source, report structure/references, capability registry và regression suite trong môi trường Python 3.13 tách biệt.
- Không khởi động scanner sản phẩm, gửi thêm traffic assessment, đổi cấu hình, xóa history, cài bản skill cá nhân hay sửa policy.

Các chat đọc trực tiếp:

- **Tiếp tục assessment ZAP** — `01a197e8-f3b2-7261-8a74-27bd52d31ddb`.
- **Tiếp tục assessment ZAP** — `01a1977c-bb3d-7a00-ac4d-189778d4679b`.
- **Vận hành lại mcp-zap cho 100ms** — `01a19750-63ef-77f1-9541-1c71fefdd8de`.
- **Tiếp tục đánh giá quyền WHEP** — `01a196d6-9ad1-74e0-b8f7-8fe1b4a522a5`.

## Độ dài và cơ chế nạp

Số đo bằng tách từ theo whitespace, không phải số token:

| Thành phần | Số đo |
|---|---:|
| Frontmatter description, sau khi gộp whitespace | 317 ký tự / 38 từ |
| Toàn bộ SKILL.md, gồm frontmatter | 102 dòng / 2.234 từ / 18.763 byte |
| References cấp đầu | 35 file / 25.534 từ |
| References gồm thư mục knowledge | 36 file / 26.513 từ |
| SKILL.md tại HEAD để tham khảo | 1.940 từ |

Theo [tài liệu chính thức về skill](https://learn.chatgpt.com/docs/build-skills), name/description được dùng trước để nhận diện; toàn bộ SKILL.md được đọc khi chọn skill. References được đọc theo nhu cầu. Vì vậy, 26.513 từ references không tự động có nghĩa toàn bộ chúng đều nằm trong context mỗi lượt.

Description hiện tại nêu ZAP, backend/frontend, anonymous/authenticated và BOLA sớm, nên có giá trị định tuyến. Chưa có tập thử implicit invocation để kết luận tỷ lệ kích hoạt đúng/sai; các chat gọi skill rõ ràng không chứng minh được điều đó.

Root document tương đối dày: chỉ 102 dòng nhưng nhiều đoạn dài, lặp quy tắc tiếp tục/checkpoint, ranh giới kết quả và ba file đầu ra. Cùng các nguyên tắc đó còn xuất hiện trong dispatcher, responsibility loop, completion và handoff. Đây là rủi ro bảo trì và chi phí context có căn cứ từ source; chưa phải bằng chứng nhân quả về lỗi agent.

Ở lượt thực thi mới nhất, command records cho thấy agent dùng `cat` với ít nhất 12 reference khác nhau, đồng thời đọc lặp result-boundary/tester-context/track-intents và resource-preflight. Theo nội dung hiện hành, 12 file này có khoảng 13.594 từ; phần đọc lặp nói trên khoảng 2.809 từ. Đây là số đo tài liệu theo command records, không phải token thực tế đã được model giữ hoặc chi phí billing. Nó cho thấy tối ưu cách chọn và tái sử dụng reference có thể đáng chú ý hơn chỉ rút vài đoạn ở root.

[Hướng dẫn chính thức về tổ chức skill](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) khuyến khích root làm bộ định tuyến tối giản tới tài liệu hỗ trợ. Khuyến nghị này phù hợp với cấu trúc skill hiện tại, nhưng chưa chứng minh rằng một bản ngắn hơn sẽ vận hành tốt hơn trên sản phẩm này.

## Khả năng đã quan sát

### Lập kế hoạch và tiếp tục nhiều mục tiêu: có, chưa ổn định giữa các lượt

Lượt thực thi mới nhất dài khoảng 51,7 phút, có 104 shell-command records, tiến qua command, receipt, role/session, parent END và media. Đây là phản ví dụ cho kết luận rằng skill chỉ làm một block rồi dừng. Thời lượng là wall time của lượt, không phải thời gian scan thuần hoặc thước đo tận dụng context.

Trong chat trước đó, sau khi người dùng gửi tiếp tục ngay trong cùng chat, agent còn thực hiện raw PDF, UI filename/Blob cleanup và receipt sau END. Khuyến nghị chuyển chat trước đó vì cần nạp nhánh command/media chưa giải thích rõ vì sao kiến thức đang có không còn dùng được. Sau đó mới xuất hiện thiếu đĩa thực tế trong lúc save; không nên dùng sự cố tài nguyên về sau để hợp thức hóa toàn bộ lý do checkpoint trước đó.

Lượt mới nhất kết thúc với hướng dẫn không cần chat mới. Đây là cải thiện quan sát được, chưa đủ để khẳng định toàn bộ lỗi chia phiên đã hết hoặc thay đổi chỉ do SKILL.md.

### Thực thi DAST, UI và ownership: có kết quả cụ thể

History có native payload allocations, real browser/UI qua ZAP, role/session/ownership comparisons và post-state readback. Các kỹ thuật được phân biệt; direct TLS media dùng hỗ trợ fixture không được tự động tính là ZAP coverage.

Tuy nhiên, runner map tự nêu giới hạn: nhiều nhánh phụ thuộc product adapter; common native lane có rule/body/vector admission cụ thể; cookie/SSO và generic FE hooks không thể suy ra từ bearer/finalsource. Khả năng của ZAP, schema MCP đang expose, khả năng runner và kết quả đã chạy là bốn lớp khác nhau. Chưa có căn cứ gọi đây là scanner đa sản phẩm tự động hoàn toàn.

### Diễn giải kết quả: là điểm mạnh

- Không biến plugin Complete, ACK hay HTTP 200 thành hoàn tất câu hỏi.
- READY không thay actual LIVE; outbound frames không thay sustained RECORDING và segment readiness.
- Receipt cũ trả 201 được phân biệt với mutation mới bằng trạng thái trước/sau.
- WHEP DELETE với secret chủ động chuyển cho actor khác được giữ inconclusive, không tự kết luận BOLA.
- Native severity/confidence được giữ riêng; observations không được cộng vào số lỗ hổng native.

Đây là hành vi thực tế hỗ trợ cho các quy tắc trong skill, không chỉ là lời hứa trong tài liệu.

### Coverage và completion: có tiến triển, còn khoảng thiếu

RUN hiện tại có 17 route unit completed và 12 partial, thay vì 29/29 partial của review cũ. Các remainingWork đã cụ thể hơn: recording readiness, STAGE STOP503, internal ingress, rate-blocked native inputs và capability/revocation policy. Route completed chỉ đóng các câu hỏi hữu hạn được nêu; không có nghĩa toàn bộ tiêu chí bảo mật của route đã được chứng nhận.

Trong 50 tiêu chí: 20 partial, 24 not-operated, 6 applicability-reviewed. Toàn bộ BE anonymous, BE authenticated, BOLA và FE vẫn partial. Không quy 17/29 thành phần trăm hoàn thành bảo mật.

Các helper reconciliation tin vào observation labels do adapter/agent cung cấp; chúng không tự xác minh HTTP body, object/origin/build hoặc ý nghĩa chính sách. Tài liệu đã công khai giới hạn này. Tests về nhãn/contract không thể thay việc review observation hoặc chứng minh agent sẽ luôn lập luận đúng.

### Phục hồi và báo cáo: dùng được, còn chi phí vận hành

History có đối soát save timeout thành công thay vì save/load lại; readback của thao tác đã chạy được phục hồi riêng khi reader lỗi. Pending/unknown được giữ làm điều kiện trước retry. Đây là cơ chế tốt.

Mặt khác, nhiều helper snapshot theo phiên và các lần đóng/khôi phục scanner làm tăng số lựa chọn cần xác minh. Đã có mismatch message count sau load; agent không replay load và tiếp tục đối soát, nhưng tình huống này cho thấy cần entry khôi phục ổn định dựa trên current lineage thay vì nối thêm tên helper theo từng block.

## Vấn đề ưu tiên

0. **Sửa đường dẫn trong regression test đóng gói.** Full suite có một lỗi xác định: `tests/test_discovery_transport.py:112` gọi cleanup script qua `rp.WORKSPACE/'zap-product-assessment/scripts/cleanup_research_accounts.py'`. File không tồn tại tại product workspace; bản đóng gói tồn tại ở `rp.PACKAGE_ROOT/'scripts/cleanup_research_accounts.py'`. Khi chỉ chuyển đường dẫn đó trong bộ nhớ bằng test harness, cùng test đạt. Đây là lỗi portability của test; chưa có bằng chứng cleanup script đóng gói bị lỗi logic hoặc gây sự cố ở sản phẩm. Giữ nguyên test/source trong audit, nên full suite hiện vẫn đỏ.
1. **Ổn định adapter và đầu vào thực thi.** Lượt mới nhất có lỗi tên trường catalog, version LEAVE, đường dẫn chứa khoảng trắng, kiểu dữ liệu và cách đọc STOPPED. Có native START bị rate-blocked 503; allocation END đầu dùng SiteNode body cũ nên chỉ đạt validation/stale-version rejection. Agent đã sửa và phân loại đúng, nhưng các lỗi làm mất công và để lại coverage chưa đủ. Không gộp mọi 503 thành cùng nguyên nhân: STAGE STOP và recording vẫn chưa có root cause chắc chắn.
2. **Tiếp tục điều tra dependency trong quyền có sẵn.** Câu kết “khi có dữ liệu mới” dễ chuyển phần điều tra cho người dùng. Chính chat mới nhất đã phải làm rõ rằng tìm trace và kiểm tra đường gọi internal vẫn là việc agent cần chủ động đánh giá. Dependency policy thực sự cần quyết định nghiệp vụ khác với dependency kỹ thuật có thể đọc/chuẩn bị trong quyền hiện có.
3. **Checkpoint dựa trên trở ngại cụ thể.** Đổi fixture/role/vector chưa đủ. Khôi phục trong cùng chat rồi làm tiếp hữu ích là bằng chứng cần cải thiện quyết định dừng; không phải bằng chứng biết chính xác context còn bao nhiêu.
4. **Tổ chức tài liệu theo một nguồn quy tắc chính.** Giữ phạm vi, chu trình vận hành và điều kiện dừng cốt lõi ở root; phần chi tiết do một reference sở hữu, các file khác trỏ tới. Giảm đọc lặp sau khi đã hiểu stable facts. Không xóa các điều kiện chống false completion để đạt số từ đẹp.
5. **Đánh giá hành vi bằng tình huống thực.** So bản hiện hành và bản rút gọn trên cùng saved scenarios: có việc độc lập thì tiếp tục; explicit stop thì dừng; reader lỗi sau mutation thì readback trước; zero-payload/rate-blocked không được tính coverage; policy chưa rõ không biến thành BOLA; question answered dù có violation vẫn có thể đóng coverage. Theo dõi câu hỏi giải quyết được, lỗi tái diễn, lần người dùng phải nhắc tiếp tục, retry sai và token thực nếu có. Không dùng số alert/request hay chỉ thời lượng chat làm KPI.

## Giới hạn kết luận

Audit kiểm tra rộng các lớp tài liệu, code/contracts, histories và derived reports; không phải live qualification mới cho toàn bộ tool/track. Không chạy A/B hoặc agent benchmark mới; không biết token/context thực tế của các chat cũ. Không chứng minh toàn bộ role/input/state combinations hoặc cross-product runtime compatibility.

Capability registry có thể hợp lệ về cấu trúc nhưng các legacy G3/P0 proof modes vẫn blocked; điều đó không phủ định các execution path khác đã thực sự chạy. Bản skill cá nhân ở `~/.codex/skills/mcp-zap-repo-operations` không tồn tại; helper install check báo missing không phải lỗi của repo-local skill.

Các số liệu là snapshot tại thời điểm nêu trên; RUN/ALERTS/SCOPE_ALERTS có thể được chat khác cập nhật sau audit. Báo cáo này không thay thế báo cáo sản phẩm.

## Nguồn và kiểm tra

- Skill: `.agents/skills/mcp-zap-repo-operations/SKILL.md` và references liên quan.
- Source: `product_scope.py`, `product_workflow.py`, các tests readback/continuation/checkpoint/portability/track contracts.
- Review lịch sử thứ cấp: `docs/reviews/zap-workflow-after-skill-20261101.md`.
- Báo cáo sản phẩm: `assessment-results/100ms-fresh-20261101/{RUN,ALERTS,SCOPE_ALERTS}.json`.
- Tài liệu OpenAI: [Build skills](https://learn.chatgpt.com/docs/build-skills), [Rethinking skills and prompts](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra), [Testing Agent Skills Systematically with Evals](https://developers.openai.com/blog/eval-skills).

Kết quả kiểm tra tĩnh: 207 local Markdown links có file đích; inventory source có 78 tool names, không thấy tên tool bị thiếu hoặc tên cũ trong native-operation-routing; không khẳng định schema/auth compatibility từ kiểm tra tên.

Ba báo cáo có cùng summary/generation, không trùng operation ID/finding ID, không thấy alert operation reference bị thiếu. Session helper trả checkpointReady=true, requiresReconciliation=false, hai next actions; đây chỉ là kiểm tra cấu trúc dữ liệu, không xác minh live state hoặc tính hợp lý của quyết định dừng.

### Regression thực sự đã chạy

Python hệ thống 3.13.2 không có jsonschema; lượt đầu bị dừng, không được tính là regression hợp lệ. Tạo venv tạm `/tmp/zap-skill-audit-20261102-venv` và cài đúng `requirements.lock`, không sửa môi trường global hay skill.

```sh
PYTHONPATH=.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src:.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/tests \
  /tmp/zap-skill-audit-20261102-venv/bin/python -B -m unittest discover \
  -s .agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/tests -p 'test_*.py'
```

Kết quả: **935 tests trong 166,967 giây; 925 đạt, 9 skipped, 1 error**. Error là test cleanup path nêu trên. Các skip bao gồm tests cần source finalsource không đóng gói trong skill; không tính chúng là đã xác minh FE/product runtime. Output của test doubles có chữ provisioning/scanning không có nghĩa audit đã provision hoặc scan sản phẩm thật; suite dùng fake/mocked runtimes và local test servers.

Chẩn đoán tập trung sau full suite: chạy riêng test lỗi, dùng mock `runpy.run_path` chỉ đổi legacy path sang packaged path trong bộ nhớ; **1 test đạt trong 0,008 giây**. Không ghi sửa đổi vào test; không trình bày kết quả chẩn đoán này thành full suite xanh.

Log full suite: `/tmp/zap-skill-audit-20261102-tests-qualified.log`. Source inventory: `/tmp/zap-skill-audit-20261102-tool-inventory.json`. Dependency-install log: `/tmp/zap-skill-audit-20261102-deps.log`. Các file `/tmp` là dữ liệu chẩn đoán tạm, không phải handoff sản phẩm hoặc nơi lưu bằng chứng lâu dài.

Capability check: registry/inventory pass, 9 capabilities; G3 blocked và operationalModesEnabled rỗng vì proof access/seeded-control/lifecycle chưa đủ trong registry. Không có target request. Đây là trạng thái của cơ chế proof registry, không phải verdict toàn cục về các track đã có execution history.

Audit đã hoàn tất; không cần mở chat mới để đọc kết quả. Việc sửa test, ổn định adapters và thử bản tài liệu rút gọn là đề xuất tiếp theo, chưa thực hiện trong lượt đánh giá này.

## Cập nhật sau audit — chỉnh sửa theo yêu cầu người dùng

Ngày 02/11/2026: người dùng yêu cầu thực hiện cải thiện và hạn chế tác động lên runner/helper đang dùng cho product gốc. Phần này ghi thay đổi sau audit, không thay thế kết quả lịch sử phía trên.

### Phạm vi sửa

- Rút root `SKILL.md` từ 2.234 xuống 1.190 từ, giữ nguyên frontmatter description. Giữ nghĩa vụ các track, phạm vi độc lập với runner, finite closure, phân biệt kết quả native/observation/support, chống false completion/replay, resource/authority gates và ba file handoff. Chi tiết đi qua các reference hiện có; không thêm reference bắt buộc hoặc gate mới.
- `operation-dispatch.md`: đọc theo quyết định hiện tại, tái sử dụng hướng dẫn ổn định đã hiểu; đọc lại khi thay đổi hoặc chưa rõ. Vẫn kiểm tra dependency sống trước thực thi.
- `local-remediation-and-continuation.md`: bảo toàn runner/helper/recovery entry đang dùng; sửa executable chỉ khi có lỗi hoặc thiếu primitive cần thiết. Phân biệt điều tra kỹ thuật agent còn có thể làm với thông tin/quyết định thực sự cần người dùng.
- `retention-stop-and-recovery.md`: trỏ quyết định dependency về hướng dẫn trên; checkpoint vì context không biến điều tra khả thi thành blocker bên ngoài.
- `test_discovery_transport.py`: sửa duy nhất đường dẫn cleanup test sang `rp.PACKAGE_ROOT/'scripts/cleanup_research_accounts.py'`. Không đổi cleanup script, product adapter hoặc runner.

### Đối chiếu tình huống trước khi kết luận

Đây là walkthrough thủ công trên các tình huống của audit và quy tắc được giữ lại, không phải benchmark agent hoặc product retest:

| Tình huống | Quyết định cần giữ trong bản sửa |
|---|---|
| Đạt mục tiêu đầu, còn câu hỏi dùng được kiến thức/fixture hiện tại | Chọn và thực hiện mục tiêu tiếp theo; không tự yêu cầu prompt mới |
| Đổi fixture hoặc role nhưng chưa có trở ngại context cụ thể | Tiếp tục trong quyền hiện có; thay fixture không tự tạo lý do checkpoint |
| Người dùng yêu cầu dừng sau block | Tôn trọng ranh giới người dùng, lưu phần còn lại |
| Script đã chạy, reader JSON lỗi | Đọc ACK/result/state có sẵn trước; không replay mutation để thử parser |
| Native scan terminal nhưng zero payload, rate-blocked hoặc auth loss | Giữ câu hỏi thiếu coverage; sửa prerequisite có căn cứ, không tính terminal thành hoàn tất |
| Recording/STOP503 chưa rõ nguyên nhân, còn nguồn chẩn đoán được phép | Chủ động điều tra hoặc chuyển việc độc lập; không chỉ chờ người dùng mang dữ liệu mới |
| Capability/revocation policy chưa rõ | Giữ kết luận giới hạn, tìm căn cứ có sẵn; không tự phê duyệt chính sách hoặc suy BOLA từ secret được chuyển có chủ đích |
| Câu hỏi đã đủ kết quả nhưng phát hiện violation | Có thể đóng coverage câu hỏi đó; giữ security finding và các nghĩa vụ khác độc lập |

Các tình huống đều có đường xử lý trong root và reference hiện có. Walkthrough không chứng minh agent tương lai sẽ chọn đúng hoặc giảm số prompt; cần theo dõi lượt vận hành tiếp theo để đánh giá điều đó.

### Bảo toàn phiên gốc

Chụp checksum cục bộ trước chỉnh sửa cho 695 file: nội dung skill (bỏ cache Python), script Python/MJS và metadata native-session-retention của phiên 100ms, cùng ba báo cáo chính thức. Chỉ năm file skill liệt kê trên được phép thay đổi trong lần sửa này. Không chỉnh executable runtime, schema, plan/pins, snapshot database, credential, raw history, trạng thái producer/scanner hay báo cáo product. Không cài/đồng bộ bản skill cá nhân, commit hoặc push.

Kiểm tra frontmatter bằng `skill-creator/scripts/quick_validate.py` đạt; link tài liệu không có file đích thiếu và `git diff --check` đạt. Full regression chạy lại: **935 tests trong 165,430 giây, 926 đạt, 9 skipped, không failure/error**. Lỗi cleanup test được sửa trên source, không dùng path override của bước chẩn đoán trước. Log: `/tmp/zap-skill-edit-20261102/tests.log`.

So checksum sau kiểm tra: đúng năm file skill/test dự kiến thay đổi trong 695 file được chụp; runner/helper, script tiếp tục phiên, metadata snapshot và ba báo cáo product nguyên vẹn. Snapshot database/raw không được mở để sửa hoặc sao chép. Phần chỉnh sửa đã hoàn tất; không cần một chat mới cho việc sửa skill. Phiên kiểm thử có thể tiếp tục từ official RUN hiện tại, đọc lại SKILL.md mới và xác minh dependency sống theo continuation; không chạy lại payload hoặc đổi pins chỉ vì thay hướng dẫn. Hiệu quả điều phối thực tế cần được đánh giá ở lượt vận hành kế tiếp.


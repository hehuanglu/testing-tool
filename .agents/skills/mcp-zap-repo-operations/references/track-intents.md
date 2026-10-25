# Phạm vi và điểm xuất phát nghiệp vụ của từng track

Đọc cùng [general context](tester-context.md). Những hướng khảo sát dưới đây là **base để lập kế hoạch**, không phải checklist bắt chạy tất cả, không ép mọi product có cùng feature và không tự mở track khác. Scope người dùng quyết định trách nhiệm; discovery quyết định những việc áp dụng; capability chỉ quyết định cách/chia lượt thực hiện. DAST là kiểm động bằng ZAP thực; UI automation và direct BOLA được ghi riêng.

## BE anonymous

**Ý định:** nhìn server như người chưa đăng nhập: public API nhận input gì, xử lý/tiết lộ gì, các đường cần đăng nhập có từ chối đúng ở mức control hay không.

**Khởi đầu nghiệp vụ:** tìm public endpoints và auth middleware; gửi baseline không identity cho luồng public bình thường, public search/detail/list và login/register/reset nếu có. Xác định content type, required fields, state/mutation và anonymous cookie cần thiết. Public auth response có thể cấp token: ghi transition và không dùng token cho request được tính anonymous. Không strip identity tùy tiện rồi coi đó là hành vi browser nguyên bản.

**Phạm vi thực hiện:** toàn method–route public trong scope; dùng import/seed/crawl phù hợp rồi passive và active theo input/rủi ro. Kiểm error handling, input processing và phản hồi liên quan bằng kỹ thuật có ý nghĩa. Protected-denial là control bổ sung, không thay public DAST. Public mutation cần fixture và caps phù hợp; không bỏ login/register vì khó chạy. Không gửi danh tính đăng nhập.

**Đủ để đóng:** đối soát mọi public endpoint; ghi kỹ thuật/kết quả hoặc phần chưa làm. Import, vài request, passive-only hay zero alerts không đủ gọi track DAST hoàn tất. Thiếu query không tự N/A active.

## BE authenticated

**Ý định:** nhìn server như user đã đăng nhập đúng role: input tới protected business handler, session còn hiệu lực và những API được cấp quyền được DAST thực.

**Khởi đầu nghiệp vụ:** xác định auth flow, token/cookie và cách dùng, tài khoản/role có sẵn hoặc tạo hợp lệ, protected probe và nghiệp vụ chính. Kiểm một baseline có nghĩa cho từng nhóm role/hành vi; chuẩn bị object/state để API thực sự xử lý. Không bắt mọi product có whoami hay cùng JWT issuer. Token thật được lưu local private khi cần, chỉ thông báo, không hỏi lại.

**Phạm vi thực hiện:** toàn protected method–route thuộc scope; xét role có hành vi khác, input query/body/path/header/content type phù hợp. Chuẩn bị/validate session, seed và ZAP active, theo dõi mất auth. Refresh/relogin là xử lý vận hành khi cần; full expiry/revoke/SSO lifecycle chỉ khi câu hỏi/scope yêu cầu. Public surface đối soát sang anonymous, không tự mở scan anonymous nếu chỉ giao protected BE. BOLA chuyên sâu là track riêng.

**Đủ để đóng:** protected endpoints được xử lý đúng actor/role với phiên hợp lệ và kỹ thuật được ghi rõ. 401/mất phiên không tính authenticated coverage. Direct request, token login thành công hoặc BOLA direct không thay ZAP authenticated DAST. Actor/fixture/vector chưa hỗ trợ còn là phần mở.

## FE anonymous

**Ý định:** nhìn sản phẩm như người dùng mới, chưa đăng nhập, đang sử dụng trình duyệt. Kiểm hành vi trang, input, điều hướng và request thực do UI tạo ra qua ZAP.

**Khởi đầu nghiệp vụ:** mở frontend thật với session sạch; xác định public routes/pages, form, search, links, upload và các transition nếu có. Quan sát DOM/UI validation, storage/cookies và network để phân biệt validation phía client với server. Thực hiện một journey bình thường trước biến đổi input. SPA shell HTTP200 chưa chứng minh route/UI hoạt động.

**Phạm vi thực hiện:** thao tác UI thật trên public journeys/routes và endpoint public liên quan scope FE; proxy traffic qua ZAP, passive và kỹ thuật active/browser phù hợp. HTTP/AJAX/Client Spider bổ sung discovery, không thay thao tác click/submit/navigation/read UI. Với stored/DOM/reflected input, chọn nơi vào và nơi hiển thị đúng; reflection khác execution. Khi UI chuyển sang authenticated, kết thúc phần anonymous của ca hoặc chuyển track chỉ nếu đã được giao.

**Đủ để đóng:** đối soát public UI journeys và câu hỏi bảo mật của network surface liên quan; active đang áp dụng còn thiếu thì scope còn mở dù UI/passive đủ; nêu UI đã thao tác, request/kỹ thuật đã chạy và kết quả. API-only, crawler-only hoặc ảnh trang không thay thực hiện FE. Không tự kéo toàn BE ngoài surface FE vào nhiệm vụ.

## FE authenticated

**Ý định:** nhìn sản phẩm như user đã đăng nhập từng role cần kiểm, thực hiện nghiệp vụ trên UI và quan sát ứng dụng cùng request/response thật.

**Khởi đầu nghiệp vụ:** login qua UI thật, xác định account/role, landing page/menu theo quyền, session storage và một journey protected bình thường. Chuẩn bị dữ liệu populated để thao tác có ý nghĩa; kiểm UI state trước/sau cùng network. Direct login/setup có thể hỗ trợ native ZAP/fixtures nhưng không thay UI login/journey.

**Phạm vi thực hiện:** protected UI journeys/routes và API liên quan trong scope FE, đúng role/session; thao tác form/click/reload/navigation và kiểm kết quả UI/network/post-state phù hợp. Native active dùng auth thực được executor hỗ trợ và xác minh actor riêng; browser auth không tự chứng minh active scanner đang dùng cùng danh tính. Role đổi view/feature phải được đối soát. Không biến menu ẩn thành bằng chứng server đã chặn quyền; BOLA đầy đủ chỉ chạy khi được giao.

**Đủ để đóng:** có thao tác browser thực, journey outcomes và kết quả kiểm bảo mật cho từng API/input liên quan; active đang áp dụng phải được allocate, thực hiện và đọc kết quả. UI/passive hoặc campaign list rỗng không thay active; kỹ thuật N/A cần căn cứ product. Đối soát inventory độc lập với journeys/campaigns; session loss chỉ tính đến điểm quan sát hợp lệ. Không thay UI mutation bằng DB DML/API setup. Thiếu fixture/role/capability chỉ giữ mở các journey phụ thuộc.

## BOLA ownership

**Ý định:** kiểm ranh giới quyền trên object: actor nào được làm action nào với object của ai, trong relation/state nào. Function-level access là chiều bổ sung riêng, không gọi mọi denial/role difference là BOLA.

**Khởi đầu nghiệp vụ:** inventory tất cả endpoint–role trong scope; xác định object, ID ở path/query/body, parent/child, owner/tenant/shared grants và lifecycle có ảnh hưởng quyền. Lấy kỳ vọng từ policy/spec hoặc giả định source đã ghi rõ. Chuẩn bị đủ các role discovery, owner và non-owner hợp lệ; kiểm positive baseline trước negative case. Với role đặc quyền, quyền trên nhiều owner không có nghĩa object không có owner.

**Phạm vi thực hiện:** owner/non-owner/cross-owner, đủ role đã discovery, anonymous khi liên quan; read/create/update/delete và business action; collection/filter/pagination; nested references và state làm thay đổi quyền. Kiểm dữ liệu trả về và side effect, không chỉ status. Object ID mới lấy từ ACK/readback; populated collection cần đối chiếu object scope. Chọn ca theo khác biệt quyền có nghĩa, không bắt tích Descartes vô hạn.

**Đủ để đóng:** mỗi endpoint–role có applicability và kết quả hoặc mục chưa thực hiện; missing actor/fixture/policy không thành N/A. Direct-client được dùng, finding ghi nguồn direct. Matched theo source-hypothesis chưa chứng nhận policy đúng; không sửa expected để khớp observed. Không thay hai track DAST bằng BOLA.

## Chung cho năm track

Giữ discovered → request sent → technique run → result read riêng. Toàn endpoint trong scope không đồng nghĩa mọi rule trên mọi input; kỹ thuật N/A cần lý do nhưng endpoint không bị bỏ. Khi không thể lập inventory chắc chắn, báo giới hạn discovery và xử lý phần xác định được, không gọi whole-product complete.

Completion dựa vào scope/inventory độc lập với workload đã chọn. Còn mục đủ điều kiện thì tiếp tục; còn mục bị chặn thì partial/blocked và lý do thật. Bộ bàn giao assessment vẫn chỉ ALERTS.json và RUN.json theo [hợp đồng bàn giao](product-assessment-handoff.md).

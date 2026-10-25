# Hợp đồng phạm vi nhiệm vụ và hoàn tất

Áp dụng [đầu ra hai file](product-assessment-handoff.md). Trung thực thao tác và kết quả; không đòi bộ bằng chứng chặt để hoàn tất báo cáo. Quyền target, giới hạn resource và gate code của executor vẫn giữ nguyên.

## Bốn lớp cần giữ riêng

1. Inventory đầy đủ từ source/spec/routes và runtime có sẵn: method–route, input, role, object/action/relation/state liên quan; chỗ chưa xác minh vẫn được ghi.
2. Phạm vi từ user và discovery thuộc track được giao. User giao hẹp thì giữ hẹp; user giao cả track thì không tự thu hẹp theo recipe hoặc ca dễ chạy.
3. Workload từng lượt hữu hạn trong quyền/capability/tài nguyên. Mục chưa chọn vẫn ở danh sách trách nhiệm, không tự thành ngoài scope.
4. Kết quả: việc thực sự đã làm, kết quả/lỗi và phần chưa làm. Tool tồn tại, import thành công, test pass hoặc đủ output không đồng nghĩa đã scan hết.

## Phạm vi backend và BOLA

- **BE anonymous:** ZAP DAST thật trên mọi API public trong scope, không token/danh tính đăng nhập. Login/register public vẫn thuộc phạm vi. Seed, validation và passive được ghi riêng; không dùng vài request hoặc passive-only thay mục tiêu active. Protected-denial là control bổ sung.
- **BE authenticated:** ZAP DAST thật trên mọi API protected trong scope với đúng actor/role và phiên còn hiệu lực. Map từng API với role, fixture/input, kỹ thuật đã chạy và kết quả. Xét các role có hành vi khác; role còn thiếu phải giữ mục chưa thực hiện. Public API được đối soát ở track anonymous. 401 hoặc mất phiên không là authenticated coverage.
- **BOLA:** mọi endpoint–role trong scope có applicability và kết quả/chưa kiểm cụ thể; phải xét đủ role đã discovery, gồm role đặc quyền và anonymous khi liên quan. Với object có owner, kiểm owner-positive, non-owner/cross-owner và quyền theo role; xét relation/state, collection/list/filter/pagination làm thay đổi quyền. Tách quyền chức năng và object ownership. Direct-client được dùng đúng scope, findings ghi nguồn direct, không thay DAST authenticated.

“Toàn API” là không bỏ sót method–route thuộc scope, không là mọi input/rule/role/state kết hợp vô hạn. Một kỹ thuật không phù hợp có thể N/A ở chiều đó; API vẫn phải được xử lý. Thiếu token/fixture/capability là mục còn mở, không N/A. Không sửa expected theo response hoặc trả sẵn pass.

## Phạm vi FE

Ý định và khảo sát ban đầu của cả năm track ở [track intents](track-intents.md); đây là base suy luận, không ép mọi product chạy tất cả case.

- **FE anonymous:** browser thật, public UI journeys/routes và public network surface liên quan scope; không login identity trong phần anonymous. Crawler/API-only không thay UI action.
- **FE authenticated:** UI login và protected journeys đúng actor/role/session, UI/network/post-state phù hợp; API/DB setup chỉ bổ trợ. Browser session không tự chứng minh native active cùng actor.

Đối soát UI responsibilities cùng câu hỏi bảo mật/kỹ thuật trên mọi API/input liên quan. Active đang áp dụng cần thực thi/readback riêng; UI/browser traffic/passive không thay thế. Mỗi chiều kỹ thuật N/A có căn cứ product; thiếu phương tiện giữ mở. Đối soát UI responsibilities cùng API liên quan; không tự kéo toàn backend ngoài scope FE. GraphQL/RPC cần giữ operation nghiệp vụ bên trong endpoint dùng chung khi liên quan scope.

## Kế hoạch hữu hạn và bốn mức bao phủ

Giữ riêng discovered → đã gửi request → đã chạy kỹ thuật phù hợp → kết quả đọc được. Không buộc manifest hoặc file chứng minh cho mỗi mức; ghi trung thực trong RUN.

Vòng vận hành: intake → inventory → câu hỏi bảo mật/role/object → mapping operation → chia lượt → thực hiện → đọc kết quả → reconcile → sửa tối thiểu/kiểm tra → tiếp tục. Ưu tiên nghiệp vụ lõi và input có ý nghĩa; không lấy recipe mẫu làm toàn bộ nhiệm vụ.

### Chọn kỹ thuật trước khi đối chiếu capability

Theo input/rủi ro thực: query/body/path/header/protocol có liên quan, kiểm validation và dữ liệu trả về. Không mặc định chỉ XSS/SQLi vì wrapper cho hai rule, cũng không bật mọi rule để tăng số lượng. Thiếu query/body không tự loại toàn bộ active. Phân biệt kỹ thuật đã chạy với kỹ thuật chỉ nằm trong kế hoạch.

## Trước execution: reconcile và lập lượt chạy

Đối chiếu recipe và tool thực với inventory/role. Ưu tiên operation có sẵn → cấu hình/phối hợp → mở rộng runner/adapter cần thiết → runner mới có lý do → capability nền tối thiểu. Gắn prerequisite đúng case: deployment, actor/role, fixture, state, operation, kiểm kết quả sau mutation và cleanup liên quan. Không đòi mọi control/qualification cho nhánh không phụ thuộc.

Không lấy thời gian làm bằng chứng task xong; caps chỉ chia lượt. Không tự dựng source archive/hash/proof campaign mới cho mỗi route. Nếu executor đang bắt pin/proof, đó là dependency implementation cụ thể; không giả pass, không bypass hoặc khái quát rejection thành ZAP không làm được.

## Dependency và semantics từng nhánh

### Gắn dependency vào case cần nó

Thiếu deployment chỉ chặn traffic; source discovery vẫn tiếp tục. Thiếu actor một role chỉ chặn các case role đó. Object chưa tạo được cần tìm cách chuẩn bị hợp lệ và ghi bước tiếp, không loại nghiệp vụ lõi. Mutation cần kiểm kết quả/trạng thái liên quan ở mức đủ biết thao tác thành công hoặc bị từ chối; không đòi campaign chứng minh độc lập mới cho mỗi object.

### Giữ riêng owner của object và quyền của actor

Role có quyền thao tác object của nhiều owner không làm object mất owner. Shared catalog/dữ liệu công khai khác object cá nhân. Xác định semantics từ nguồn có sẵn và kiểm thử thật; không gán role/route/state của product cũ cho product mới. Policy suy từ source phải được gọi đúng là giả định theo source, chưa tự là chuẩn nghiệp vụ được xác nhận.

### Đọc lại kết quả cuối

RUN phải giữ đúng nhánh nào đã chạy, role nào, kết quả nào và phần chưa làm; mô tả trong chat phải khớp file. Chưa có dữ liệu thì nói chưa có, không lấp bằng kết quả control hoặc số lượng kỳ vọng cố định.

## Caps, quyết định phạm vi và tiếp tục

Sau mỗi lượt cập nhật RUN/ALERTS rồi tự chọn lượt tiếp. Không đợi PM sau từng subset đủ điều kiện. Với lỗi cục bộ, chẩn đoán/sửa/kiểm tra tập trung rồi tiếp tục; không rerun tất cả chỉ vì sửa docs hoặc aggregation. Start/mutation chưa rõ kết quả thì đọc trạng thái trước retry. Chỉ user quyết định loại trừ hoặc giảm scope ban đầu.

## Đối chiếu kết thúc

Dùng [vòng thực thi và readback](responsibility-loop.md). Join inventory/roles/journeys độc lập với workload và kết quả. `reconcile_responsibilities` chỉ kiểm cases được truyền vào; rỗng hoặc observed toàn selected cases không là whole-track complete. Thiếu inventory rõ ràng phải nêu discovery incomplete.

### Ý nghĩa kết quả từng input

Với input/kỹ thuật được chọn theo product, xác định câu hỏi cần trả lời và điều kiện khép tương ứng: validation, lookup, tạo/lưu, phản hồi hoặc chuyển trạng thái khi liên quan. Đối soát ở mức này để traffic của input, role hay nhánh khác không che phần thiếu; không tạo mọi tổ hợp rule × input × role × state hoặc schema/bộ bằng chứng mới.

Câu hỏi và điều kiện khép lấy từ chức năng/input/sink thuộc scope trước chọn workload, không suy ngược từ nhánh mà payload tình cờ chạm được. Nếu product tạo ra trách nhiệm kiểm xử lý/tạo/lưu thì không tự đổi mục tiêu thành chỉ validation/duplicate để khép track. Một baseline tạo mới và một campaign kiểm duplicate vẫn là hai quan sát khác nhau; chưa thay trách nhiệm active trên nhánh tạo mới khi nhánh đó áp dụng. Điều này không bắt mọi input phải tới lưu trữ: applicability theo loại input/kỹ thuật và product vẫn cần được đánh giá cụ thể.

- Input đã phân bổ cho active phải có biến đổi thực tới ứng dụng và kết quả được đọc theo câu hỏi đó. Baseline `null`, trường bị scanner bỏ qua hoặc campaign có traffic ở trường khác không khép input này. Chuẩn bị seed hợp lệ/kỹ thuật phù hợp hoặc quyết định applicability có căn cứ; một kỹ thuật N/A không khép mọi câu hỏi của input.
- Phân loại phản hồi theo ý nghĩa thực: boundary validation đúng hợp đồng, denial dự kiến, mất auth, fixture/sibling chặn ngoài ý muốn hoặc đã tới bước xử lý cần kiểm. HTTP status, scan terminal và số request không tự xác định lớp này; dùng response/readback và source/spec sẵn có khi cần. Chưa xác định được thì giữ mục liên quan mở, không suy diễn đã tới handler/lưu trữ.
- Boundary/denial có thể khép đúng câu hỏi đã chọn cho nó. Nếu câu hỏi là xử lý/tạo/lưu mà uniqueness, field liên quan hoặc state chặn trước đó, giữ riêng kết quả boundary đã có và tiếp tục phần mục tiêu còn thiếu. Không bắt mọi payload được chấp nhận, trả 2xx hoặc tới DB; không coi mọi 400/409 là thiếu coverage.
- Baseline thành công trước scan chưa bảo đảm fixture còn hợp lệ trong active. Chuẩn bị uniqueness, cặp trường phụ thuộc và object/state phù hợp cho lượt tiếp trong quyền; kiểm phản hồi/trạng thái sau mutation ở mức cần thiết. Kết quả PUT không tự thay POST tạo mới hoặc nhánh nghiệp vụ khác. Reconcile ACK/state trước retry, không nới guard hay sửa product để payload đi qua.

Kết quả xử lý dựa vào hợp đồng và nội dung phản hồi, không chỉ HTTP 2xx: trang login, lỗi nghiệp vụ trong HTTP 200 hoặc phản hồi do guard sinh không thay kết quả handler cần kiểm. Với xử lý bất đồng bộ, HTTP 202/job ACK chỉ xác nhận tiếp nhận; câu hỏi yêu cầu kết quả xử lý còn cần trạng thái/kết quả của đúng job/object qua interface sẵn có. Pending/chưa biết thì đọc trạng thái và tiếp tục phần độc lập, không gửi lại mutation chỉ vì chưa có kết quả cuối. Không buộc mọi ca phải có DB trace hoặc một kiểu readback duy nhất.

### Kết luận toàn track

- Mọi method–route thuộc track phải có thao tác/kết quả hoặc chưa thực hiện với lý do cụ thể. Hai track BE vẫn cần DAST ZAP thật; BOLA vẫn xét đủ endpoint–role, ownership và state quan trọng.
- Còn API/role hoặc câu hỏi input/kỹ thuật thuộc trách nhiệm chưa được xử lý thì không gọi toàn nhiệm vụ hoàn tất. Lỗi ghi rõ không tự khép nghĩa vụ; tiếp tục nhánh đủ điều kiện và sửa lỗi cục bộ trong scope.
- Khi đủ thao tác theo scope nhưng exploit/policy chưa được xác nhận, nêu giới hạn nhận định; không tự biến scan thành chương trình assurance mới.
- Zero alerts không chứng minh an toàn. Technical pass, report có sẵn và hai file kết quả không là release sign-off.

Trước kết thúc hỏi: **Còn phần việc còn mở nào mà Agent chưa đưa tới một quyết định xử lý có căn cứ ?** Đối chiếu cả trách nhiệm chưa nằm trong workload. Có quyết định chạy/sửa/chuẩn bị không đồng nghĩa đã thực hiện; còn bước hợp lệ trong nhiệm vụ thì tiếp tục. Dependency có căn cứ cho phép bàn giao partial khi không còn nhánh đủ điều kiện, không biến thành scope complete. Giới hạn exploit/policy giữ riêng với execution và coverage. Chi tiết quyết định ở [khắc phục](local-remediation-and-continuation.md#quyết-định-cho-phần-việc-còn-mở).

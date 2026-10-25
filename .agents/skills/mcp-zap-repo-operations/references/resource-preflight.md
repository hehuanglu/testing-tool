# Resource preflight và xử lý thiếu dung lượng/RAM

Đọc trước workload nặng hoặc khi preflight báo thiếu tài nguyên. Mục tiêu là xác
định bottleneck và đưa ra bước xử lý có căn cứ, không dừng ở một con số free-space.
Đây là hướng dẫn chẩn đoán/điều phối; không thay threshold hoặc tiêu chí admission
của runner để vượt gate. Lỗi implementation đo/cấp phát hoặc orchestration được
sửa và kiểm chứng theo [khắc phục cục bộ](local-remediation-and-continuation.md),
rồi đo lại. Một mode nhẹ có contract riêng không tự thừa hưởng gate của
mode scanner/browser; vẫn kiểm prerequisite thật của từng nhánh.

Khi nhiều lượt gây khó theo dõi dữ liệu/resource hoặc cần diễn giải stop/recovery,
đọc [retention, cap và failure domain](retention-stop-and-recovery.md). Không cần
fault injection hay retention index mới để hoàn thành một preflight thường.

## Đo đúng trước khi khuyến nghị

- Ghi thời điểm, filesystem chứa output thật, Docker context và workload sắp chạy.
  Dùng `df -k OUTPUT_PARENT` cho host. Nếu Docker disk image nằm trên volume khác,
  đo volume đó riêng; free trong Linux VM không phải host free và ngược lại.
- Với workload dùng safety contract, lấy reserve/growth/calibration hiện hành từ
  plan/source/sidecar. W4 hiện dùng preflight `2×estimatedGrowth + 2GiB reserve`,
  runtime reserve2GiB, cùng memory/sampling/stop requirements; fixed8GiB floor đã
  được người dùng bỏ ngày19/10/2026. Không áp dụng snapshot này thay source hiện tại,
  coi đủ disk là đủ admission, hoặc dùng calibration HTTP cho workload HTTPS/browser
  khác. Thiếu calibration thì ghi chưa tính được required headroom chính xác.
- Kiểm `docker system df` và chỉ dùng `docker system df -v` khi cần attribution.
  Tách images/layers shared, writable containers, volumes, build cache. Không cộng
  nguyên image SIZE của mọi tag vì có layer dùng chung. Reclaimable theo Docker
  không chứng minh object có thể xóa: image không có container vẫn có thể là pinned
  baseline/client image; volume LINKS0 vẫn có thể là backup hoặc dữ liệu người dùng.
- Docker Desktop macOS: dùng vị trí disk image thực tế (đường mặc định chỉ là gợi ý),
  `du -k Docker.raw` hoặc `stat` allocated blocks để đo chiếm chỗ thật; `ls -lh`
  thường là logical maximum. Không kết luận file228GiB đang chiếm228GiB. Docker.raw
  đã gồm dữ liệu images/volumes; không cộng lại chúng vào host total.
- Tách RAM khỏi disk: `memory_pressure -Q`, `sysctl vm.swapusage` và process RSS
  theo `ps -axo pid,rss,comm | sort -k2,2nr` khi hữu ích. RSS chỉ là snapshot, không
  cộng process RSS thành physical-memory accounting. Không in full command args
  hoặc environment có thể chứa credential. Không gọi thiếu disk là thiếu RAM.

Preflight thường chỉ cần các phép đo trên. Không mặc định quét đệ quy toàn home,
chạy toàn bộ suite, khởi tạo helper container hoặc đọc dữ liệu cá nhân cho mọi run.
Status-only giữ read-only, không tạo container để đo storage. Khi runner yêu cầu
VM measurements, dùng measurement path hiện có và ownership của đúng run; nếu chưa
đo được thì ghi thiếu, không suy từ `docker system df`.

## Khi dung lượng thấp: tự tìm nguyên nhân trong scope chỉ đọc

Đi từ tổng quan xuống nhánh lớn, giới hạn độ sâu/thời gian và số kết quả. Trên máy
này `du -x -k -d 1` hữu ích cho home, `/Applications`, `~/Library/Application Support`,
`~/Library/Containers`, `~/Library/Group Containers`, project root và `.codex`.
Chỉ mở rộng nhánh thật sự lớn. Dừng tiến trình đo dư thừa của chính lượt chẩn đoán
nếu trùng traversal; không kill tác vụ người dùng. Đọc size/path là đủ, không cần
đọc message DB, browser history, credential file hay nội dung evidence private.

Phân nhóm để hướng dẫn đúng:

- App bundle trong `/Applications`: dung lượng cài đặt. Quit app không xóa bundle.
- App data: browser profiles, chat attachments, simulator/emulator images, downloaded
  resources, app installer staging. Không gọi toàn bộ Application Support/User hay
  Containers là cache. UUID container chưa map được app thì ghi chưa xác định;
  permission denied không phải size0 và không là quyền vượt macOS privacy control.
- Developer/project: dependencies/build outputs, git/worktrees, corpora, sessions,
  reports/private browser profiles và backups. Artifact/evidence có retention hoặc
  source pin phải giữ; hướng dẫn archive có kiểm chứng/chuyển ổ thay vì xóa trực tiếp.
- Cache/log/temporary: phân biệt cache tái tạo được với session, local history,
  IndexedDB, user data, update đang chạy. Tên `cache` hoặc `in_progress` chỉ là dấu
  hiệu để kiểm tra, không là bằng chứng bỏ được. Không đọc file nội dung để tìm secret.
- System/VM: swap, sleepimage, APFS snapshots/purgeable. Có thể đọc snapshot list và
  deleted-open-file metadata khi `df`/`du` lệch lớn; không xóa swap/sleepimage/snapshot.
  macOS-protected directories và shared/cloned/sparse files làm số liệu không khớp
  tuyệt đối; ghi phần chưa quan sát, không gán chênh lệch thành một app chưa xác minh.

Không đếm trùng `/Applications` với `/System/Volumes/Data/Applications`, thư mục cha
với con, hoặc Docker.raw với objects bên trong. Ghi đơn vị rõ (`GiB = bytes/2^30`;
`du -k` ra KiB), measurement coverage/permission errors và thời điểm. Một snapshot
cho biết contributors hiện tại; muốn kết luận tăng liên tục cần so với snapshot
cũ tương thích. Không khẳng định memory leak/disk leak từ một lần đo.

## Hướng dẫn hành động dựa trên bằng chứng

Nếu **thiếu RAM/memory pressure**: đề xuất đóng bớt browser tab/app đo được đang
dùng nhiều RAM, lưu công việc rồi Quit bình thường. Cho biết chỉ kỳ vọng giảm
working set/swap growth; không hứa lấy lại toàn bộ swap ngay hoặc tăng disk free
một lượng chính xác. Chỉ đề xuất stop stack thử nghiệm khi ownership và tác vụ
đang dùng đã rõ. Quit Docker làm dừng toàn bộ product/scanner container; không coi
là thao tác vô hại để tiếp tục chính assessment cần Docker.

Nếu **thiếu disk**: ưu tiên chỉ ra đúng path/nhóm lớn, owner/app và lựa chọn cụ thể:

1. App-managed removal cho downloaded media/resources hoặc emulator không dùng;
   xem dữ liệu cần giữ trước. Gỡ app không dùng chỉ thu hồi phần đo được; app data
   có thể còn lại. Di chuyển dữ liệu lớn sang ổ khác khi cần giữ.
2. Cache/installer staging đã xác minh không còn tác vụ dùng có thể là candidate
   cho cleanup phạm vi hẹp. Báo bytes đo được và tác động rebuild/download lại;
   đó là upper-bound candidate size, không hứa cùng lượng `df` tăng ngay.
3. Archive evidence/backups chỉ khi được cho phép, có đủ nơi chứa và kiểm hash/
   restore trước xóa bản gốc. Nén ngay trên ổ sắp đầy cần thêm headroom, không mặc
   định đề xuất như một biện pháp không tốn dung lượng.
4. Docker chỉ xét object IDs cụ thể đã đối chiếu labels/mounts/references. Không tự
   chạy system/volume prune, `down -v`, đổi disk-image-size hoặc xóa/move Docker.raw.
   Muốn đổi location dùng giao diện Docker; muốn reclaim dùng quy trình đã được
   người dùng cho phép sau khi inventory/bảo toàn dữ liệu. Không chạy lệnh privileged
   reclaim chỉ để audit.

Không tự quit/stop/delete/di chuyển chỉ từ yêu cầu “kiểm tra nguyên nhân”. Nếu bước
tiếp theo cần mutation, chuẩn bị danh sách path/ID, size, ownership, tác động và
phần được giữ để người dùng duyệt phạm vi cụ thể; tái dùng quyền cleanup còn hiệu
lực đúng scope, không hỏi lại. Không cài cleanup app hoặc đổi autostart/config để
chữa một kết quả preflight nếu người dùng chưa yêu cầu.

Sau hành động đã được phép, đo lại đúng host filesystem, Docker image allocated
blocks/VM free và memory theo nhu cầu; xác nhận product/scanner/evidence còn nguyên.
Khi preflight vừa đủ nhưng provisioning làm xuống reserve, kiểm tăng trưởng thực
và workload đồng thời, tuần tự hóa bước nặng, tránh build/copy trùng và tái dùng
artifact đúng pin khi entry hỗ trợ. Cleanup chỉ resource tạm của run theo quyền
có thật; không hạ reserve hoặc tự xóa evidence. Đây là phần khắc phục phải đánh
giá trước khi chỉ báo resource-blocked và kết thúc. Snapshot cũ thiếu không chặn
retry sau khi prerequisite đã được kiểm lại và thực sự đủ.
Chỉ retry mode bị block sau khi **mọi** prerequisite của mode đó đạt; không rerun
POST/scan start đã mất ACK hoặc các nhánh đã hoàn thành chỉ vì disk vừa đủ hơn.

## Đầu ra tối thiểu cho người dùng

Nêu bottleneck chính; free/required/shortfall khi tính được; nhóm app/data lớn nhất
với size thực và giới hạn phép đo; các bước ưu tiên kèm tác động. Phân biệt rõ
“tắt app giúp RAM”, “dọn/chuyển file giúp disk” và phần có thể reclaim nhưng chưa
được phép. Khi blocked, đưa bước khắc phục cụ thể thay vì chỉ báo gate fail. Giữ
nguyên execution/evidence/security/cleanup/gate status của từng mode và tiếp tục
phần độc lập đã đủ điều kiện. Báo cáo chẩn đoán mới không sửa manifest evidence cũ.

Nguồn tham khảo (kiểm tra lại khi đưa hướng dẫn sản phẩm thay đổi theo phiên bản):
[Apple: Free up storage](https://support.apple.com/en-au/102624),
[Docker Mac FAQ: actual disk usage](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/macfaqs/).


FE anonymous có transport/journey research lane riêng: đọc [FE anonymous research](fe-anonymous-research.md) khi nhánh FE được chọn. Không ép qua backend HTTP binding; backend-only giữ prerequisites cũ.

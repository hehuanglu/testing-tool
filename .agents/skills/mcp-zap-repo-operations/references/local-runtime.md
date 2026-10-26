# Runtime local hoặc connector đã cấu hình

Runtime được discovery tại lượt hiện hành, không lấy endpoint, ports, Compose project, profile hoặc image ID của máy dev làm mặc định. Đọc [setup skill](setup.md) để phân biệt tài nguyên bundled, runtime scanner và product.

## Kiểm tra hiện tại

Với connector MCP đang có, gọi native `zap_passive_scan_status` khi cần kiểm kết nối/backlog. Nó chỉ chứng minh connector và backlog tại thời điểm gọi; không chứng minh mọi producer đã dừng hoặc assessment đã hoàn tất. Client→MCP auth khác ZAP→product auth.

Chỉ dùng preflight Docker khi deployment/executor được chọn phụ thuộc Docker. Daemon không sẵn vẫn cho phép source discovery; ghi nhánh runtime bị chặn và tiếp tục phần độc lập. Không đổi context/restart/rebuild để biến preflight thành pass.

Khi đã có quyền kiểm runtime local:

```sh
docker context show
docker version
docker compose version
docker ps --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
```

Lấy riêng labels Compose working_dir/config_files/project, container ID, image ID, state và mount destinations của installation liên quan. Không xuất Config.Env/full inspect hoặc secrets. Product và scanner có ownership riêng; không stop product để lấy port hoặc vượt lỗi.

Nếu có checkout scanner đã xác minh (`MCP_ZAP_REPO`), đọc help/source của `bin/self-serve-doctor.sh` rồi dùng doctor của checkout đó với endpoint/credential tương ứng. Doctor không start scan hoặc recreate stack; readiness không tự là capability qualification. Không truyền API key trong argv.

## Start/stop đúng installation

Chỉ thay đổi runtime khi yêu cầu cần và ownership/config/ports đã xác minh. Dùng đúng Compose project, env file và toàn bộ file set lấy từ installation; không giả có dev/auth override. Chạy `config --quiet` để kiểm cấu hình mà không in secret. Trước stop/restart xác định run đang dùng scanner và xử lý đúng operation/job; backlog 0 không cho phép huỷ scan của người khác.

Ưu tiên start container đã dừng bằng file set đã xác minh, stop giữ dữ liệu khi phù hợp. Build/up chỉ khi nhiệm vụ cần và đã đọc source/status/image trước/sau. Không mặc định force-recreate, bootstrap --force, down -v, đổi keys hoặc bật experimental auth. Release/dev/auth/OpenAPI-content là các topology khác nhau; đọc hướng dẫn của checkout scanner hiện hành trước chọn.

Docker/browser/images/JAR riêng của assessment được admission bởi executor tương ứng. Không sửa pins/gate hoặc lấy binary có sẵn làm bằng chứng source-to-image. Đo tài nguyên theo [preflight](resource-preflight.md) trước workload nặng; không prune/reset DB để vượt lỗi.

## Chẩn đoán hữu hạn

- Port trùng: xác định listener/container/project, không stop ứng dụng khác để lấy port.
- Health/auth fail: kiểm state/transport/profile của đúng installation, lưu lỗi đã lọc; không đổi surface/keys khi chưa rõ nguyên nhân.
- Tool không thấy: so runtime tools/schema và scopes, guided/expert; không giả engine thiếu chức năng chỉ từ registration.
- Queue restart: kiểm backend, lease/fence và operation identity; in-memory không bảo đảm resume.
- Không có source scanner: vẫn dùng connector hiện có khi đủ capability; chỉ các bước build/doctor/source bị thiếu dependency, không khẳng định chúng đã chạy.

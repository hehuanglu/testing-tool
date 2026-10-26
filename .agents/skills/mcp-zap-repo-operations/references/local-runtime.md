# Local runtime

## Trạng thái đã quan sát ngày 18/10/2026

macOS arm64; Docker29.8.1, Compose5.5.1. Repo HEAD `e2c8ee650ac4fad2984de65d5255c22a862f2f61`, source version0.16.0, dirty JSON bearer spike. MCP chạy image `mcp-zap-server:dev`, ID `sha256:85b5ff8460ca708f07fb14a89c6ae1990632e6bb4741e6edde3773dede5f120f`; ZAP2.17.0. Không có attestation chứng minh image đó được build từ dirty source hiện tại.

Endpoint MCP `http://127.0.0.1:7456/mcp`; ZAP host8090, Juice Shop3001→container3000, Petstore3002→container8080. Các port bind127.0.0.1. `http://juice-shop:3000` và `http://petstore:8080` là URL từ network scanner; host port không phải container port.

MCP config quan sát: API-key, guided, JWT disabled, in-memory jobs, single-node coordinator, OpenAPI content disabled. History durability phải kiểm tra riêng; không suy từ queue backend. Private-network/localhost allowed trong Compose local không là egress isolation hoặc quyền quét mọi LAN target.

Compose labels của cả bốn service cùng trỏ đúng repo và ba file theo thứ tự:

1. `docker-compose.yml`
2. `docker-compose.dev.yml`
3. `examples/authenticated-scanning/docker-compose.auth-profile.yml`

Profile và secret được mount read-only từ workspace `.zap-auth/`. Chỉ kiểm tra path/mode/ownership khi cần; không đọc credential để làm inventory. Đọc `examples/authenticated-scanning/README.md` trước thay đổi topology này.

## Kiểm tra hiện tại

Chỉ dùng preflight Docker dưới đây khi deployment hoặc executor của giai đoạn
thực sự phụ thuộc Docker. Đường dẫn product/source hợp lệ vẫn cho phép discovery
offline khi daemon không sẵn; ghi nhánh Docker bị chặn và tiếp tục phần độc lập.
Không restart/rebuild/đổi context để biến preflight thành pass. Phân biệt input
product/target sai cần user sửa với lỗi scanner/runtime cục bộ có thể chẩn đoán và
khắc phục theo [quy trình hiện có](local-remediation-and-continuation.md).

Trước workload nặng hoặc khi thiếu disk/RAM, dùng
[resource preflight](resource-preflight.md) để đo host/Docker/memory, chẩn đoán
nhánh chiếm chỗ và đưa hướng dẫn cụ thể. Không mặc định quit app giúp disk hoặc
tự cleanup để vượt gate.

Từ repo đã xác nhận:

```sh
git status --short
git rev-parse HEAD
docker context show
docker version
docker compose version
docker ps --filter label=com.docker.compose.project=mcp-zap-server --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
```

Lấy riêng labels `com.docker.compose.project.working_dir` và `com.docker.compose.project.config_files`, container ID, image ID, state và mount destinations. Không xuất `Config.Env` hay full inspect. Khi cần effective config, parse riêng trong process và chỉ in các trường cho phép; `config --quiet` xác minh cấu hình mà không in secrets.

Với kết nối đang có, gọi native `zap_passive_scan_status`. Nó chứng minh connector này hoạt động và backlog tại thời điểm gọi; không chứng minh tất cả producers đã dừng, scan đã hoàn tất hay client khác kết nối được.

Khi cần xác minh server endpoint từ checkout:

```sh
./bin/self-serve-doctor.sh
```

Doctor đọc MCP key từ `.env` trong process; không truyền `--api-key`. Nó kiểm tra health, auth rejection, initialize, tools/list, guided visibility và passive status. Nó không start scan hoặc recreate stack. Chỉ dùng endpoint/credential tương ứng installation đã xác nhận; environment override có thể khác `.env`.

## Chạy/dừng đúng topology

Các lệnh sau chỉ dùng khi yêu cầu cần thay đổi runtime và ownership/ports/config đã xác minh. Không chạy như audit mặc định.

**Stack hiện tại dev + auth:**

```sh
cd '/Users/hahoangloc/Working/testing tool/mcp-zap-server'
docker compose --project-directory "$PWD" --env-file "$PWD/.env" -p mcp-zap-server \
  -f "$PWD/docker-compose.yml" -f "$PWD/docker-compose.dev.yml" \
  -f "$PWD/examples/authenticated-scanning/docker-compose.auth-profile.yml" config --quiet
```

Dùng cùng prefix/file set với `start --wait --wait-timeout 300` để chạy lại container đã dừng mà không rebuild; `stop` để dừng giữ dữ liệu. Khi thật sự cần cập nhật source/config, dùng cùng file set với `up -d --build --wait --wait-timeout 300`, rồi doctor. Rebuild có thể đưa dirty spike vào runtime; ghi source/status/image trước và sau, không bật experimental auth. Không thêm `--force-recreate` nếu không cần.

Trước stop/restart xác định có run đang dùng scanner và xử lý đúng operation/job của nó; không hủy scan của chat khác vì thấy backlog0. Sau start/up kiểm tra health và authenticated readiness một lần; cấu hình client không cần viết lại khi endpoint/key không đổi.

**Release thuần khi được chọn rõ:** đọc upstream setup skill và `docs/getting-started/SELF_SERVE_FIRST_RUN.md`; `./bin/bootstrap-local.sh --start` dùng release tag xác định và `.env` hiện có. Bootstrap không dùng development override, không phù hợp restart stack auth hiện tại. `--force` thay `.env` và xoay cả hai keys.

**Dev thuần:** `./dev.sh` dùng base+dev, build local rồi doctor. Nó bỏ auth override; chỉ phù hợp deployment không dùng profile.

**OpenAPI content:** `docker-compose.openapi-content.yml` là override staging tùy chọn. Cần pre-provision thư mục, quyền writer/reader và enable flag theo `docs/src/content/docs/scanning/api-schema-imports.md`. Thêm nó vào đúng file set đã chọn; không bật tùy tiện lên stack chỉ để kiểm tra capability.

## Chẩn đoán có giới hạn

- Port trùng: map listener đến đúng container/project; không stop ứng dụng khác để lấy port.
- Doctor fail: lưu thông báo đã lọc, kiểm tra một lượt state/health/transport/auth phù hợp. Không sửa key hoặc đổi surface trước khi xác định nguyên nhân.
- Client không thấy tool: đối chiếu native client, guided/expert và scopes; doctor không chứng minh client đó đã reload. Không mở rộng quyền hoặc đổi server surface chỉ để hiện tool.
- Queue restart: cần backend thực tế, worker lease/fence và operation identity; đọc queue runbook. In-memory không bảo đảm phục hồi qua restart.
- `ha.sh`: hiện thiếu `docker-compose.ha.yml` và nginx template; script chủ động fail trước mutation. Không tự tạo HA config để coi setup đã đủ.
- Không dùng hướng dẫn `down -v` trong tài liệu test product như một bước cleanup chung. Đây là target riêng, không thuộc scanner stop.

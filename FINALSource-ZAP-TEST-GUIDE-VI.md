# Hướng dẫn kiểm thử `finalsource` bằng `mcp-zap-server`

Ngày chạy mẫu: 2026-10-17  
Môi trường: macOS + Docker Desktop, dữ liệu test cô lập

## 1. Trạng thái đã thiết lập

- `finalsource` đang chạy tại `https://localhost:8080`.
- Vì ZAP chạy trong container, URL target phải dùng là `https://host.docker.internal:8080`.
- Stack test dùng project Compose riêng: `finalsource-zap-test`.
- `mcp-zap-server` v0.16.0 đang chạy tại `http://localhost:7456/mcp`.
- ZAP 2.17.0 đang chạy nội bộ tại `http://localhost:8090`.
- Self-serve doctor đã đạt toàn bộ kiểm tra kết nối, xác thực MCP, discovery tool và kết nối ZAP.
- Đã chạy HTTP Spider, Client Spider, passive scan, active scan trang web, import OpenAPI và active scan API.
- Database cũ không bị xóa. Volume gốc vẫn còn và có thêm bản sao `finalsource_mysql_data_backup_20261017`.

> Không chạy active scan trên production. ZAP có thể gửi payload phá hoại hoặc làm thay đổi dữ liệu. Chỉ chạy trên môi trường và tài khoản test được phép.

## 2. Kết quả baseline hiện tại

Phạm vi quét không đăng nhập:

- UI/SPA: `/`, `/login` và các static asset được crawl.
- OpenAPI: `/docs-json` được import; ZAP đã gọi các route auth, accounts, bills, categories, expenses, goals, savings và transactions.
- Active scan API hoàn tất 100%; passive backlog còn 0.

ZAP ghi nhận 333 alert instance, nhưng 281 instance là `User Agent Fuzzer` mức Informational. Vì vậy không nên dùng con số 333 như số lượng lỗi nghiệp vụ.

| Mức | Nhóm đáng chú ý | Nhận định tester |
| --- | --- | --- |
| Medium | CSP wildcard; `style-src 'unsafe-inline'`; một response thiếu CSP | Cần sửa/cân nhắc hardening. Kiểm tra riêng response HTML và static asset trước khi tạo bug trùng lặp. |
| Medium | `Application Error Disclosure` tại `/docs-json` | ZAP kích hoạt response chứa `Internal Server Error`. Cần tái hiện request/payload trong report và kiểm tra log backend; có thể là false positive do tài liệu API. |
| Low | Thiếu HSTS ở một số response | Có thể do cấu hình `add_header` theo `location` của nginx. Kiểm tra từng URL/response thực tế. |
| Low | Thiếu `X-Content-Type-Options` ở một số response | Nên đặt nhất quán `nosniff`, đặc biệt cho static content. |
| Low | `X-Powered-By: Express` trên các API | Nên tắt để giảm lộ công nghệ backend. |
| Low | `Debug Error Messages` tại `/docs-json` | Cùng evidence `Internal server error`; gộp triage với Error Disclosure, không mở hai bug nếu cùng nguyên nhân. |
| Info | cache-control, suspicious comment, modern web app, user-agent behavior | Chỉ mở bug sau khi xác nhận có dữ liệu nhạy cảm hoặc hành vi sai; đa số là tín hiệu điều tra. |

Không có alert High trong baseline này. Điều đó **không** chứng minh ứng dụng không có lỗ hổng: phần lớn route nghiệp vụ trả 401 vì lượt quét chưa đăng nhập.

Báo cáo HTML: `test-artifacts/finalsource-zap-report-2026-10-17.html`  
SHA-256: `e9b2bb7426308667d964bff6dbd5ff66c8182a0a42ec547b13c2d5ee866b13ae`

## 3. Khởi động và dừng môi trường

### Khởi động `finalsource`

```bash
cd "/Users/hahoangloc/Working/testing tool/finalsource"
docker compose -p finalsource-zap-test up -d --build --wait
```

Kiểm tra:

```bash
curl -k -I https://localhost:8080
docker compose -p finalsource-zap-test ps
```

### Khởi động `mcp-zap-server`

```bash
cd "/Users/hahoangloc/Working/testing tool/mcp-zap-server"
./bin/bootstrap-local.sh --start --wait-timeout 600
```

Kiểm tra lại toàn bộ wiring:

```bash
./bin/self-serve-doctor.sh
```

### Dừng sau khi test

```bash
cd "/Users/hahoangloc/Working/testing tool/finalsource"
docker compose -p finalsource-zap-test stop

cd "/Users/hahoangloc/Working/testing tool/mcp-zap-server"
docker compose stop
```

Không thêm `-v` nếu muốn giữ database test và artifacts. `down -v` sẽ xóa volume của stack tương ứng.

## 4. Kết nối MCP vào Codex

Endpoint là `http://localhost:7456/mcp`; header xác thực là `X-API-Key`.

Trong Codex, mở Settings → MCP servers → Add server → chọn Streamable HTTP:

1. URL: `http://localhost:7456/mcp`
2. Header name: `X-API-Key`
3. Copy API key vào clipboard mà không in ra terminal:

   ```bash
   cd "/Users/hahoangloc/Working/testing tool/mcp-zap-server"
   sed -n 's/^MCP_API_KEY=//p' .env | pbcopy
   ```

4. Dán vào header value, Save, rồi restart Codex để reload tool catalog.
5. Kiểm tra bằng `codex mcp list` nếu dùng CLI.

Không commit `.env`, không dán API key hoặc mật khẩu tài khoản target vào prompt.

Bạn chỉ thêm MCP connection **một lần**. Không cần thêm lại URL/header khi dùng một
guided feature khác đang được server đăng ký. Các trường hợp đặc biệt:

- Đổi `guided` sang `expert`: đặt `MCP_SERVER_TOOLS_SURFACE=expert` trong `.env`,
  recreate `mcp-server`, sau đó reconnect/restart Codex để gọi lại `tools/list`.
- Thêm hoặc sửa target auth profile: recreate `mcp-server` để profile được nạp;
  không đổi MCP URL/API key trong Codex. Auth session cũ hết hiệu lực và phải
  prepare/validate lại.
- Upgrade image có tool mới: restart server và reconnect Codex; không cần tạo một
  MCP connection mới nếu endpoint và credential không đổi.
- Đổi cơ chế truy cập MCP từ API key sang JWT: cập nhật header phía Codex rồi
  reconnect. JWT ở lớp này chỉ cho Codex gọi MCP, không đăng nhập vào target.

## 5. Prompt mẫu cho tester

Sau khi MCP đã xuất hiện trong Codex, có thể dùng prompt sau:

```text
Chỉ dùng các guided ZAP tools. Target được phép là
https://host.docker.internal:8080.

1. Crawl bằng strategy=client vì đây là React SPA.
2. Chờ crawl hoàn tất; nếu trạng thái nói completion chưa được xác nhận thì ghi caveat.
3. Chờ passive scan backlog về 0.
4. Import OpenAPI từ https://host.docker.internal:8080/docs-json với
   hostOverride=https://host.docker.internal:8080.
5. Chạy active scan cho https://host.docker.internal:8080/api.
6. Chờ scan hoàn tất và passive backlog về 0.
7. Trả findings summary trước, sau đó drill down từng alert Medium/High với instance cụ thể.
8. Tạo report HTML có baseUrl=https://host.docker.internal:8080 và đọc lại report qua MCP.
9. Xuất release evidence và customer handoff; nêu rõ mọi caveat.
Không quét host khác và không dùng expert tools nếu chưa hỏi tôi.
```

Trình tự tool mong đợi:

1. `zap_crawl_start` → `zap_crawl_status`
2. `zap_passive_scan_wait`
3. `zap_target_import`
4. `zap_attack_start` → `zap_attack_status`
5. `zap_passive_scan_wait`
6. `zap_findings_summary` → `zap_findings_details`
7. `zap_report_generate` → `zap_report_read`/`zap_report_read_chunk`
8. `zap_scan_history_release_evidence` → `zap_scan_history_customer_handoff`

## 6. Cách triage theo nghiệp vụ tester

Với mỗi alert, ghi ticket theo mẫu:

- Title: hành vi/rủi ro, không dùng nguyên tên rule một cách máy móc.
- Scope: URL, method, trạng thái đăng nhập, loại user và dữ liệu test.
- Preconditions: tài khoản/dữ liệu cần có.
- Steps: request hoặc thao tác UI tối thiểu để tái hiện.
- Actual vs Expected.
- Evidence: response headers/body đã che token, ảnh chụp và log liên quan.
- Impact nghiệp vụ: lộ dữ liệu, sửa/xóa dữ liệu, vượt quyền hay chỉ hardening.
- Reproducibility: số lần tái hiện; phân loại confirmed/false positive/needs review.

Ưu tiên kiểm tra thủ công:

1. **Phân quyền ngang:** tạo User A và User B; lấy ID account/goal/transaction của A; thử đọc/sửa/xóa bằng token B. Mong đợi 403 hoặc 404, không lộ dữ liệu.
2. **Tính đúng số dư:** tạo account, income, expense; xác nhận balance, expense summary và savings summary khớp phép tính và không cộng trùng khi refresh.
3. **CRUD và tính toàn vẹn:** create/edit/delete account, transaction, goal; kiểm tra quan hệ phụ thuộc, rollback và thông báo lỗi.
4. **Biên dữ liệu:** số tiền 0/âm/rất lớn/nhiều chữ số thập phân; ngày cuối tháng/năm; chuỗi Unicode; field rỗng; ID không tồn tại.
5. **Auth:** đăng ký trùng email, sai mật khẩu nhiều lần, token hết hạn/giả mạo, logout, back button, refresh, local/session storage.
6. **Validation đồng nhất:** cùng một dữ liệu sai phải bị chặn ở UI và API; response không lộ stack trace/SQL/internal path.
7. **Race/idempotency:** submit hai lần, hai tab cùng sửa/xóa, refresh sau POST.
8. **UX và accessibility:** keyboard-only, focus, label/error, contrast, responsive; ZAP không thay thế kiểm thử này.

## 7. Quét có đăng nhập: phần cần làm thủ công

`finalsource` đăng nhập bằng React + JSON API, lưu access token trong
`localStorage`/`sessionStorage`, rồi Axios gửi `Authorization: Bearer <token>`.
`mcp-zap-server` v0.16.0 hỗ trợ browser profile để headless Firefox đăng nhập và
Client Spider crawl trong trạng thái đã đăng nhập. Cơ chế session detection có thể
phát lại cookie hoặc header token, gồm bearer token, khi xác minh/crawl.

Điều này **không giống** với việc đưa một JWT có sẵn vào guided scan. Browser
profile chỉ được chấp nhận bởi `strategy: client`; guided active scan từ chối
browser session và chỉ nhận form-login session. Profile `kind: bearer` hoặc
`kind: api-key` hiện chỉ kiểm tra secret reference, chưa tự inject header vào
guided crawl/attack. Vì vậy coverage có đăng nhập của repo hiện bị giới hạn.

Để crawl UI sau đăng nhập:

1. Tạo một tài khoản test riêng tại `https://localhost:8080/register`; không dùng tài khoản thật.
2. Copy `examples/authenticated-scanning/auth-profiles.example.yml` ra thư mục riêng, đổi profile thành:

   ```yaml
   mcp:
     server:
       auth:
         bootstrap:
           profiles:
             - id: finalsource-browser
               kind: browser
               allowed-origin: https://host.docker.internal:8080
               credential-reference: file:/run/secrets/target_form_password
               login-url: https://host.docker.internal:8080/login
               username: EMAIL_TAI_KHOAN_TEST
               logged-in-indicator-regex: ".*Logout.*"
               logged-out-indicator-regex: ".*Login.*"
   ```

3. Tạo secret file chỉ chứa mật khẩu; đặt quyền theo hướng dẫn repo. Khai báo đường dẫn tuyệt đối trong `.env`:

   ```dotenv
   MCP_ZAP_AUTH_PROFILES_FILE=/duong/dan/tuyet/doi/auth-profiles.yml
   MCP_ZAP_FORM_PASSWORD_FILE=/duong/dan/tuyet/doi/target-form-password
   ZAP_API_READ_TIMEOUT_MS=60000
   ```

4. Khởi động bằng auth override, không dùng lại bootstrap script trong lúc profile đang bật:

   ```bash
   cd "/Users/hahoangloc/Working/testing tool/mcp-zap-server"
   docker compose \
     -f docker-compose.yml \
     -f docker-compose.dev.yml \
     -f examples/authenticated-scanning/docker-compose.auth-profile.yml \
     up -d --build --force-recreate --wait
   ```

5. Qua MCP: gọi `zap_auth_session_prepare` với profile `finalsource-browser` và
   target protected; gọi `zap_auth_session_validate`. Chỉ tiếp tục khi có đủ
   `Valid: true`, `Outcome: authenticated` và `likelyAuthenticated=true`.
6. Gọi `zap_crawl_start` với `strategy: client` và `authSessionId`. Xác nhận ZAP
   thật sự thấy ít nhất một trang/API protected và response thuộc đúng test user;
   trạng thái start thành công chưa đủ chứng minh đăng nhập.
7. Chờ passive backlog về 0 rồi đọc findings và sinh report. Không chuyển thẳng
   browser `authSessionId` sang `zap_attack_start`, vì tool sẽ từ chối.

Browser profile dùng khả năng tự nhận diện của ZAP nên input React không có `name`
không tự động được xem là lỗi cấu hình. Nếu prepare/validate vẫn thất bại, guided
workflow không hỗ trợ custom login steps, MFA hay CAPTCHA. Khi đó dùng ZAP Desktop
để kiểm thử/cấu hình auth trước, hoặc dùng native ZAP API/Automation Framework bên
ngoài wrapper có giới hạn của repo; không đưa password/JWT vào prompt hay ticket.

ZAP gốc có JSON authentication và header-based session management, nên về mặt
engine có thể lấy token từ JSON login response rồi thêm Authorization header.
Tuy nhiên `mcp-zap-server` v0.16.0 không cung cấp việc này như một guided bearer
scan: Automation Framework wrapper của repo cũng giới hạn session management và
không cho replacer/script jobs. Đây là nhánh expert/manual, không nên báo cáo như
coverage của guided workflow cho đến khi đã chứng minh request protected thực sự
mang token và trả dữ liệu của đúng user.

Nguồn kiểm chứng:

- Repo v0.16.0: [target authentication support](https://github.com/dtkmn/mcp-zap-server/blob/v0.16.0/docs/src/content/docs/getting-started/form-login-target-authentication.md)
- Repo v0.16.0: [authenticated scanning reference](https://github.com/dtkmn/mcp-zap-server/blob/v0.16.0/docs/src/content/docs/scanning/authenticated-scanning-best-practices.md)
- Repo v0.16.0: [Client Spider](https://github.com/dtkmn/mcp-zap-server/blob/v0.16.0/docs/src/content/docs/scanning/client-spider.md)
- ZAP engine: [JSON authentication](https://www.zaproxy.org/docs/desktop/start/features/authmethods/) và [header-based session management](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/session-header/)

## 8. Giới hạn đã quan sát

- Direct Compose mode ghi nhận scan là `started`; evidence ledger không tự chứng minh terminal success. Customer handoff vì vậy có trạng thái caveat dù API ZAP báo 100%. Muốn evidence mạnh hơn cần queue/PostgreSQL topology của repo.
- Client Spider trả 100% nhưng repo cảnh báo 100% cũng có thể là stopped; phải kiểm tra URL protected và nội dung authenticated.
- Scanner không xác nhận logic số dư, ownership, workflow, accessibility hay tính đúng của báo cáo tài chính.
- Active scan không đăng nhập chỉ đánh được bề mặt public/401; không đại diện cho coverage route protected.
- Self-signed TLS có thể gây cảnh báo trình duyệt; `curl -k` chỉ dùng local test, không phải cấu hình production.
- Alert count là số instance, không phải số bug. Cần gộp theo root cause và tái hiện.

## 9. Dọn dữ liệu sau test

Dừng stack là lựa chọn an toàn. Chỉ khi chắc chắn không cần dữ liệu test nữa mới xóa project test:

```bash
cd "/Users/hahoangloc/Working/testing tool/finalsource"
docker compose -p finalsource-zap-test down -v
```

Lệnh trên không nhắm tới volume gốc `security-vibe-coding_mysql_data` hay bản backup `finalsource_mysql_data_backup_20261017`.

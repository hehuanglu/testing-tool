# Delegated DAST candidate và actual live ZAP sink controls

Product authenticated DAST chưa được admit. Legacy P0 giữ containment. Đây là runbook của increment implementation, không là lệnh quét finalsource và không có override/force.

## Source và dependencies

- `finalsource_delegated.py`: exact numeric target binding, no redirects, JSON login, principal projection từ accounts.data.user_id, GET query policy giữ nguyên payload bytes. Login user/JWT claims/membership không thay subject oracle. Role protocol chưa quan sát: explicit role=None; role-bearing legacy callers vẫn exact equality. Transport records là holder observations, chưa independent wire attribution.
- `delegated_attestation.py`: immutable BrokerBinding và runtime target/scanner/holder snapshots; pinned byte replay trước/sau gate verification; deadline/epoch; source reservation và operation intent/ACK/no-replay. **ProofReplay là trusted executable interface; chưa có production semantic collector/replayer cho toàn gates.** Không deserialize JSON allow thành implementation. Tests dùng fake provider chỉ kiểm ordering/denial, không product admission.
- `delegated_holder.py`: tái dùng CredentialBroker/ActorSession, source resolution một lần, bootstrap epoch và per-dispatch guard/monitor. Instantiate chỉ trong holder đã được chứng minh process/platform isolation. Object Python không cung cấp isolation. Policy failure latches broker/producer; raw protected bytes chỉ về final-hop boundary.
- `delegated_scanner.py`: tái dùng Scanner/MCP schema validation, OperationLedger và read_report; selected named policy, owned operation ID, no start retry, producer/passive checks và native JSON+HTML full chunk/EOF/UTF8/hash reader. Không provision scanner hoặc nhận product credential. Runtime provider phải khóa inventory/rules/vectors/rate, supply attribution và terminal/stop recovery. Lớp này chưa là end-to-end executor.

Native path vẫn known persistence failure, experimental tắt. Delegated proof không mở native. Product business writes, DB seeding/reset/restart và browser không thuộc contract GET candidate.

`native_secret_gate.py` và `live_sink_pair.py` replay private raw history/page/count/EOF và typed session DB từ fresh zero/positive sessions, five encoding controls và writer terminal. NativeG3Replay tính denominator143 rồi từ chối141cặp còn thiếu. Nó chỉ nhận owned canary nguồn nội bộ. Unit integration nối concrete replay này vào RuntimeAttestor/DelegatedHolder xác nhận không gọi resolver khi incomplete/wrong epoch/target.

`private_source_broker.py` xử lý source gộp ngay trong isolated source broker: metadata-only file pin/no-follow read, projection một actor, grant bound run/plan/actor/build/origin/deadline. Server và client đều xác minh kernel UID/GID trước source I/O/frame tương ứng; callback trước/sau read, grant single-use kể cả lostACK. Audit inventory giữ cả unused actor password và historical registrationToken đã đọc. Actor holder chỉ nhận username/password của actor đó. Chưa mount/read credential product hoặc chứng minh platform boundaries.

## Actual sink diagnostic có thể thực thi

Từ package root, dùng `.venv/bin/python`. CLI hiện có chỉ nhận fresh work directory và external plan pin, không URL hoặc actor credential:

```sh
.venv/bin/python scripts/actual_zap_sink_control.py --help
.venv/bin/python scripts/actual_zap_sink_control.py prepare --work-dir /ABSOLUTE/FRESH/DIRECTORY
.venv/bin/python scripts/actual_zap_sink_control.py run --work-dir /ABSOLUTE/FRESH/DIRECTORY --expect-plan-hash EXTERNAL_HASH_FROM_PREPARE
.venv/bin/python scripts/actual_zap_sink_control.py recover --work-dir /ABSOLUTE/FRESH/DIRECTORY --expect-plan-hash ORIGINAL_EXTERNAL_HASH
```

Thay placeholders bằng output thật. `prepare` không gửi product HTTP hoặc đọc secrets, chỉ xác minh pinned image và snapshot source read-only. `run` dùng owned network=none, scanner tmpfs/core0/cap0/no-swap cgroup và resource sampling. Không suy host/VM acceptance từ các cờ đó. Control canary sinh bên trong child; actual HTTP qua ZAP proxy đến owned loopback target; đọc core.messages; save actual session; đợi writer terminal rồi chạy cùng SessionDbReadback JDBC và scanner_secret_audit framing. Exact five encoding families phải có trong actual HISTORY.REQHEADER. Actual headers của image này là SQL type12; không quảng bá BINARY family coverage. Duplicate occurrences trên các rows hợp lệ được đếm; duplicate typed-cell identity bị từ chối.

Raw seed/API messages/typed cells/logs nằm trong child/tmpfs, không Docker env/argv hoặc controller output. Controller chỉ nhận allow-listed metadata. Child output lạ bị chặn trước publication. Resource profile chỉ cho diagnostic này; không là product calibration. ProductRequests và activeRequests đều0. Positive controls cố ý đặt canary ở owned sinks, không phải leak từ credential product.

Plan/hash/source/image drift hoặc resource failure chặn. Không rerun attempted namespace. Lost create ACK reconcile đúng intent/name/image/label; recover chỉ stop/remove exact owned resource, không replay login/start. Recovery ghi file mới ở parent, không sửa status/attempt cũ. Nếu ownership hoặc terminal không xác nhận: quarantine. Không prune, restart borrowed containers hoặc xóa evidence.

## Kiểm chứng và handoff

Opt-in paired contract1.1 dùng cùng prepare/run/recover, thêm `--paired-audit` **chỉ ở prepare**:

```sh
.venv/bin/python scripts/actual_zap_sink_control.py prepare --paired-audit --work-dir /ABSOLUTE/FRESH/PAIRED_DIRECTORY
```

Khóa external plan hash từ prepare rồi dùng lệnh run/recover ở trên. Legacy1.0 vẫn mặc định. Collector dùng one-based positive `start` cho API messages và kiểm count trước/sau, unique IDs, full pages và EOF. Đây là behavior của [ZAP2.17 CoreAPI PaginationConstraintsChecker](https://raw.githubusercontent.com/zaproxy/zaproxy/v2.17.0/zap/src/main/java/org/zaproxy/zap/extension/api/CoreAPI.java). CoreAPI có image filtering; API inventory không tự chứng minh tất cả native persistence. Typed DB audit đọc mọi PUBLIC table/cell được reader hỗ trợ, không chỉ seeded headers. Trường quoted lowercase của Flyway được giữ đúng schema; SQL types/cell identity/terminal framing vẫn strict.

Source-channel control có CLI riêng chỉ tạo canary source trong owned Linux tmpfs; không nhận product URL, reference hoặc secret:

```sh
.venv/bin/python scripts/private_source_control.py --help
.venv/bin/python scripts/private_source_control.py prepare --work-dir /ABSOLUTE/FRESH/SOURCE_DIRECTORY
.venv/bin/python scripts/private_source_control.py run --work-dir /ABSOLUTE/FRESH/SOURCE_DIRECTORY --expect-plan-hash EXTERNAL_HASH_FROM_PREPARE
.venv/bin/python scripts/private_source_control.py recover --work-dir /ABSOLUTE/FRESH/SOURCE_DIRECTORY --expect-plan-hash ORIGINAL_EXTERNAL_HASH
```

Actor A/B dùng UID1003/1004, source broker UID1005, scanner-denial UID1000. Ten controls gồm wrong peer/server/plan, cross actor, prerequisite denial, A/B sessions, source replay và lostACK/no replay. Source chỉ đọc3lần; gated grant bị consume trước I/O; hai actor có epoch riêng. Detached server đọc public grant metadata đã stage trong tmpfs, không dựa stdin của detached exec. Kernel peer controls trong cùng owned netns không thay host↔VM transport/swap/dump proof, source zone topology hoặc product oracle/attribution.

Fresh checkpoint [paired A6 và source-channel A3](../../../test-artifacts/delegated-g3-20261020T133635Z/PROGRESS_VI.md) ghi current executable source pins, failed attempts và cleanup. Paired A6 có8API messages mỗi phase và5exact seeded HISTORY.REQHEADER cells trong positive DB;10là seed intents qua proxy, không phải số request app đã independently attributed. Không suy authenticated/active technique coverage từ các counts này.

```sh
PYTHONPATH=src:tests .venv/bin/python -m unittest test_live_sink_probe test_actual_sink_runner test_finalsource_delegated test_delegated_attestation test_delegated_scanner test_credential_broker test_auth_lifecycle -q
PYTHONPATH=src .venv/bin/python -m zap_assessment.capabilities check
```

Full suite cần chạy khi thay broker/session hoặc gate contracts. Readback/hash verifier là consistency, không là G3/security approval. Runtime result `pass` của diagnostic chỉ mô tả seeded history/session controls. Giữ execution/evidence/security/cleanup/gate riêng; gate vẫn block operational.

## Điều kiện còn thiếu trước product

1. Actual per-sink/lifecycle access, five-encoding controls, decoder completeness, forbidden live-case zero matches và browser locked absence proof trong denominator13×11. Success controls ở2sinks không thay143acceptance.
2. Host↔Docker VM secret transport, host/VM swap/dumps/diagnostics and crash lifecycle seeded collection; không có collector/provider hiện hành đủ chứng minh. Metadata sysctl/proc không đóng proof; không tự thay settings/restart môi trường.
3. Product source-broker topology/mount/UID/ownership và current fixture provenance được verify. Combined-reference projection đã có implementation/owned peer controls; không còn cần người dùng tự tạo per-actor secret files. Historical combined credential file trong workspace giữ reference; chưa mount/read, không copy vào new bundle hoặc resolve bằng host controller.
4. Independent product binding/epoch/positive/anonymous/invalid-session controls, final-hop egress/arrival attribution, exact scanner inventory và product workload calibration/stop/recovery.
5. Trusted operational ProofReplay + isolated runtime provider/entry nối prepare/preflight/run/recover/verify, complete product runs/reports/secret-audit/cleanup. Component tests và fake providers không thay những phần này.

Fixed-build regression và independent review chỉ claim khi có baseline/reviewer thật; không thêm chúng thành prerequisite giả cho delegated bounded GET contract. Thiếu role/refresh/revoke protocol ghi applicability, không sửa finalsource cho vừa checklist.

Checkpoint: [PROGRESS](../../../test-artifacts/delegated-dast-20261020T124540Z/PROGRESS_VI.md). Rollback từng file theo `source-before/`/change index của checkpoint, giữ evidence/failed attempts và dirty scanner spike.

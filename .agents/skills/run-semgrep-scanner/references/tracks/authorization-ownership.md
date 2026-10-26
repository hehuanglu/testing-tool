# authorization-ownership — Quyền chức năng, object và tenant

## Ý định, applicability và discovery

Base độc lập ORM: tìm actor–action–object/tenant/shared grants, handlers/jobs, persistence wrappers, model relations, list/bulk/export và lifecycle. Tên account/organization/workspace/member chỉ ví dụ, không whitelist. Đọc principal provenance và authoritative fields từ source/policy, không lấy regex ownership làm inventory. Function-level authorization không tự gọi BOLA.

## AUTHZ-01 — Actor có được phép thực hiện action/chức năng không?

- **Áp dụng/discovery:** privileged/business actions và entrypoints thuộc scope, kể cả jobs/library callers có trust khác.
- **Kỳ vọng/nguồn:** actor–action policy từ role/permission spec, ACL hoặc quyết định được cung cấp; source-only expectation có nhãn giả định.
- **Source/kỹ thuật:** search guard/middleware/policy/service calls, manual global/local registrations và privileged/exception paths; bundled ownership không đủ function-level coverage.
- **Control/giải thích khác:** global/inherited guards, service checks, trusted internal caller, delegated grants; không kết luận từ thiếu local decorator hoặc client menu.
- **Evidence/giới hạn:** locations registration/check/action và principal source, policy reference; không chứng minh runtime allow/deny hoặc gọi mọi quyền chức năng là BOLA.
- **Khép/bước tiếp:** action paths và control/policy đủ căn cứ cho câu hỏi; đọc service/caller/global config còn thiếu, policy chưa biết chỉ chặn phần phụ thuộc.

## AUTHZ-02 — Detail/read/update/delete có ràng buộc đúng object/owner/tenant/grant không?

- **Áp dụng/discovery:** object IDs/keys tới lookup và use/mutation; tìm persistence API thực, wrappers và principal binding.
- **Kỳ vọng/nguồn:** owner/tenant/shared grants theo model/authorization policy, gồm actor đặc quyền khi có; owner không bắt buộc tên userId.
- **Source/kỹ thuật:** bundled ID lookup/update/criteria candidates cho TypeORM shapes, search raw/custom repository; manual callers/prior checks → criteria → before-use authorization.
- **Control/giải thích khác:** `findOne({id})` chỉ candidate; prior checks/wrappers có thể enforce. Thêm predicate không chứng minh đúng principal; status/type khác ownership; principal từ client khác server authority.
- **Evidence/giới hạn:** locations identity/object/check/criteria/use, policy/control review và manual flow đúng nguồn; không suy toàn hệ thống thiếu check từ một lookup.
- **Khép/bước tiếp:** paths chọn có authoritative binding và controls đã đọc hoặc issue đủ claim; wrapper/owner tên lạ cần đọc tiếp, không bị bỏ do matcher vắng.

## AUTHZ-03 — Collection/list/search/filter/pagination/bulk/export có giữ scope không?

- **Áp dụng/discovery:** collection queries, count/aggregate, bulk IDs và export paths; inventory riêng khi khác detail flow.
- **Kỳ vọng/nguồn:** collection và từng phần tử theo tenant/grants/policy; counts, filters và export cũng có thể lộ thông tin.
- **Source/kỹ thuật:** bundled bulk/request-criteria candidates, search repository/SQL/filter builders; manual predicates trước query, per-element actions và serializer/export.
- **Control/giải thích khác:** global scoped repository, row-level policy có source/config được cung cấp, permitted cross-tenant admin, filters bị overwrite; detail check chưa bao phủ list.
- **Evidence/giới hạn:** collection construction/scope/use locations, policy và principal/control path; static không chứng minh dataset populated hoặc isolation runtime.
- **Khép/bước tiếp:** queries và bulk elements được review ở mức policy cần; đọc builders/wrappers hoặc policy/RLS config thiếu, giữ gaps đúng source.

## AUTHZ-04 — Parent–child/nested references và thay đổi quan hệ có nhất quán quyền không?

- **Áp dụng/discovery:** nested URLs/IDs, foreign keys, relation assignment/reparent, batch linking; tìm object chính và referenced objects.
- **Kỳ vọng/nguồn:** parent-child membership/tenant/grant consistency theo relation/business policy; quyền object chính không tự cấp quyền object tham chiếu.
- **Source/kỹ thuật:** search relation APIs/IDs/joins, manual validation trước use/link/write; ownership candidates chỉ gợi ý, custom rule có thể map wrapper riêng.
- **Control/giải thích khác:** DB constraints có thể bảo vệ existence/consistency nhưng không luôn actor authorization; service checks, shared grant hoặc intentional cross-tenant relations cần đọc.
- **Evidence/giới hạn:** cả hai object paths, check/criteria/write và principal locations; source không chứng minh DB constraints runtime nếu schema/deployment thiếu.
- **Khép/bước tiếp:** ràng buộc từng reference quan trọng đã đối chiếu; đọc schema/linked-object checks còn thiếu thay vì chỉ kiểm ID chính.

## AUTHZ-05 — Lifecycle/state transitions có thay đổi quyền hoặc điều kiện hành động không?

- **Áp dụng/discovery:** approve/publish/archive/transfer/lock, state-dependent reads/writes và privileged transitions.
- **Kỳ vọng/nguồn:** state machine/action policy từ business spec hoặc source hypothesis; xác định actor và trạng thái được phép trước/sau.
- **Source/kỹ thuật:** search transition methods/state predicates/events; manual check → transition/write, transaction/order và alternative callers. Bundled chưa có generic detector lifecycle.
- **Control/giải thích khác:** domain aggregate/invariant wrapper có thể enforce; state check không thay role/tenant binding, concurrent changes cần giới hạn nhận định.
- **Evidence/giới hạn:** state/control/mutation locations, expectation và assumptions; không khẳng định concurrency/lifecycle runtime đã kiểm.
- **Khép/bước tiếp:** transitions trong scope có preconditions/authority đã đọc; tìm aggregate/event handler khác hoặc giữ gap source/policy cụ thể.

## AUTHZ-06 — Client-controlled owner/tenant/protected fields có thể override authority không?

- **Áp dụng/discovery:** assignment/merge/spread/Object.assign/create/update/save với fields owner/tenant/role/state/grants thật của model.
- **Kỳ vọng/nguồn:** immutable/server-authoritative fields và allowed changes theo API/schema/policy; names không quyết định trust.
- **Source/kỹ thuật:** bundled ownership-name/body/spread/persistence candidates, search field writes và manual provenance, field allowlist, overwrite order tới actual persistence.
- **Control/giải thích khác:** server-derived input, runtime DTO filter, entity hooks, authoritative override sau spread, create chưa save; kiểm principal có verify/binding trước khi nhận giá trị.
- **Evidence/giới hạn:** source/validation/merge/write/control locations và policy; không copy giá trị nhạy cảm, không suy TypeScript type là runtime validation.
- **Khép/bước tiếp:** fields thực và write path được giải thích đủ; đọc hooks/callers/wrappers hoặc custom naming rule có fixture khi hữu ích.

## Mẫu ledger actor–action–object–relation–state

Mỗi protected operation trong scope ghi `{actor_source, action, object_or_collection, related_references, state_protected_fields, check_predicate, use_write, callers, locations, question_id, status, next_step}` trong result/review. Actor authority phải truy tới verifier/principal, predicates tới implementation thực; status do tester chọn theo mức câu hỏi.

Detail/update/delete có thể tách khi đường control khác; list/count/aggregate không được khép bởi detail check. Giữ trách nhiệm từng reference (ví dụ account và category) khi link/write. Owner predicate không tự khép quyền client thay state/protected fields. Chỉ gộp operation dùng chung control khi mapping callers đủ rõ.

Receiver method name chỉ gợi ý: Map/Set.delete là in-memory; service.update/custom wrapper có thể write thật; TypeORM import/type/constructor, transaction manager và alias cần truy provenance. Không whitelist tên repository hoặc loại service wrappers. DTO suffix/owner field chưa xác định input/output: đọc Body/Query/Param callers, response serializers, shared/aliased/inherited DTO; không exclude ResponseDto toàn cục.

## Mapping, thích nghi và khép track

[Catalog](../rule-catalog.md): `authorization-ownership-static.yml`, TS/Nest/TypeORM shapes, phần lớn inventory-candidate. AUTHZ-01/04/05 cần manual-review hoặc custom-rule-needed; các câu khác cũng chỉ bundled-partial. Không đổi regex thành whitelist tên nghiệp vụ mới rồi coi đầy đủ.

Ví dụ repository `loadForWorkspace` dùng field `spaceKey`: đọc implementation và principal provenance dù không match ownership regex. Guard trước lookup vẫn có thể match; fixture minh họa điều đó. Khép theo paths/questions thuộc scope, không theo số matches hoặc có thêm tenant predicate.

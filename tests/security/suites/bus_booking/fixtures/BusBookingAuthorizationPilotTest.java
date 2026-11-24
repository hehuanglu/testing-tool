package com.example.busbooking.api;

import com.example.busbooking.business.port.notification.EmailVerificationSender;
import com.example.busbooking.security.JwtProperties;
import com.example.busbooking.security.JwtService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.HttpMethod;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.convention.TestBean;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.springframework.http.MediaType.APPLICATION_JSON;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.MOCK, properties = {
        "auth.rate-limit.login-limit=30", "springdoc.api-docs.enabled=false"
})
@ActiveProfiles("test")
@AutoConfigureMockMvc(printOnlyOnFailure = false,
        print = org.springframework.boot.webmvc.test.autoconfigure.MockMvcPrint.NONE)
class BusBookingAuthorizationPilotTest {
    private static final Instant NOW = Instant.parse("2026-11-01T00:00:00Z");

    @TestBean Clock clock;
    static Clock clock() { return Clock.fixed(NOW, ZoneOffset.UTC); }

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcTemplate db;
    @Autowired PasswordEncoder passwords;
    @Autowired JwtProperties jwtProperties;
    @MockitoBean EmailVerificationSender mail;

    @Test
    void recordTheAuthorizationContract() throws Exception {
        new BusBookingAuthorizationContract(db, json, passwords, jwtProperties, clock) {
            @Override
            Response call(String method, String path, Map<String, Object> body, String... headers) throws Exception {
                var request = MockMvcRequestBuilders.request(HttpMethod.valueOf(method), path);
                if (body != null) request.contentType(APPLICATION_JSON).content(json.writeValueAsBytes(body));
                if (headers.length > 0) request.header("Authorization", (Object[]) headers);
                var result = mvc.perform(request).andReturn();
                var response = result.getResponse();
                return response(response.getStatus(), response.getContentAsByteArray(), response.getContentType(),
                        "Bearer".equals(response.getHeader("WWW-Authenticate")),
                        result.getRequest().getSession(false) != null, result.getHandler() != null, path);
            }
        }.recordTheAuthorizationContract();
    }
}

abstract class BusBookingAuthorizationContract {
    private static final List<String> ACTORS = List.of("anonymous", "USER", "ADMIN", "SUPER_ADMIN", "other-USER");
    private static final List<String> TABLES = List.of("locations", "bus_operators", "routes", "vehicles",
            "trips", "bookings", "users", "roles", "email_verifications");
    private static final String PHONE = "0901234567";
    private static final String USER_ROLE = "USER";
    private final JdbcTemplate db;
    private final ObjectMapper json;
    private final PasswordEncoder passwords;
    private final JwtProperties jwtProperties;
    private final Instant now;
    private final LocalDate fixtureDate;

    BusBookingAuthorizationContract(JdbcTemplate db, ObjectMapper json, PasswordEncoder passwords,
                                    JwtProperties jwtProperties, Clock clock) {
        this.db = db;
        this.json = json;
        this.passwords = passwords;
        this.jwtProperties = jwtProperties;
        this.now = clock.instant();
        this.fixtureDate = LocalDate.ofInstant(now, ZoneId.of("Asia/Ho_Chi_Minh"));
    }

    abstract Response call(String method, String path, Map<String, Object> body, String... headers) throws Exception;

    private final Map<String, Long> ids = new LinkedHashMap<>();
    private final Map<String, String> tokens = new LinkedHashMap<>();
    private final Map<String, Map<String, Object>> identity = new LinkedHashMap<>();
    private final Map<String, List<Map<String, Object>>> groups = new LinkedHashMap<>();
    private long target;
    private final String password = "Bb1-" + UUID.randomUUID();

    record Response(int status, JsonNode body, boolean json, boolean bearer, boolean session, Boolean handlerRecorded, String path) {}
    record State(long origin, long destination, long extra, long operator, long route,
                 long vehicle, long trip, long booking) {}
    record Request(String path, Map<String, Object> body) {}

    void recordTheAuthorizationContract() throws Exception {
        seedActors();
        if (qualifyIdentities()) {
            authenticationConditions();
            var lines = Files.readAllLines(Path.of(System.getenv("BUS_PILOT_MATRIX")));
            for (String line : lines.subList(1, lines.size())) {
                var entry = line.split(" ");
                if (entry[1].equals("public")) continue;
                for (int index = 0; index < ACTORS.size(); index++) {
                    if (!entry[4 + index].equals("-")) {
                        exercise(entry, ACTORS.get(index), Integer.parseInt(entry[4 + index]));
                    }
                }
            }
            roleConditions();
        }
        var receipt = Map.of("runId", System.getenv("BUS_PILOT_RUN_ID"), "identities", identity, "groups", groups);
        Files.write(Path.of(System.getenv("BUS_PILOT_RECEIPT")), json.writeValueAsBytes(receipt));
    }

    private void seedActors() {
        String hash = passwords.encode(password);
        for (String actor : ACTORS.subList(1, ACTORS.size())) {
            ids.put(actor, insertUser(actor, roleFor(actor), hash, true));
        }
        target = insertUser("target", USER_ROLE, hash, true);
        insertUser("pending", USER_ROLE, hash, false);
    }

    private long insertUser(String alias, String role, String hash, boolean verified) {
        return insert("""
                INSERT INTO users(full_name,email,password,phone,role_id,status,email_verified)
                VALUES ('Pilot account', ?, ?, ?, (SELECT id FROM roles WHERE name = ?), 'ACTIVE', ?) RETURNING id
                """, email(alias), hash, PHONE, role, verified);
    }

    private String email(String alias) { return alias.toLowerCase(java.util.Locale.ROOT) + "@pilot.invalid"; }
    private String roleFor(String actor) { return actor.equals("other-USER") ? USER_ROLE : actor; }

    private boolean qualifyIdentities() throws Exception {
        for (var actor : ids.keySet()) {
            var login = call("POST", "/api/auth/login", Map.of("email", email(actor), "password", password));
            var token = login.body().path("token");
            boolean issued = login.status() == 200 && token.isString() && !token.asString().isBlank();
            if (issued) tokens.put(actor, token.asString());
            var me = call("GET", "/api/auth/me", null, headers(actor));
            String resolved = "unknown";
            for (var account : ids.entrySet()) {
                if (me.body().path("id").asLong(-1) == account.getValue()
                        && me.body().path("role").asString("").equals(roleFor(account.getKey()))) {
                    resolved = account.getKey();
                }
            }
            identity.put(actor, Map.of("loginStatus", login.status(), "status", me.status(),
                    "actor", resolved, "noSession", !login.session() && !me.session()));
        }
        return ids.size() == tokens.size()
                && identity.entrySet().stream().allMatch(entry ->
                    entry.getValue().get("actor").equals(entry.getKey())
                    && entry.getValue().get("status").equals(200)
                    && entry.getValue().get("noSession").equals(true));
    }

    private void authenticationConditions() throws Exception {
        var valid = headers("USER")[0];
        var expired = new JwtService(jwtProperties, Clock.fixed(now.minusSeconds(172800), ZoneOffset.UTC))
                .issue(ids.get("USER")).value();
        authCheck("missing", "anonymous", "/api/auth/me", 401);
        authCheck("malformed", "anonymous", "/api/auth/me", 401, "Bearer");
        authCheck("expired", "USER", "/api/auth/me", 401, "Bearer " + expired);
        authCheck("duplicate", "USER", "/api/auth/me", 401, valid, valid);
        authCheck("public-invalid", "anonymous", "/api/locations", 401, "Bearer invalid");
        authCheck("public-no-token", "anonymous", "/api/locations", 200);
        db.update("UPDATE users SET status = 'INACTIVE' WHERE id = ?", ids.get("USER"));
        authCheck("inactive", "USER", "/api/auth/me", 401, valid);
        db.update("UPDATE users SET status = 'ACTIVE', email_verified = false WHERE id = ?", ids.get("USER"));
        authCheck("unverified", "USER", "/api/auth/me", 401, valid);
        db.update("UPDATE users SET email_verified = true WHERE id = ?", ids.get("USER"));
        authCheck("restored", "USER", "/api/auth/me", 200, valid);
        var before = snapshot();
        var wrong = call("POST", "/api/auth/login", Map.of("email", email("USER"), "password", password + "-wrong"));
        add("BB-AUTH", "wrong-password", "USER", wrong, denied(wrong, 401) && wrong.bearer(),
                before.equals(snapshot()));
    }

    private void authCheck(String id, String actor, String path, int expected, String... headers) throws Exception {
        var before = snapshot();
        var response = call("GET", path, null, headers);
        boolean correct = expected == 401 ? denied(response, expected) && response.bearer() : response.json() &&
                (id.equals("restored") ? principal(response.body(), ids.get("USER"), USER_ROLE) : response.body().isArray());
        add("BB-AUTH", id, actor, response, correct && !response.session(), before.equals(snapshot()));
    }

    private void exercise(String[] item, String actor, int expected) throws Exception {
        String operation = item[0];
        // Every matrix cell starts with the same resource state. Actor and role are fixtures independent of the JWT.
        db.execute("TRUNCATE bookings, trips, vehicles, bus_operators, routes, locations RESTART IDENTITY");
        db.update("UPDATE users SET full_name = 'Pilot account', phone = ? WHERE id = ?", PHONE, ids.getOrDefault(actor, target));
        if (operation.equals("role-update")) {
            db.update("UPDATE users SET role_id = (SELECT id FROM roles WHERE name = 'USER') WHERE id = ?", target);
        }
        State initial = seedBusiness(operation);
        Request request = request(operation, item[3], initial);
        var before = snapshot();
        var response = call(item[2], request.path(), request.body(), headers(actor));
        boolean unchanged = before.equals(snapshot());
        if (expected >= 400) {
            add(item[1], operation, actor, response, denied(response, expected) &&
                    (expected != 401 || response.bearer()), unchanged);
        } else {
            boolean body = allowedBody(operation, actor, initial, response.body());
            boolean state = item[2].equals("GET") ? unchanged : allowedWrite(operation, actor, initial, response.body());
            add(item[1], operation, actor, response, response.json() && body, state);
        }
    }

    private State seedBusiness(String operation) {
        long origin = location("Pilot origin");
        long destination = location("Pilot destination");
        long extra = location("Pilot alternate");
        long operator = insert("""
                INSERT INTO bus_operators(name,address,phone,email,status)
                VALUES ('Pilot operator','Pilot address',?,'operator@pilot.invalid','ACTIVE') RETURNING id
                """, PHONE);
        long vehicle = insert("""
                INSERT INTO vehicles(operator_id,license_plate,vehicle_type,seat_capacity,status)
                VALUES (?,'51A12345','Sleeper',10,'ACTIVE') RETURNING id
                """, operator);
        long route = insert("""
                INSERT INTO routes(origin_id,destination_id,estimated_duration_minutes,status)
                VALUES (?,?,120,'ACTIVE') RETURNING id
                """, origin, destination);
        if (operation.equals("vehicle-update")) {
            return new State(origin, destination, extra, operator, route, vehicle, 0, 0);
        }
        boolean booked = !List.of("trip-cancel", "trip-update").contains(operation);
        long trip = insert("""
                INSERT INTO trips(route_id,vehicle_id,departure_time,arrival_time,price,available_seats,status)
                VALUES (?,?,?,?,150000,?,'SCHEDULED') RETURNING id
                """, route, vehicle, fixtureDate.plusDays(9).atTime(8, 0), fixtureDate.plusDays(9).atTime(10, 0),
                booked ? 9 : 10);
        long booking = booked ? insert("""
                INSERT INTO bookings(booking_code,user_id,trip_id,passenger_name,passenger_phone,quantity,
                    unit_price,total_amount,status,booked_at)
                VALUES ('PILOT-BOOKING',?,?,'Pilot passenger',?,1,150000,150000,'CONFIRMED',
                    ?) RETURNING id
                """, ids.get("USER"), trip, PHONE, fixtureDate.atStartOfDay()) : 0;
        return new State(origin, destination, extra, operator, route, vehicle, trip, booking);
    }

    private long location(String name) {
        return insert("INSERT INTO locations(name,province,address) VALUES (?,'Pilot Province','Pilot address') RETURNING id", name);
    }

    private Request request(String operation, String template, State seed) {
        String path = template.replace("{locationId}", Long.toString(seed.origin()))
                .replace("{operatorId}", Long.toString(seed.operator())).replace("{vehicleId}", Long.toString(seed.vehicle()))
                .replace("{routeId}", Long.toString(seed.route())).replace("{tripId}", Long.toString(seed.trip()))
                .replace("{bookingId}", Long.toString(seed.booking())).replace("{userId}", Long.toString(target));
        Map<String, Object> body = switch (operation) {
            case "profile-update" -> Map.of("fullName", "Pilot updated", "phone", "0912345678");
            case "booking-create" -> Map.of("tripId", seed.trip(), "quantity", 2,
                    "passengerName", "Pilot passenger", "passengerPhone", PHONE);
            case "location-create", "location-update" ->
                Map.of("name", "Pilot changed", "province", "Pilot Province", "address", "Changed address");
            case "operator-create", "operator-update" -> {
                var fields = new LinkedHashMap<String, Object>(Map.of("name", "Pilot changed", "address", "Changed address",
                        "phone", PHONE, "email", "changed@pilot.invalid"));
                if (operation.endsWith("update")) fields.put("status", "ACTIVE");
                yield fields;
            }
            case "vehicle-create", "vehicle-update" -> {
                var fields = new LinkedHashMap<String, Object>(Map.of("operatorId", seed.operator(),
                        "licensePlate", "51A54321", "vehicleType", "Coach", "seatCapacity", operation.endsWith("create") ? 12 : 10));
                if (operation.endsWith("update")) fields.put("status", "ACTIVE");
                yield fields;
            }
            case "route-create", "route-update" -> {
                var fields = new LinkedHashMap<String, Object>(Map.of("originId", seed.origin(),
                        "destinationId", operation.endsWith("create") ? seed.extra() : seed.destination(),
                        "estimatedDurationMinutes", 150));
                if (operation.endsWith("update")) fields.put("status", "ACTIVE");
                yield fields;
            }
            case "trip-create", "trip-update" -> {
                String date = fixtureDate.plusDays(operation.endsWith("create") ? 10 : 9).toString();
                yield Map.of("routeId", seed.route(), "vehicleId", seed.vehicle(), "price", 160000,
                        "departureTime", date + "T08:00:00", "arrivalTime", date + "T10:00:00");
            }
            case "role-update" -> Map.of("role", "ADMIN");
            default -> null;
        };
        return new Request(path, body);
    }

    private boolean allowedBody(String operation, String actor, State seed, JsonNode data) {
        return switch (operation) {
            case "auth-me", "profile-read" -> principal(data, ids.get(actor), roleFor(actor));
            case "profile-update" -> principal(data, ids.get(actor), roleFor(actor))
                    && text(data, "fullName", "Pilot updated") && text(data, "phone", "0912345678");
            case "booking-history", "bookings-read" -> contains(data.path("content"), seed.booking());
            case "booking-read" -> number(data, "id", seed.booking()) && text(data, "status", "CONFIRMED");
            case "booking-cancel" -> number(data, "id", seed.booking()) && text(data, "status", "CANCELLED");
            case "booking-create" -> data.path("id").asLong(-1) > 0 && number(data, "quantity", 2)
                    && text(data, "status", "CONFIRMED");
            case "locations-read" -> contains(data, seed.origin());
            case "operators-read" -> contains(data, seed.operator());
            case "routes-read" -> contains(data, seed.route());
            case "vehicles-read" -> contains(data, seed.vehicle());
            case "trips-read" -> contains(data.path("content"), seed.trip());
            case "location-create", "operator-create" -> data.path("id").asLong(-1) > 0 && text(data, "name", "Pilot changed");
            case "location-update" -> number(data, "id", seed.origin()) && text(data, "name", "Pilot changed");
            case "operator-update" -> number(data, "id", seed.operator()) && text(data, "name", "Pilot changed");
            case "route-create" -> data.path("id").asLong(-1) > 0 && number(data.path("destination"), "id", seed.extra())
                    && number(data, "estimatedDurationMinutes", 150);
            case "route-update" -> number(data, "id", seed.route()) && number(data, "estimatedDurationMinutes", 150);
            case "vehicle-create" -> data.path("id").asLong(-1) > 0 && text(data, "licensePlate", "51A54321");
            case "vehicle-update" -> number(data, "id", seed.vehicle()) && text(data, "licensePlate", "51A54321");
            case "trip-create" -> data.path("id").asLong(-1) > 0 && number(data, "price", 160000);
            case "trip-update" -> number(data, "id", seed.trip()) && number(data, "price", 160000);
            case "trip-cancel" -> number(data, "id", seed.trip()) && text(data, "status", "CANCELLED");
            case "role-update" -> principal(data, target, "ADMIN");
            default -> throw new IllegalArgumentException("Unknown operation");
        };
    }

    private boolean allowedWrite(String operation, String actor, State seed, JsonNode body) {
        long id = body.path("id").asLong(-1);
        return switch (operation) {
            case "profile-update" -> exists("users", "full_name = 'Pilot updated' AND phone = '0912345678'", ids.get(actor))
                    && storedRole(ids.get(actor)).equals(roleFor(actor));
            case "booking-create" -> exists("bookings", "status = 'CONFIRMED' AND quantity = 2 AND trip_id = ? AND user_id = ?",
                    id, seed.trip(), ids.get(actor)) && exists("trips", "available_seats = 7", seed.trip());
            case "booking-cancel" -> exists("bookings", "status = 'CANCELLED'", seed.booking())
                    && exists("trips", "available_seats = 10", seed.trip());
            case "location-create", "location-update" -> exists("locations", "name = 'Pilot changed' AND address = 'Changed address'", id);
            case "operator-create", "operator-update" -> exists("bus_operators", "name = 'Pilot changed' AND status = 'ACTIVE'", id);
            case "route-create", "route-update" -> exists("routes", "estimated_duration_minutes = 150 AND destination_id = ?", id,
                    operation.endsWith("create") ? seed.extra() : seed.destination());
            case "vehicle-create", "vehicle-update" -> exists("vehicles", "license_plate = '51A54321' AND vehicle_type = 'Coach' AND seat_capacity = ?", id,
                    operation.endsWith("create") ? 12 : 10);
            case "trip-create", "trip-update" -> exists("trips", "price = 160000 AND status = 'SCHEDULED'", id);
            case "trip-cancel" -> exists("trips", "status = 'CANCELLED' AND available_seats = 10", seed.trip());
            case "role-update" -> storedRole(target).equals("ADMIN") && countRoots() == 1;
            default -> throw new IllegalArgumentException("Unknown write operation");
        };
    }

    private void roleConditions() throws Exception {
        var adminHeader = headers("ADMIN");
        var rootHeader = headers("SUPER_ADMIN");
        var initial = snapshot();
        var before = call("GET", "/api/admin/locations", null, adminHeader);
        add("BB-ROLE-LIFECYCLE", "before-demotion", "ADMIN", before, before.json() && before.body().isArray(),
                initial.equals(snapshot()));
        var demote = call("PUT", rolePath(ids.get("ADMIN")), Map.of("role", USER_ROLE), rootHeader);
        add("BB-ROLE-LIFECYCLE", "demote", "SUPER_ADMIN", demote,
                principal(demote.body(), ids.get("ADMIN"), USER_ROLE), storedRole(ids.get("ADMIN")).equals(USER_ROLE));
        var demoted = snapshot();
        var blocked = call("GET", "/api/admin/locations", null, adminHeader);
        add("BB-ROLE-LIFECYCLE", "old-token-denied", "ADMIN", blocked, denied(blocked, 403), demoted.equals(snapshot()));
        var me = call("GET", "/api/auth/me", null, adminHeader);
        add("BB-ROLE-LIFECYCLE", "old-token-current-role", "ADMIN", me,
                principal(me.body(), ids.get("ADMIN"), USER_ROLE), demoted.equals(snapshot()));

        var promote = call("PUT", rolePath(ids.get("ADMIN")), Map.of("role", "ADMIN"), rootHeader);
        add("BB-ROLE-LIFECYCLE", "restore-admin", "SUPER_ADMIN", promote,
                principal(promote.body(), ids.get("ADMIN"), "ADMIN"), storedRole(ids.get("ADMIN")).equals("ADMIN"));
        roleRule("root-immutable", ids.get("SUPER_ADMIN"), USER_ROLE, 403, "FORBIDDEN");
        roleRule("root-not-assignable", target, "SUPER_ADMIN", 400, "INVALID_REQUEST");
        long pending = db.queryForObject("SELECT id FROM users WHERE email = ?", Long.class, email("pending"));
        roleRule("pending-not-promotable", pending, "ADMIN", 409, "ACCOUNT_NOT_ELIGIBLE");
    }

    private void roleRule(String condition, long subject, String role, int code, String error) throws Exception {
        var before = snapshot();
        var response = call("PUT", rolePath(subject), Map.of("role", role), headers("SUPER_ADMIN"));
        add("BB-ROLE-RULES", condition, "SUPER_ADMIN", response, error(response, code, error),
                before.equals(snapshot()) && countRoots() == 1);
    }

    private String rolePath(long id) { return "/api/admin/users/" + id + "/role"; }
    private int countRoots() {
        return db.queryForObject("SELECT count(*) FROM users JOIN roles ON role_id=roles.id WHERE roles.name='SUPER_ADMIN'", Integer.class);
    }

    private String storedRole(long id) {
        return db.queryForObject("SELECT roles.name FROM users JOIN roles ON role_id=roles.id WHERE users.id=?", String.class, id);
    }

    private Map<String, String> snapshot() {
        var rows = new LinkedHashMap<String, String>();
        for (String table : TABLES) {
            rows.put(table, db.queryForObject("SELECT jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t))::text FROM " + table + " t", String.class));
        }
        return rows;
    }

    private boolean exists(String table, String predicate, Object... parameters) {
        return Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS (SELECT 1 FROM " + table
                + " WHERE id = ? AND " + predicate + ")", Boolean.class, parameters));
    }

    private long insert(String sql, Object... parameters) { return db.queryForObject(sql, Long.class, parameters); }

    private String[] headers(String actor) {
        return tokens.containsKey(actor) ? new String[]{"Bearer " + tokens.get(actor)} : new String[]{};
    }

    Response response(int status, byte[] bytes, String contentType, boolean bearer, boolean session,
                      Boolean handlerRecorded, String path) {
        boolean isJson = contentType != null && contentType.startsWith("application/json") && bytes.length > 0;
        JsonNode parsed;
        try {
            parsed = isJson ? json.readTree(bytes) : json.createObjectNode();
        } catch (tools.jackson.core.JacksonException invalidResponse) {
            parsed = json.createObjectNode();
            isJson = false;
        }
        return new Response(status, parsed, isJson, bearer, session, handlerRecorded, path);
    }

    private void add(String group, String operation, String actor, Response response, boolean body, boolean dbState) {
        var row = new LinkedHashMap<String, Object>(Map.of("operation", operation, "actor", actor,
                "status", response.status(), "responseMatches", body, "stateMatches", dbState));
        if (response.handlerRecorded() != null) row.put("handlerRecorded", response.handlerRecorded());
        groups.computeIfAbsent(group, key -> new ArrayList<>()).add(row);
    }

    private boolean denied(Response response, int code) {
        return error(response, code, code == 401 ? "UNAUTHORIZED" : "FORBIDDEN");
    }

    private boolean error(Response response, int code, String error) {
        var body = response.body();
        return response.json() && number(body, "status", code) && text(body, "error", error)
                && text(body, "path", response.path()) && !body.has("token") && !body.has("id")
                && !body.has("email") && !body.has("password") && !body.has("passwordHash")
                && !body.has("role") && !body.has("content") && !body.has("bookingCode");
    }

    private boolean principal(JsonNode body, long id, String role) {
        return number(body, "id", id) && text(body, "role", role) && !body.has("token") && !body.has("passwordHash");
    }

    private boolean text(JsonNode node, String field, String value) { return node.path(field).asString("").equals(value); }
    private boolean number(JsonNode node, String field, long value) {
        var observed = node.path(field);
        return observed.isNumber() && observed.asDecimal().compareTo(java.math.BigDecimal.valueOf(value)) == 0;
    }

    private boolean contains(JsonNode array, long id) {
        if (!array.isArray()) return false;
        for (var row : array) {
            if (number(row, "id", id)) return true;
        }
        return false;
    }
}

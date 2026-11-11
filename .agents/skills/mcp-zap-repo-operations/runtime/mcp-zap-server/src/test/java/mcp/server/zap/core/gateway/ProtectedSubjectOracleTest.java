package mcp.server.zap.core.gateway;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class ProtectedSubjectOracleTest {
    private final String json = "HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\n";
    @Test void matchesProtectedSubjectOnly() {
        assertTrue(ZapEngineContextAccess.protectedSubjectMatches(json, "{\"data\":{\"user_id\":42}}", "/data/user_id", "42"));
        assertFalse(ZapEngineContextAccess.protectedSubjectMatches(json, "{\"data\":{\"user_id\":43}}", "/data/user_id", "42"));
        assertFalse(ZapEngineContextAccess.protectedSubjectMatches(json, "{\"data\":{\"accounts\":[]}}", "/data/user_id", "42"));
        assertFalse(ZapEngineContextAccess.protectedSubjectMatches(json.replace("application/json", "text/html"), "<html>42</html>", "/data/user_id", "42"));
        assertFalse(ZapEngineContextAccess.protectedSubjectMatches(json, "<html>42</html>", "/data/user_id", "42"));
        assertFalse(ZapEngineContextAccess.protectedSubjectMatches(json.replace("200 OK", "401 Unauthorized"), "{\"data\":{\"user_id\":42}}", "/data/user_id", "42"));
    }

    @Test void acceptsStatusLineWithoutReasonPhrase() {
        String headers = "HTTP/1.1 200\r\nContent-Type: application/json\r\n\r\n";
        String body = "{\"id\":null,\"userId\":11,\"items\":[]}";
        assertTrue(ZapEngineContextAccess.protectedSubjectMatches(headers, body, "/userId", "11"));
        assertFalse(ZapEngineContextAccess.protectedSubjectMatches(headers, body, "/userId", "12"));
        assertFalse(ZapEngineContextAccess.protectedSubjectMatches(headers.replace("200", "401"), body, "/userId", "11"));
        assertFalse(ZapEngineContextAccess.protectedSubjectMatches(headers.replace("200", "2000"), body, "/userId", "11"));
        assertFalse(ZapEngineContextAccess.protectedSubjectMatches(headers.replace("application/json", "text/html"), body, "/userId", "11"));
    }
}

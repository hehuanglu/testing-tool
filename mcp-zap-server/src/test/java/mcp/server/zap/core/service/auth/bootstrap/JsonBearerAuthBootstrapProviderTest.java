package mcp.server.zap.core.service.auth.bootstrap;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import mcp.server.zap.core.service.ContextUserService;
import mcp.server.zap.core.service.UrlValidationService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class JsonBearerAuthBootstrapProviderTest {

    @TempDir
    Path tempDir;

    @Test
    void preparesNativeJsonAuthenticationWithoutStoringPasswordOrToken() throws Exception {
        ContextUserService contexts = mock(ContextUserService.class);
        when(contexts.upsertContext(any(), any(), any(), eq(true))).thenReturn(Map.of("contextId", "1"));
        when(contexts.upsertUser(eq("1"), eq("zap-user"), any(), eq(true)))
                .thenReturn(Map.of("userId", "7"));
        JsonBearerAuthBootstrapProvider provider = provider(contexts);

        AuthSessionPrepareResult prepared = provider.prepare(request("correct-password"));

        assertThat(prepared.session().authKind()).isEqualTo(AuthBootstrapKind.JSON_BEARER);
        assertThat(prepared.session().toString()).doesNotContain("correct-password", "eyJhbGci");
        verify(contexts).configureContextAuthentication(
                eq("1"), eq("jsonBasedAuthentication"), any(), eq("authenticated=true"), eq("status=401"));
        verify(contexts).configureSessionManagement(
                eq("1"), eq("headerBasedSessionManagement"),
                eq("headers=Authorization%3ABearer+%7B%25json%3Adata.accessToken%25%7D"));
    }

    @Test
    void validationRequiresPositiveProtectedResponseAndRedactsTokenLikeDiagnostics() throws Exception {
        ContextUserService contexts = mock(ContextUserService.class);
        when(contexts.upsertContext(any(), any(), any(), eq(true))).thenReturn(Map.of("contextId", "1"));
        when(contexts.upsertUser(eq("1"), eq("zap-user"), any(), eq(true)))
                .thenReturn(Map.of("userId", "7"));
        JsonBearerAuthBootstrapProvider provider = provider(contexts);
        PreparedAuthSession session = provider.prepare(request("wrong-password")).session();
        when(contexts.testUserAuthentication("1", "7", "https://api.example.test/api/v1/accounts"))
                .thenReturn(Map.of(
                        "likelyAuthenticated", false,
                        "authResponse", "synthetic-token eyJhbGciOiJIUzI1NiJ9.secret.signature",
                        "authState", "401"
                ));

        AuthSessionValidationResult result = provider.validate(session);

        assertThat(result.valid()).isFalse();
        assertThat(result.outcome()).isEqualTo("authentication_failed");
        assertThat(result.diagnostics().toString())
                .contains("Header replay verified: false")
                .doesNotContain("eyJhbGci", "wrong-password");
    }

    @Test
    void validationAcceptsOnlyPositiveHeaderReplayEvidence() throws Exception {
        ContextUserService contexts = mock(ContextUserService.class);
        when(contexts.upsertContext(any(), any(), any(), eq(true))).thenReturn(Map.of("contextId", "1"));
        when(contexts.upsertUser(eq("1"), eq("zap-user"), any(), eq(true)))
                .thenReturn(Map.of("userId", "7"));
        JsonBearerAuthBootstrapProvider provider = provider(contexts);
        PreparedAuthSession session = provider.prepare(request("correct-password")).session();
        when(contexts.testUserAuthentication("1", "7", "https://api.example.test/api/v1/accounts"))
                .thenReturn(Map.of("likelyAuthenticated", true));

        AuthSessionValidationResult result = provider.validate(session);

        assertThat(result.valid()).isTrue();
        assertThat(result.outcome()).isEqualTo("authenticated");
        assertThat(result.diagnostics()).contains("Header replay verified: true");
    }

    @Test
    void subjectValidationBootstrapsOnceAndThenChecksContinuityWithoutExplicitRelogin() throws Exception {
        ContextUserService contexts = mock(ContextUserService.class);
        JsonBearerAuthBootstrapProvider provider = provider(contexts);
        PreparedAuthSession session = new PreparedAuthSession("subject-session", "research", AuthBootstrapKind.JSON_BEARER,
                provider.providerId(), new mcp.server.zap.core.gateway.TargetDescriptor(
                    mcp.server.zap.core.gateway.TargetDescriptor.Kind.WEB, "https://api.example.test/api/v1/accounts", "research"),
                HttpOrigin.fromConfiguredOrigin("https://api.example.test"), "file:/unused", "research", "1", "zap-user", "7",
                "Authorization", "https://api.example.test/api/auth/login", "https://api.example.test/api/v1/accounts", true,
                "/data/user_id", "42");
        when(contexts.verifyUserIdentity("1", "7", session.verificationUrl(), "/data/user_id", "42", true))
                .thenReturn(Map.of("likelyAuthenticated", true));
        when(contexts.verifyUserIdentity("1", "7", session.verificationUrl(), "/data/user_id", "42", false))
                .thenReturn(Map.of("likelyAuthenticated", false));
        assertThat(provider.validate(session).valid()).isTrue();
        assertThat(provider.validate(session).valid()).isFalse();
        verify(contexts).verifyUserIdentity("1", "7", session.verificationUrl(), "/data/user_id", "42", false);
    }

    private JsonBearerAuthBootstrapProvider provider(ContextUserService contexts) {
        return new JsonBearerAuthBootstrapProvider(
                contexts, new CredentialReferenceResolver(), mock(UrlValidationService.class));
    }

    private AuthBootstrapRequest request(String password) throws Exception {
        Path passwordFile = Files.writeString(tempDir.resolve("password-" + password.hashCode()), password);
        return new AuthBootstrapRequest(
                "json-api",
                "https://api.example.test/api/v1/accounts",
                AuthBootstrapKind.JSON_BEARER,
                HttpOrigin.fromConfiguredOrigin("https://api.example.test"),
                "file:" + passwordFile,
                "https://api.example.test/api/auth/login",
                "scan@example.test",
                "zap-user",
                null,
                null,
                "email",
                "password",
                "/data/accessToken",
                "Authorization",
                "Bearer ",
                "https://api.example.test/api/v1/accounts",
                "authenticated=true",
                "status=401"
        );
    }
}

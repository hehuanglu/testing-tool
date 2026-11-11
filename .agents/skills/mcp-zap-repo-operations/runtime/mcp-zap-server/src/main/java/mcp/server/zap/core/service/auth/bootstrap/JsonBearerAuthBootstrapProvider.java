package mcp.server.zap.core.service.auth.bootstrap;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Pattern;
import mcp.server.zap.core.gateway.TargetDescriptor;
import mcp.server.zap.core.service.ContextUserService;
import mcp.server.zap.core.service.UrlValidationService;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/**
 * Experimental native ZAP JSON-login provider.
 *
 * <p>Default-disabled because native authentication-verification history can retain the raw
 * session header after HTTP Sender scripts run. See the feasibility-spike documentation before
 * enabling it in an isolated environment.</p>
 */
@Component
@ConditionalOnProperty(
        prefix = "zap.auth",
        name = "experimental-json-bearer-enabled",
        havingValue = "true")
public class JsonBearerAuthBootstrapProvider implements AuthBootstrapProvider {
    private static final String CONTEXT_NAME_SUFFIX = "-auth";
    private static final String DEFAULT_USER_NAME = "zap-scan-user";

    private final java.util.Set<String> bootstrapped = java.util.concurrent.ConcurrentHashMap.newKeySet();
    private final ContextUserService contextUserService;
    private final CredentialReferenceResolver credentialReferenceResolver;
    private final UrlValidationService urlValidationService;

    public JsonBearerAuthBootstrapProvider(ContextUserService contextUserService,
                                           CredentialReferenceResolver credentialReferenceResolver,
                                           UrlValidationService urlValidationService) {
        this.contextUserService = contextUserService;
        this.credentialReferenceResolver = credentialReferenceResolver;
        this.urlValidationService = urlValidationService;
    }

    @Override
    public String providerId() {
        return "zap-json-bearer";
    }

    @Override
    public boolean supports(AuthBootstrapRequest request) {
        return request.authKind() == AuthBootstrapKind.JSON_BEARER;
    }

    @Override
    public AuthSessionPrepareResult prepare(AuthBootstrapRequest request) {
        requireJsonBearer(request);
        validateUrl(request.allowedOrigin(), request.targetUrl(), "targetUrl");
        validateUrl(request.allowedOrigin(), request.loginUrl(), "loginUrl");
        validateUrl(request.allowedOrigin(), request.verificationUrl(), "verificationUrl");

        String password = credentialReferenceResolver.resolveSecret(request.credentialReference());
        String contextName = request.profileId() + CONTEXT_NAME_SUFFIX;
        String zapUserName = hasText(request.zapUserName()) ? request.zapUserName().trim() : DEFAULT_USER_NAME;
        Map<String, Object> context = contextUserService.upsertContext(
                contextName,
                List.of(buildScopeRegex(request.allowedOrigin())),
                List.of(buildLogoutRegex(request.allowedOrigin())),
                true
        );
        String contextId = stringValue(context.get("contextId"));

        String loginRequestData = "{\"" + request.usernameJsonField() + "\":\"{%username%}\",\""
                + request.passwordJsonField() + "\":\"{%password%}\"}";
        String authConfig = configParam("loginUrl", request.loginUrl())
                + "&" + configParam("loginRequestData", loginRequestData);
        contextUserService.configureContextAuthentication(
                contextId,
                "jsonBasedAuthentication",
                authConfig,
                request.loggedInIndicatorRegex(),
                request.loggedOutIndicatorRegex()
        );

        String jsonPath = request.tokenJsonPointer().substring(1).replace('/', '.');
        String headerTemplate = request.headerName() + ":" + request.headerPrefix()
                + "{%json:" + jsonPath + "%}";
        contextUserService.configureSessionManagement(
                contextId,
                "headerBasedSessionManagement",
                configParam("headers", headerTemplate)
        );

        String credentials = configParam("username", request.username())
                + "&" + configParam("password", password);
        Map<String, Object> user = contextUserService.upsertUser(contextId, zapUserName, credentials, true);
        String userId = stringValue(user.get("userId"));

        PreparedAuthSession session = new PreparedAuthSession(
                UUID.randomUUID().toString(),
                request.profileId(),
                AuthBootstrapKind.JSON_BEARER,
                providerId(),
                new TargetDescriptor(TargetDescriptor.Kind.WEB, request.targetUrl(), contextName),
                request.allowedOrigin(),
                request.credentialReference(),
                contextName,
                contextId,
                zapUserName,
                userId,
                request.headerName(),
                request.loginUrl(),
                request.verificationUrl(),
                true,
                request.subjectJsonPointer(),
                request.expectedSubject(),
                request.signedJwtIdentity()
        );
        return new AuthSessionPrepareResult(
                session,
                List.of("Validate this session before use. JSON bearer sessions support guided HTTP crawl and guided active-scan preparation; queued execution is rejected fail-closed.")
        );
    }

    @Override
    public AuthSessionValidationResult validate(PreparedAuthSession session) {
        requireSessionOrigin(session);
        Map<String, Object> result = session.signedJwtIdentity() != null
                ? contextUserService.verifySignedJwtIdentity(session.contextId(), session.userId(), session.verificationUrl(),
                        session.signedJwtIdentity(), session.expectedSubject(), bootstrapped.add(session.sessionId()))
                : session.subjectJsonPointer() == null
                ? contextUserService.testUserAuthentication(session.contextId(), session.userId(), session.verificationUrl())
                : contextUserService.verifyUserIdentity(session.contextId(), session.userId(), session.verificationUrl(),
                        session.subjectJsonPointer(), session.expectedSubject(), bootstrapped.add(session.sessionId()));
        boolean valid = Boolean.TRUE.equals(result.get("likelyAuthenticated"));
        return new AuthSessionValidationResult(
                session,
                valid,
                valid ? "authenticated" : "authentication_failed",
                List.of(
                        "likelyAuthenticated=" + result.get("likelyAuthenticated"),
                        "Header replay verified: " + valid,
                        valid
                                ? "Protected verification returned positive authenticated evidence through the ZAP context/user."
                                : "Protected verification did not prove authenticated header replay; the session remains unusable."
                )
        );
    }

    private void requireJsonBearer(AuthBootstrapRequest request) {
        if (request.authKind() != AuthBootstrapKind.JSON_BEARER) {
            throw new IllegalArgumentException("json-bearer provider received a different auth kind");
        }
        if (request.signedJwtIdentity() != null && (request.subjectJsonPointer() != null
                || !hasText(request.expectedSubject()) || !"Authorization".equals(request.headerName())
                || !"Bearer ".equals(request.headerPrefix()))) {
            throw new IllegalArgumentException("Signed JWT identity requires one exclusive bound subject strategy");
        }
        requireText(request.profileId(), "profileId");
        requireText(request.targetUrl(), "targetUrl");
        requireText(request.loginUrl(), "loginUrl");
        requireText(request.verificationUrl(), "verificationUrl");
        requireText(request.username(), "username");
        requireText(request.usernameJsonField(), "usernameJsonField");
        requireText(request.passwordJsonField(), "passwordJsonField");
        requireText(request.tokenJsonPointer(), "tokenJsonPointer");
        requireText(request.headerName(), "headerName");
        requireText(request.headerPrefix(), "headerPrefix");
        requireText(request.loggedInIndicatorRegex(), "loggedInIndicatorRegex");
        requireText(request.loggedOutIndicatorRegex(), "loggedOutIndicatorRegex");
    }

    private void validateUrl(HttpOrigin origin, String url, String label) {
        if (origin == null) {
            throw new IllegalArgumentException("Auth profile allowedOrigin cannot be null");
        }
        urlValidationService.validateUrl(url);
        origin.requireMatch(url, label);
    }

    private void requireSessionOrigin(PreparedAuthSession session) {
        if (session.authorizedOrigin() == null) {
            throw new IllegalArgumentException("Prepared auth session has no authorized profile origin");
        }
        session.authorizedOrigin().requireMatch(session.target().baseUrl(), "auth session target");
        session.authorizedOrigin().requireMatch(session.loginUrl(), "auth session loginUrl");
        session.authorizedOrigin().requireMatch(session.verificationUrl(), "auth session verificationUrl");
    }

    private String buildScopeRegex(HttpOrigin origin) {
        return buildOriginRegexPrefix(origin) + "(?:[/?#].*)?\\z";
    }

    private String buildLogoutRegex(HttpOrigin origin) {
        return buildOriginRegexPrefix(origin) + Pattern.quote("/logout") + "(?:[/?#].*)?\\z";
    }

    private String buildOriginRegexPrefix(HttpOrigin origin) {
        String host = origin.host().contains(":") ? "[" + origin.host() + "]" : origin.host();
        int defaultPort = "https".equals(origin.scheme()) ? 443 : 80;
        String portRegex = origin.port() == defaultPort ? "(?::0*" + defaultPort + ")?" : ":0*" + origin.port();
        return "\\A(?i:" + Pattern.quote(origin.scheme() + "://" + host) + ")" + portRegex;
    }

    private String configParam(String key, String value) {
        return urlEncode(key) + "=" + urlEncode(value);
    }

    private String urlEncode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    private String stringValue(Object value) {
        return value == null ? null : value.toString();
    }

    private String requireText(String value, String fieldName) {
        if (!hasText(value)) {
            throw new IllegalArgumentException(fieldName + " cannot be null or blank");
        }
        return value;
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}

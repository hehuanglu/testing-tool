package mcp.server.zap.core.service.auth.bootstrap;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import java.util.regex.PatternSyntaxException;
import mcp.server.zap.core.configuration.AuthBootstrapProperties;
import mcp.server.zap.core.service.UrlValidationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * Resolves immutable operator-managed authentication profiles for MCP callers.
 */
@Component
public class AuthProfileResolver {
    private static final int MAX_INDICATOR_REGEX_LENGTH = 512;
    private static final Pattern PROFILE_ID = Pattern.compile("[A-Za-z0-9._-]{1,64}");
    private static final Pattern JSON_FIELD_NAME = Pattern.compile("[A-Za-z_][A-Za-z0-9_.-]{0,127}");
    private static final Pattern HEADER_NAME = Pattern.compile("[!#$%&'*+.^_`|~0-9A-Za-z-]{1,128}");
    private static final Pattern SAFE_POINTER_SEGMENT = Pattern.compile("[A-Za-z_][A-Za-z0-9_-]{0,127}");

    private final Map<String, ConfiguredAuthProfile> profiles;
    private final UrlValidationService urlValidationService;

    public AuthProfileResolver(AuthBootstrapProperties properties) {
        this(properties, null);
    }

    @Autowired
    public AuthProfileResolver(AuthBootstrapProperties properties, UrlValidationService urlValidationService) {
        this.urlValidationService = urlValidationService;
        this.profiles = compileProfiles(properties == null ? List.of() : properties.getProfiles());
    }

    public AuthBootstrapRequest resolve(String profileId, String targetUrl) {
        String normalizedProfileId = requireProfileId(profileId);
        ConfiguredAuthProfile profile = profiles.get(normalizedProfileId);
        if (profile == null) {
            throw new IllegalArgumentException("Unknown auth profile ID: " + normalizedProfileId);
        }
        return profile.requestFor(requireText(targetUrl, "targetUrl"));
    }

    private Map<String, ConfiguredAuthProfile> compileProfiles(List<AuthBootstrapProperties.Profile> configuredProfiles) {
        Map<String, ConfiguredAuthProfile> compiled = new LinkedHashMap<>();
        if (configuredProfiles == null) {
            return Map.of();
        }
        for (AuthBootstrapProperties.Profile configured : configuredProfiles) {
            if (configured == null) {
                throw new IllegalArgumentException("Auth profile configuration cannot contain null entries");
            }
            ConfiguredAuthProfile profile = compileProfile(configured);
            if (compiled.putIfAbsent(profile.id(), profile) != null) {
                throw new IllegalArgumentException("Duplicate auth profile ID: " + profile.id());
            }
        }
        return Map.copyOf(compiled);
    }

    private ConfiguredAuthProfile compileProfile(AuthBootstrapProperties.Profile configured) {
        String id = requireProfileId(configured.getId());
        AuthBootstrapKind authKind;
        try {
            authKind = AuthBootstrapKind.fromWireValue(configured.getKind());
        } catch (IllegalArgumentException e) {
            throw invalidProfile(id, e.getMessage(), e);
        }
        HttpOrigin allowedOrigin;
        try {
            allowedOrigin = HttpOrigin.fromConfiguredOrigin(configured.getAllowedOrigin());
        } catch (IllegalArgumentException e) {
            throw invalidProfile(id, e.getMessage(), e);
        }

        String credentialReference = requireProfileText(id, configured.getCredentialReference(), "credentialReference");
        try {
            CredentialReferenceResolver.validateReference(credentialReference);
        } catch (IllegalArgumentException e) {
            throw invalidProfile(id, e.getMessage(), e);
        }
        String loginUrl = trimToNull(configured.getLoginUrl());
        String verificationUrl = trimToNull(configured.getVerificationUrl());
        String username = trimToNull(configured.getUsername());
        String loggedInIndicatorRegex = validateIndicatorRegex(
                id,
                configured.getLoggedInIndicatorRegex(),
                "loggedInIndicatorRegex"
        );
        String loggedOutIndicatorRegex = validateIndicatorRegex(
                id,
                configured.getLoggedOutIndicatorRegex(),
                "loggedOutIndicatorRegex"
        );
        if (authKind == AuthBootstrapKind.FORM || authKind == AuthBootstrapKind.BROWSER) {
            loginUrl = requireProfileText(id, loginUrl, "loginUrl");
            username = requireProfileText(id, username, "username");
            loggedInIndicatorRegex = requireProfileText(id, loggedInIndicatorRegex, "loggedInIndicatorRegex");
            try {
                allowedOrigin.requireMatch(loginUrl, "loginUrl");
            } catch (IllegalArgumentException e) {
                throw invalidProfile(id, e.getMessage(), e);
            }
        }
        String usernameJsonField = trimToNull(configured.getUsernameJsonField());
        String passwordJsonField = trimToNull(configured.getPasswordJsonField());
        String tokenJsonPointer = trimToNull(configured.getTokenJsonPointer());
        String headerName = trimToNull(configured.getHeaderName());
        String headerPrefix = configured.getHeaderPrefix();
        if (authKind == AuthBootstrapKind.JSON_BEARER) {
            loginUrl = requireProfileText(id, loginUrl, "loginUrl");
            verificationUrl = requireProfileText(id, verificationUrl, "verificationUrl");
            username = requireProfileText(id, username, "username");
            usernameJsonField = requireProfileText(id, usernameJsonField, "usernameJsonField");
            passwordJsonField = requireProfileText(id, passwordJsonField, "passwordJsonField");
            tokenJsonPointer = requireProfileText(id, tokenJsonPointer, "tokenJsonPointer");
            headerName = requireProfileText(id, headerName, "headerName");
            if (headerPrefix == null || headerPrefix.isBlank()) {
                throw invalidProfile(id, "headerPrefix cannot be null or blank");
            }
            loggedInIndicatorRegex = requireProfileText(id, loggedInIndicatorRegex, "loggedInIndicatorRegex");
            loggedOutIndicatorRegex = requireProfileText(id, loggedOutIndicatorRegex, "loggedOutIndicatorRegex");
            validateJsonField(id, usernameJsonField, "usernameJsonField");
            validateJsonField(id, passwordJsonField, "passwordJsonField");
            validateJsonPointer(id, tokenJsonPointer);
            validateHeader(id, headerName, headerPrefix);
            try {
                allowedOrigin.requireMatch(loginUrl, "loginUrl");
                allowedOrigin.requireMatch(verificationUrl, "verificationUrl");
                validateUrlPolicy(loginUrl);
                validateUrlPolicy(verificationUrl);
            } catch (IllegalArgumentException e) {
                throw invalidProfile(id, e.getMessage(), e);
            }
        }
        if (authKind == AuthBootstrapKind.BROWSER
                && (trimToNull(configured.getUsernameField()) != null || trimToNull(configured.getPasswordField()) != null)) {
            throw invalidProfile(id, "usernameField and passwordField are only supported by form auth profiles; browser authentication discovers login fields");
        }

        if (configured.getSignedJwtIdentity() != null) {
            if (authKind != AuthBootstrapKind.JSON_BEARER || trimToNull(configured.getSubjectJsonPointer()) != null
                    || trimToNull(configured.getExpectedSubject()) == null
                    || !"Authorization".equals(headerName) || !"Bearer ".equals(headerPrefix)) {
                throw invalidProfile(id, "signedJwtIdentity requires json-bearer, expectedSubject and exclusive identity strategy");
            }
        } else if ((trimToNull(configured.getSubjectJsonPointer()) == null)
                != (trimToNull(configured.getExpectedSubject()) == null)) {
            throw invalidProfile(id, "subjectJsonPointer and expectedSubject must be configured together");
        }
        if (configured.getSubjectJsonPointer() != null) {
            validateJsonPointer(id, configured.getSubjectJsonPointer());
        }

        return new ConfiguredAuthProfile(
                id,
                authKind,
                allowedOrigin,
                credentialReference,
                loginUrl,
                username,
                trimToNull(configured.getZapUserName()),
                trimToNull(configured.getUsernameField()),
                trimToNull(configured.getPasswordField()),
                usernameJsonField,
                passwordJsonField,
                tokenJsonPointer,
                headerName,
                headerPrefix,
                verificationUrl,
                loggedInIndicatorRegex,
                loggedOutIndicatorRegex,
                trimToNull(configured.getSubjectJsonPointer()),
                trimToNull(configured.getExpectedSubject()),
                configured.getSignedJwtIdentity()
        );
    }

    private void validateJsonField(String profileId, String value, String fieldName) {
        if (!JSON_FIELD_NAME.matcher(value).matches()) {
            throw invalidProfile(profileId, fieldName + " contains unsupported characters");
        }
    }

    private void validateJsonPointer(String profileId, String pointer) {
        if (pointer.length() > 512 || !pointer.startsWith("/") || pointer.equals("/")) {
            throw invalidProfile(profileId, "tokenJsonPointer must be a non-root JSON Pointer of at most 512 characters");
        }
        for (String segment : pointer.substring(1).split("/", -1)) {
            if (!SAFE_POINTER_SEGMENT.matcher(segment).matches()) {
                throw invalidProfile(profileId, "tokenJsonPointer contains an unsafe or malformed segment");
            }
        }
    }

    private void validateHeader(String profileId, String headerName, String headerPrefix) {
        if (!HEADER_NAME.matcher(headerName).matches()) {
            throw invalidProfile(profileId, "headerName must be a valid HTTP field name");
        }
        if (headerPrefix.length() > 64 || headerPrefix.chars().anyMatch(ch -> ch < 0x20 || ch == 0x7f)) {
            throw invalidProfile(profileId, "headerPrefix must contain only visible characters and spaces and be at most 64 characters");
        }
    }

    private void validateUrlPolicy(String url) {
        if (urlValidationService != null) {
            urlValidationService.validateUrl(url);
        }
    }

    private String validateIndicatorRegex(String profileId, String value, String fieldName) {
        String regex = trimToNull(value);
        if (regex == null) {
            return null;
        }
        if (regex.length() > MAX_INDICATOR_REGEX_LENGTH) {
            throw invalidProfile(
                    profileId,
                    fieldName + " cannot exceed " + MAX_INDICATOR_REGEX_LENGTH + " characters"
            );
        }
        try {
            Pattern.compile(regex);
        } catch (PatternSyntaxException e) {
            throw invalidProfile(profileId, fieldName + " must be a valid regular expression", e);
        }
        return regex;
    }

    private String requireProfileId(String value) {
        String id = requireText(value, "profileId");
        if (!PROFILE_ID.matcher(id).matches()) {
            throw new IllegalArgumentException("profileId must use 1-64 letters, numbers, dots, underscores, or dashes");
        }
        return id;
    }

    private String requireProfileText(String profileId, String value, String fieldName) {
        try {
            return requireText(value, fieldName);
        } catch (IllegalArgumentException e) {
            throw invalidProfile(profileId, e.getMessage(), e);
        }
    }

    private IllegalArgumentException invalidProfile(String profileId, String message, Exception cause) {
        return new IllegalArgumentException("Auth profile '" + profileId + "' is invalid: " + message, cause);
    }

    private IllegalArgumentException invalidProfile(String profileId, String message) {
        return new IllegalArgumentException("Auth profile '" + profileId + "' is invalid: " + message);
    }

    private String requireText(String value, String fieldName) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(fieldName + " cannot be null or blank");
        }
        return value.trim();
    }

    private String trimToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private record ConfiguredAuthProfile(
            String id,
            AuthBootstrapKind authKind,
            HttpOrigin allowedOrigin,
            String credentialReference,
            String loginUrl,
            String username,
            String zapUserName,
            String usernameField,
            String passwordField,
            String usernameJsonField,
            String passwordJsonField,
            String tokenJsonPointer,
            String headerName,
            String headerPrefix,
            String verificationUrl,
            String loggedInIndicatorRegex,
            String loggedOutIndicatorRegex,
            String subjectJsonPointer,
            String expectedSubject,
            mcp.server.zap.core.gateway.SignedJwtIdentity signedJwtIdentity
    ) {
        private AuthBootstrapRequest requestFor(String targetUrl) {
            return new AuthBootstrapRequest(
                    id,
                    targetUrl,
                    authKind,
                    allowedOrigin,
                    credentialReference,
                    loginUrl,
                    username,
                    zapUserName,
                    usernameField,
                    passwordField,
                    usernameJsonField,
                    passwordJsonField,
                    tokenJsonPointer,
                    headerName,
                    headerPrefix,
                    verificationUrl,
                    loggedInIndicatorRegex,
                    loggedOutIndicatorRegex,
                    subjectJsonPointer,
                    expectedSubject,
                    signedJwtIdentity
            );
        }
    }
}

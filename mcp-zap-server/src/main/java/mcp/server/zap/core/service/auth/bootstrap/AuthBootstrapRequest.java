package mcp.server.zap.core.service.auth.bootstrap;

/**
 * Gateway request model for guided auth bootstrap preparation.
 */
public record AuthBootstrapRequest(
        String profileId,
        String targetUrl,
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
    public AuthBootstrapRequest(String profileId, String targetUrl, AuthBootstrapKind authKind, HttpOrigin allowedOrigin,
            String credentialReference, String loginUrl, String username, String zapUserName, String usernameField,
            String passwordField, String usernameJsonField, String passwordJsonField, String tokenJsonPointer,
            String headerName, String headerPrefix, String verificationUrl, String loggedInIndicatorRegex,
            String loggedOutIndicatorRegex, String subjectJsonPointer, String expectedSubject) {
        this(profileId, targetUrl, authKind, allowedOrigin, credentialReference, loginUrl, username, zapUserName,
                usernameField, passwordField, usernameJsonField, passwordJsonField, tokenJsonPointer, headerName,
                headerPrefix, verificationUrl, loggedInIndicatorRegex, loggedOutIndicatorRegex, subjectJsonPointer,
                expectedSubject, null);
    }
    public AuthBootstrapRequest(
        String profileId,
        String targetUrl,
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
        String loggedOutIndicatorRegex
    ) {
        this(profileId, targetUrl, authKind, allowedOrigin, credentialReference, loginUrl, username, zapUserName, usernameField, passwordField, usernameJsonField, passwordJsonField, tokenJsonPointer, headerName, headerPrefix, verificationUrl, loggedInIndicatorRegex, loggedOutIndicatorRegex, null, null);
    }
}

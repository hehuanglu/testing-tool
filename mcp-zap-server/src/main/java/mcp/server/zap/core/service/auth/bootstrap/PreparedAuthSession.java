package mcp.server.zap.core.service.auth.bootstrap;

import mcp.server.zap.core.gateway.TargetDescriptor;

/**
 * In-memory descriptor for a prepared auth session.
 */
public record PreparedAuthSession(
        String sessionId,
        String profileId,
        AuthBootstrapKind authKind,
        String providerId,
        TargetDescriptor target,
        HttpOrigin authorizedOrigin,
        String credentialReference,
        String contextName,
        String contextId,
        String zapUserName,
        String userId,
        String headerName,
        String loginUrl,
        String verificationUrl,
        boolean engineBound,
        String subjectJsonPointer,
        String expectedSubject,
        mcp.server.zap.core.gateway.SignedJwtIdentity signedJwtIdentity
) {
    public PreparedAuthSession(String sessionId, String profileId, AuthBootstrapKind authKind, String providerId,
            TargetDescriptor target, HttpOrigin authorizedOrigin, String credentialReference, String contextName,
            String contextId, String zapUserName, String userId, String headerName, String loginUrl,
            String verificationUrl, boolean engineBound, String subjectJsonPointer, String expectedSubject) {
        this(sessionId, profileId, authKind, providerId, target, authorizedOrigin, credentialReference, contextName,
                contextId, zapUserName, userId, headerName, loginUrl, verificationUrl, engineBound, subjectJsonPointer,
                expectedSubject, null);
    }
    public PreparedAuthSession(
        String sessionId,
        String profileId,
        AuthBootstrapKind authKind,
        String providerId,
        TargetDescriptor target,
        HttpOrigin authorizedOrigin,
        String credentialReference,
        String contextName,
        String contextId,
        String zapUserName,
        String userId,
        String headerName,
        String loginUrl,
        String verificationUrl,
        boolean engineBound
    ) {
        this(sessionId, profileId, authKind, providerId, target, authorizedOrigin, credentialReference, contextName, contextId, zapUserName, userId, headerName, loginUrl, verificationUrl, engineBound, null, null);
    }
}

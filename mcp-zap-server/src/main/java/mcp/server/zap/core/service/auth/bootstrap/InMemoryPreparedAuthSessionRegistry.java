package mcp.server.zap.core.service.auth.bootstrap;

import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.Set;
import org.springframework.stereotype.Component;

/**
 * Default session registry for the guided auth bootstrap flow.
 */
@Component
public class InMemoryPreparedAuthSessionRegistry implements PreparedAuthSessionRegistry {
    private final ConcurrentMap<String, PreparedAuthSession> sessions = new ConcurrentHashMap<>();
    private final Set<String> validatedSessions = ConcurrentHashMap.newKeySet();

    @Override
    public PreparedAuthSession save(PreparedAuthSession session) {
        sessions.put(session.sessionId(), session);
        return session;
    }

    @Override
    public Optional<PreparedAuthSession> findById(String sessionId) {
        return Optional.ofNullable(sessions.get(sessionId));
    }

    @Override
    public void markValidated(String sessionId) {
        if (sessions.containsKey(sessionId)) {
            validatedSessions.add(sessionId);
        }
    }

    @Override
    public void invalidate(String sessionId) {
        validatedSessions.remove(sessionId);
    }

    @Override
    public boolean isValidated(String sessionId) {
        return sessions.containsKey(sessionId) && validatedSessions.contains(sessionId);
    }
}

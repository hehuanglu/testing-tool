package org.example.auth.dto;

import java.time.Instant;
import java.util.Objects;

public record AccessToken(String value, long expiresIn, Instant expiresAt) {
    public AccessToken {
        if (value == null || value.isBlank() || expiresIn <= 0) throw new IllegalArgumentException("Token không hợp lệ");
        Objects.requireNonNull(expiresAt, "expiresAt");
    }
    @Override public String toString() { return "AccessToken[REDACTED]"; }
}

package org.example.auth.dto;

public record TokenResponse(String accessToken, String tokenType, long expiresIn, AccountRecord user) {
    @Override public String toString() { return "TokenResponse[REDACTED]"; }
}

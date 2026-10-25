package org.example.auth.dto;

import java.util.Objects;

public record AccountCredential(AccountRecord account, String passwordHash) {
    public AccountCredential {
        Objects.requireNonNull(account, "account");
        if (passwordHash == null || passwordHash.isBlank()) throw new IllegalArgumentException("Thiếu passwordHash");
    }
    @Override public String toString() { return "AccountCredential[REDACTED]"; }
}

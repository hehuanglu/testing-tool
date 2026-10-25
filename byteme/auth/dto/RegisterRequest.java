package org.example.auth.dto;

public record RegisterRequest(String fullName, String email, String phone, String password, String confirmPassword) {
    @Override public String toString() { return "RegisterRequest[REDACTED]"; }
}

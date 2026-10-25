package org.example.auth.dto;

public record RegisterCommand(String fullName, String email, String phone,
                              String password, String confirmPassword) {
    @Override public String toString() { return "RegisterCommand[REDACTED]"; }
}

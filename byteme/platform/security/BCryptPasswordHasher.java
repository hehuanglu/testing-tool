package org.example.platform.security;

import java.nio.charset.StandardCharsets;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.example.auth.service.PasswordHasher;

/** Raw BCrypt 60 ký tự, tương thích password_hash và seed ByteMe. */
public final class BCryptPasswordHasher implements PasswordHasher {
    private final BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
    @Override public String hash(String rawPassword) {
        requireLength(rawPassword);
        return encoder.encode(rawPassword);
    }
    @Override public boolean matches(String rawPassword, String storedHash) {
        requireLength(rawPassword);
        return encoder.matches(rawPassword, storedHash);
    }
    private static void requireLength(String password) {
        if (password == null || password.getBytes(StandardCharsets.UTF_8).length > 72)
            throw new IllegalArgumentException("Password không được quá 72 byte UTF-8");
    }
}

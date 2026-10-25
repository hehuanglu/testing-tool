package org.example.auth.controller;

import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.example.auth.dto.*;
import org.example.auth.service.*;
import org.example.platform.security.LoginRateLimiter;

@RestController
public class AuthController {
    private final RegisterService register;
    private final LoginService login;
    private final LoginRateLimiter limiter;

    public AuthController(RegisterService register, LoginService login, LoginRateLimiter limiter) {
        this.register = register;
        this.login = login;
        this.limiter = limiter;
    }

    @PostMapping(path = "/api/auth/register", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AccountRecord> register(@RequestBody RegisterRequest request) {
        var result = register.register(new RegisterCommand(request.fullName(), request.email(), request.phone(), request.password(), request.confirmPassword()));
        return ResponseEntity.status(201).cacheControl(CacheControl.noStore()).body(result);
    }

    @PostMapping(path = "/api/auth/token", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<TokenResponse> login(@RequestBody LoginRequest request) {
        String email = AuthValidation.email(request.email());
        AuthValidation.password(request.password(), "password", 1);
        limiter.email(email);
        var result = login.login(new LoginCommand(email, request.password()));
        return ResponseEntity.ok().cacheControl(CacheControl.noStore())
                .body(new TokenResponse(result.token().value(), "Bearer", result.token().expiresIn(), result.user()));
    }
}

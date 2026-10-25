package org.example.auth.controller;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.example.auth.service.AuthFailure;
import org.example.auth.service.DuplicateAccountException;
import org.example.common.ApiError;
import org.example.common.GlobalErrors;
import org.example.platform.security.LoginRateLimiter;

/** Lỗi nghiệp vụ của Auth; lỗi chung (JSON sai, 405, 415, 500...) do GlobalErrors xử lý. */
@Order(Ordered.HIGHEST_PRECEDENCE)
@RestControllerAdvice(assignableTypes = AuthController.class)
public class AuthErrors {
    @ExceptionHandler(AuthFailure.class)
    ResponseEntity<ApiError> auth(AuthFailure e, HttpServletRequest r) {
        int status = switch (e.code()) {
            case "INVALID_CREDENTIALS" -> 401;
            case "ACCOUNT_NOT_ACTIVE" -> 403;
            default -> 400;
        };
        return ResponseEntity.status(status).cacheControl(CacheControl.noStore())
            .body(new ApiError(status, e.code(), e.getMessage(), r.getRequestURI(), e.fields()));
    }

    @ExceptionHandler(DuplicateAccountException.class)
    ResponseEntity<ApiError> duplicate(HttpServletRequest r) {
        return GlobalErrors.error(r, 409, "ACCOUNT_CONFLICT", "Thông tin tài khoản đã được sử dụng.");
    }

    @ExceptionHandler(LoginRateLimiter.LimitExceeded.class)
    ResponseEntity<ApiError> quota(LoginRateLimiter.LimitExceeded e, HttpServletRequest r) {
        return ResponseEntity.status(429).header("Retry-After", Long.toString(e.retryAfter())).cacheControl(CacheControl.noStore())
            .body(new ApiError(429, "LOGIN_RATE_LIMITED", "Vượt giới hạn đăng nhập.", r.getRequestURI()));
    }
}

package org.example.common;

import java.util.List;

/** Body lỗi chung cho mọi endpoint: {status, code, message, path, fieldErrors}. */
public record ApiError(int status, String code, String message, String path, List<FieldError> fieldErrors) {
    public record FieldError(String field, String message) {}

    public ApiError(int status, String code, String message, String path) {
        this(status, code, message, path, List.of());
    }
}

package org.example.auth.service;
import java.util.List;
import org.example.common.ApiError.FieldError;
public final class AuthFailure extends RuntimeException {
    private final String code;
    private final List<FieldError> fields;
    public AuthFailure(String code, String message) { this(code, message, List.of()); }
    public AuthFailure(String code, String message, List<FieldError> fields) {
        super(message); this.code=code; this.fields=List.copyOf(fields);
    }
    public String code() { return code; }
    public List<FieldError> fields() { return fields; }
}

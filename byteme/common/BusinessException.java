package org.example.common;

/**
 * Lỗi nghiệp vụ dùng chung cho Food/Cart/Order. Tầng nghiệp vụ chỉ chọn loại lỗi và mã lỗi;
 * GlobalErrors chuyển loại lỗi thành HTTP status, nên service không phụ thuộc framework web.
 */
public class BusinessException extends RuntimeException {
    public enum Type { INVALID, FORBIDDEN, NOT_FOUND, CONFLICT }

    private final Type type;
    private final String code;

    public BusinessException(Type type, String code, String message) {
        super(message);
        this.type = type;
        this.code = code;
    }

    public static BusinessException invalid(String code, String message) {
        return new BusinessException(Type.INVALID, code, message);
    }

    public static BusinessException forbidden(String code, String message) {
        return new BusinessException(Type.FORBIDDEN, code, message);
    }

    public static BusinessException notFound(String code, String message) {
        return new BusinessException(Type.NOT_FOUND, code, message);
    }

    public static BusinessException conflict(String code, String message) {
        return new BusinessException(Type.CONFLICT, code, message);
    }

    public Type type() { return type; }

    public String code() { return code; }
}

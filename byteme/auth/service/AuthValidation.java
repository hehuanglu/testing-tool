package org.example.auth.service;

import org.example.common.ApiError;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Locale;
public final class AuthValidation {
    private AuthValidation() {}
    public static String email(String value) {
        String v=text(value,"email",254).toLowerCase(Locale.ROOT);
        if (!v.matches("[^@\\s]+@[^@\\s]+\\.[^@\\s]+") || v.substring(0,v.indexOf('@')).length()>64)
            invalid("email","Email không hợp lệ.");
        return v;
    }
    public static String phone(String value) {
        String v=text(value,"phone",20);
        if (!v.matches("(?:0[0-9]{9}|\\+[1-9][0-9]{7,14})")) invalid("phone","Cần số nội địa 10 chữ số bắt đầu 0 hoặc số quốc tế.");
        return v;
    }
    public static String text(String value,String field,int max) {
        if(value==null) invalid(field,"Trường bắt buộc.");
        String v=value.trim();
        if(v.isBlank() || v.codePointCount(0,v.length())>max) invalid(field,"Độ dài không hợp lệ.");
        return v;
    }
    public static void password(String value,String field,int min) {
        if(value==null || value.codePointCount(0,value.length())<min || value.codePointCount(0,value.length())>72
           || value.getBytes(StandardCharsets.UTF_8).length>72) invalid(field,"Độ dài password không hợp lệ.");
    }
    public static void invalid(String field,String message) {
        throw new AuthFailure("VALIDATION_ERROR","Dữ liệu đầu vào không hợp lệ.",List.of(new ApiError.FieldError(field,message)));
    }
}

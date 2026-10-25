package org.example.auth.controller;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Type;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.cfg.*;
import com.fasterxml.jackson.databind.type.LogicalType;
import org.springframework.core.MethodParameter;
import org.springframework.http.*;
import org.springframework.http.converter.HttpMessageConverter;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.servlet.mvc.method.annotation.RequestBodyAdviceAdapter;

/** JSON strict chỉ cho Auth; không đổi ObjectMapper dùng chung của module khác. */
@ControllerAdvice(assignableTypes = AuthController.class)
public class AuthJsonAdvice extends RequestBodyAdviceAdapter {
    private final ObjectMapper strict;

    public AuthJsonAdvice(ObjectMapper shared) {
        strict = shared.copy().enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES,
                DeserializationFeature.FAIL_ON_TRAILING_TOKENS);
        for (var shape : new CoercionInputShape[]{CoercionInputShape.Integer,
                CoercionInputShape.Float, CoercionInputShape.Boolean}) {
            strict.coercionConfigFor(LogicalType.Textual).setCoercion(shape, CoercionAction.Fail);
        }
    }

    @Override public boolean supports(MethodParameter parameter, Type targetType,
            Class<? extends HttpMessageConverter<?>> converterType) {
        return parameter.getContainingClass() == AuthController.class;
    }

    @Override public HttpInputMessage beforeBodyRead(HttpInputMessage input, MethodParameter parameter,
            Type targetType, Class<? extends HttpMessageConverter<?>> converterType) throws IOException {
        byte[] body = input.getBody().readAllBytes();
        try {
            strict.readerFor(strict.constructType(targetType)).readValue(body);
        } catch (IOException e) {
            throw new HttpMessageNotReadableException("JSON/schema không hợp lệ.", input);
        }
        return new HttpInputMessage() {
            @Override public InputStream getBody() { return new ByteArrayInputStream(body); }
            @Override public HttpHeaders getHeaders() { return input.getHeaders(); }
        };
    }
}

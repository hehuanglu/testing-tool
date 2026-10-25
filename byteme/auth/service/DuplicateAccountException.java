package org.example.auth.service;

public class DuplicateAccountException extends RuntimeException {
    public DuplicateAccountException() { super("Email hoặc số điện thoại đã tồn tại."); }
}

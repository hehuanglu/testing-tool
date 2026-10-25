package org.example.auth.dto;

public record NewCustomer(String fullName, String email, String phone, String passwordHash) {
    public NewCustomer {
        if (fullName == null || fullName.isBlank() || email == null || email.isBlank()
                || phone == null || phone.isBlank() || passwordHash == null || passwordHash.isBlank())
            throw new IllegalArgumentException("NewCustomer thiếu dữ liệu bắt buộc");
    }
    @Override public String toString() { return "NewCustomer[REDACTED]"; }
}

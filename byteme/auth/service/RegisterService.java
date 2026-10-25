package org.example.auth.service;

import java.util.Objects;
import java.util.List;
import org.example.auth.dto.*;
import org.example.auth.entity.AccountStatus;
import org.example.auth.repository.AccountRepository;
import org.example.common.ApiError;
import org.example.shared.api.Role;
import org.springframework.stereotype.Service;

@Service
public class RegisterService {
    private final AccountRepository repository;
    private final PasswordHasher passwords;

    public RegisterService(AccountRepository repository, PasswordHasher passwords) {
        this.repository = repository;
        this.passwords = passwords;
    }

    public AccountRecord register(RegisterCommand command) {
        String name = AuthValidation.text(command.fullName(), "fullName", 150);
        String email = AuthValidation.email(command.email());
        String phone = AuthValidation.phone(command.phone());
        AuthValidation.password(command.password(), "password", 8);
        AuthValidation.password(command.confirmPassword(), "confirmPassword", 8);
        if (!Objects.equals(command.password(), command.confirmPassword()))
            throw new AuthFailure("PASSWORD_MISMATCH", "Mật khẩu xác nhận không khớp.", List.of(new ApiError.FieldError("confirmPassword", "Phải trùng password.")));
        if (repository.existsByEmailOrPhone(email, phone)) throw new DuplicateAccountException();
        AccountRecord result = repository.createCustomer(new NewCustomer(name, email, phone, passwords.hash(command.password())));
        if (result.role() != Role.CUSTOMER || result.status() != AccountStatus.ACTIVE)
            throw new AccountPersistenceException(new IllegalStateException("Repository vi phạm createCustomer"));
        return result;
    }
}

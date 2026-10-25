package org.example.auth.repository;

import java.sql.SQLException;
import java.util.Optional;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;
import org.example.auth.dto.*;
import org.example.auth.entity.AccountStatus;
import org.example.auth.entity.User;
import org.example.auth.service.AccountPersistenceException;
import org.example.auth.service.DuplicateAccountException;
import org.example.shared.api.Role;

@Repository
public class MySqlAccountRepository implements AccountRepository {
    private final UserRepository userRepository;

    public MySqlAccountRepository(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    @Transactional(readOnly = true)
    public boolean existsByEmailOrPhone(String email, String phone) {
        try {
            return userRepository.existsByEmailOrPhone(email, phone);
        } catch (RuntimeException e) {
            throw new AccountPersistenceException(e);
        }
    }

    @Override
    @Transactional
    public AccountRecord createCustomer(NewCustomer input) {
        try {
            var row = new User();
            row.setFullName(input.fullName());
            row.setEmail(input.email());
            row.setPhone(input.phone());
            row.setPasswordHash(input.passwordHash());
            row.setRole("CUSTOMER");
            row.setStatus("ACTIVE");
            return map(userRepository.saveAndFlush(row));
        } catch (RuntimeException e) {
            for (Throwable cause = e; cause != null; cause = cause.getCause()) {
                if (cause instanceof SQLException sql && sql.getErrorCode() == 1062
                    && (sql.getMessage().contains("uq_users_email") || sql.getMessage().contains("uq_users_phone")))
                    throw new DuplicateAccountException();
            }
            throw new AccountPersistenceException(e);
        }
    }

    @Override
    @Transactional(readOnly = true)
    public Optional<AccountCredential> findCredentialByEmail(String email) {
        try {
            return userRepository.findByEmail(email).map(row -> new AccountCredential(map(row), row.getPasswordHash()));
        } catch (RuntimeException e) {
            throw new AccountPersistenceException(e);
        }
    }

    private static AccountRecord map(User row) {
        return new AccountRecord(row.getId().toString(), row.getFullName(), row.getEmail(), row.getPhone(),
                                 Role.valueOf(row.getRole()), AccountStatus.valueOf(row.getStatus()));
    }
}

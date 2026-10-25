package org.example.auth.repository;

import java.util.Optional;
import org.example.auth.dto.AccountCredential;
import org.example.auth.dto.AccountRecord;
import org.example.auth.dto.NewCustomer;

public interface AccountRepository {
    boolean existsByEmailOrPhone(String email, String phone);
    AccountRecord createCustomer(NewCustomer input);
    Optional<AccountCredential> findCredentialByEmail(String email);
}

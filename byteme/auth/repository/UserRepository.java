package org.example.auth.repository;

import java.util.Optional;
import org.example.auth.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface UserRepository extends JpaRepository<User, Long> {
    boolean existsByEmailOrPhone(String email, String phone);
    Optional<User> findByEmail(String email);
}

package org.example.cart.repository;

import org.example.cart.entity.Cart;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface CartRepository extends JpaRepository<Cart, Long> {
    Optional<Cart> findByUserId(Long userId);

    /** Ghi các item đã thêm/sửa/xóa (flush để item mới có id trước khi trả DTO). */
    default void saveChanges(Cart cart) {
        saveAndFlush(cart);
    }
}

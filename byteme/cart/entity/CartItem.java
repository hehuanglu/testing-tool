package org.example.cart.entity;

import jakarta.persistence.*;
import lombok.*;


/** created_at/updated_at do MySQL tự đặt (DEFAULT / ON UPDATE CURRENT_TIMESTAMP), không map ở đây. */
@Entity
@Table(name = "cart_items")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class CartItem {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "cart_id", nullable = false)
    private Cart cart;

    // Chỉ giữ ID món: Cart lấy thông tin món qua FoodService, không dùng entity của module Food.
    @Column(name = "food_id", nullable = false)
    private Long foodId;

    @Column(nullable = false)
    private Integer quantity;
}

package org.example.order.entity;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;

/** Snapshot tên/giá món tại lúc đặt; không đổi khi món được sửa sau đó. created_at do MySQL tự đặt. */
@Entity
@Table(name = "order_items")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class OrderItem {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "order_id", nullable = false)
    private Order order;

    // Chỉ giữ ID món, không dùng entity của module Food.
    @Column(name = "food_id", nullable = false)
    private Long foodId;

    @Column(name = "food_name", nullable = false, length = 150)
    private String foodName;

    @Column(name = "unit_price", nullable = false, precision = 15, scale = 2)
    private BigDecimal unitPrice;

    @Column(nullable = false)
    private Integer quantity;
}

package org.example.order.dto;

import org.example.order.entity.OrderItem;

import java.math.BigDecimal;

public record OrderItemDto(Long foodId, String foodName, BigDecimal unitPrice, int quantity, BigDecimal lineTotal) {
    public static OrderItemDto fromEntity(OrderItem item) {
        return new OrderItemDto(item.getFoodId(), item.getFoodName(), item.getUnitPrice(), item.getQuantity(),
                item.getUnitPrice().multiply(BigDecimal.valueOf(item.getQuantity())));
    }
}

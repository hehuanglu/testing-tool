package org.example.order.dto;

import jakarta.validation.constraints.NotNull;
import org.example.order.domain.OrderStatus;

public record StatusRequest(
        @NotNull(message = "status là bắt buộc")
        OrderStatus status) {
}

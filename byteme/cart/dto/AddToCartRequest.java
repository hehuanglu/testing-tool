package org.example.cart.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

public record AddToCartRequest(
        @NotNull(message = "foodId là bắt buộc")
        @Positive(message = "foodId phải là số dương")
        Long foodId,

        @NotNull(message = "Số lượng là bắt buộc")
        @Min(value = 1, message = "Số lượng tối thiểu là 1")
        Integer quantity) {
}

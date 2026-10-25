package org.example.food.dto;

import org.example.food.entity.Food;

import java.math.BigDecimal;

public record FoodDto(Long id, Long categoryId, String name, String description, BigDecimal price,
        String imageUrl, Integer stockQuantity, String status) {

    public static FoodDto fromEntity(Food food) {
        return new FoodDto(food.getId(), food.getCategoryId(), food.getName(), food.getDescription(),
                food.getPrice(), food.getImageUrl(), food.getStockQuantity(), food.getStatus());
    }
}

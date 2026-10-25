package org.example.cart.dto;

import org.example.food.dto.FoodDto;

public record CartItemDto(Long id, FoodDto food, Integer quantity) {}

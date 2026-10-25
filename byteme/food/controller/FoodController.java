package org.example.food.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.example.food.dto.FoodDto;
import org.example.food.dto.FoodRequest;
import org.example.food.service.FoodService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/foods")
@RequiredArgsConstructor
public class FoodController {

    private final FoodService foodService;

    @GetMapping
    public ResponseEntity<List<FoodDto>> getFoods(@RequestParam(required = false) Long categoryId) {
        return ResponseEntity.ok(foodService.getActiveFoods(categoryId));
    }

    @GetMapping("/{id}")
    public ResponseEntity<FoodDto> getFoodById(@PathVariable Long id) {
        return ResponseEntity.ok(foodService.getFoodById(id));
    }

    @GetMapping("/search")
    public ResponseEntity<List<FoodDto>> searchFoods(
            @RequestParam String q,
            @RequestParam(required = false) Long categoryId) {
        return ResponseEntity.ok(foodService.searchFoods(q, categoryId));
    }

    @PostMapping
    public ResponseEntity<FoodDto> createFood(@Valid @RequestBody FoodRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(foodService.createFood(request));
    }

    @PutMapping("/{id}")
    public ResponseEntity<FoodDto> updateFood(@PathVariable Long id, @Valid @RequestBody FoodRequest request) {
        return ResponseEntity.ok(foodService.updateFood(id, request));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteFood(@PathVariable Long id) {
        foodService.deleteFood(id);
        return ResponseEntity.noContent().build();
    }
}

package org.example.food.service;

import lombok.RequiredArgsConstructor;
import org.example.common.BusinessException;
import org.example.food.dto.FoodDto;
import org.example.food.dto.FoodRequest;
import org.example.food.entity.Food;
import org.example.food.repository.CategoryRepository;
import org.example.food.repository.FoodRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class FoodService {

    private static final String ACTIVE = "ACTIVE";

    private final FoodRepository foodRepository;
    private final CategoryRepository categoryRepository;

    @Transactional(readOnly = true)
    public List<FoodDto> getActiveFoods(Long categoryId) {
        if (categoryId != null) requireCategory(categoryId);
        return foodRepository.findActive(categoryId).stream().map(FoodDto::fromEntity).toList();
    }

    @Transactional(readOnly = true)
    public FoodDto getFoodById(Long id) {
        Food food = findFood(id);
        if (!ACTIVE.equals(food.getStatus())) {
            throw foodNotFound();
        }
        return FoodDto.fromEntity(food);
    }

    @Transactional(readOnly = true)
    public List<FoodDto> searchFoods(String keyword, Long categoryId) {
        if (keyword == null || keyword.trim().isEmpty() || keyword.trim().length() > 100) {
            throw BusinessException.invalid("VALIDATION_ERROR", "Từ khóa phải có từ 1 đến 100 ký tự.");
        }

        if (categoryId != null) requireCategory(categoryId);
        return foodRepository.searchActive(escapeLike(keyword.trim()), categoryId).stream()
                .map(FoodDto::fromEntity).toList();
    }

    @Transactional
    public FoodDto createFood(FoodRequest request) {
        requireCategory(request.categoryId());

        String name = request.name().trim();
        if (foodRepository.existsByName(name)) {
            throw duplicateName();
        }

        Food food = Food.builder()
                .categoryId(request.categoryId())
                .name(name)
                .description(request.description())
                .price(request.price())
                .imageUrl(request.imageUrl())
                .stockQuantity(request.stockQuantity() != null ? request.stockQuantity() : 0)
                .status(request.status() != null ? request.status() : ACTIVE)
                .build();
        return FoodDto.fromEntity(foodRepository.save(food));
    }

    /** Entity đã được JPA quản lý: thay đổi tự ghi xuống DB khi transaction commit, không cần save(). */
    @Transactional
    public FoodDto updateFood(Long id, FoodRequest request) {
        Food food = findFood(id);
        requireCategory(request.categoryId());

        String name = request.name().trim();
        if (foodRepository.existsByNameAndIdNot(name, id)) {
            throw duplicateName();
        }

        food.setCategoryId(request.categoryId());
        food.setName(name);
        food.setDescription(request.description());
        food.setPrice(request.price());
        food.setImageUrl(request.imageUrl());
        if (request.stockQuantity() != null) food.setStockQuantity(request.stockQuantity());
        if (request.status() != null) food.setStatus(request.status());
        return FoodDto.fromEntity(food);
    }

    /** Ngừng bán (INACTIVE) thay vì xóa: đơn cũ giữ snapshot, hủy đơn vẫn hoàn kho được. */
    @Transactional
    public void deleteFood(Long id) {
        findFood(id).setStatus("INACTIVE");
    }

    // ----- Dùng bởi module Cart -----

    /** Món phải tồn tại (404) và đang bán (409) mới được thêm vào giỏ. */
    @Transactional(readOnly = true)
    public FoodDto getAvailableFood(long id) {
        Food food = findFood(id);
        requireActive(food);
        return FoodDto.fromEntity(food);
    }

    /** Thông tin món để hiển thị trong giỏ, kể cả món đã ngừng bán. */
    @Transactional(readOnly = true)
    public Map<Long, FoodDto> findByIds(Collection<Long> ids) {
        return foodRepository.findAllById(ids).stream()
                .map(FoodDto::fromEntity)
                .collect(Collectors.toMap(FoodDto::id, Function.identity()));
    }

    // ----- Dùng bởi module Order, luôn trong giao dịch của Order -----

    /**
     * Kiểm tra món còn bán và đủ kho rồi trừ kho; thay đổi ghi xuống DB khi giao dịch Order commit.
     * Trả về tên/giá hiện tại để Order lưu snapshot.
     */
    @Transactional
    public FoodDto reserveStock(long id, int quantity) {
        Food food = findFood(id);
        requireActive(food);
        if (food.getStockQuantity() < quantity) {
            throw BusinessException.conflict("INSUFFICIENT_STOCK", "Món ăn không đủ tồn kho.");
        }
        food.setStockQuantity(food.getStockQuantity() - quantity);
        return FoodDto.fromEntity(food);
    }

    /** Hoàn lại kho khi hủy đơn, kể cả món đã ngừng bán. */
    @Transactional
    public void releaseStock(long id, int quantity) {
        Food food = findFood(id);
        food.setStockQuantity(food.getStockQuantity() + quantity);
    }

    private Food findFood(long id) {
        return foodRepository.findById(id).orElseThrow(FoodService::foodNotFound);
    }

    private void requireCategory(Long categoryId) {
        if (!categoryRepository.existsById(categoryId)) {
            throw BusinessException.notFound("CATEGORY_NOT_FOUND", "Không tìm thấy danh mục.");
        }
    }

    private static void requireActive(Food food) {
        if (!ACTIVE.equals(food.getStatus())) {
            throw BusinessException.conflict("FOOD_UNAVAILABLE", "Món ăn đã ngừng bán.");
        }
    }

    private static BusinessException foodNotFound() {
        return BusinessException.notFound("FOOD_NOT_FOUND", "Không tìm thấy món ăn.");
    }

    private static BusinessException duplicateName() {
        return BusinessException.conflict("FOOD_NAME_CONFLICT", "Tên món ăn đã tồn tại trong thực đơn.");
    }

    /** Escape ký tự đại diện của LIKE để '%' và '_' trong từ khóa được tìm đúng nghĩa đen. */
    private static String escapeLike(String keyword) {
        return keyword.replace("!", "!!").replace("%", "!%").replace("_", "!_");
    }
}

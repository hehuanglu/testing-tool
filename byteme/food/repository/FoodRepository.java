package org.example.food.repository;

import org.example.food.entity.Food;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;

public interface FoodRepository extends JpaRepository<Food, Long> {
    // categoryId = null nghĩa là không lọc theo danh mục.
    @Query("""
            select f from Food f
            where f.status = 'ACTIVE' and (:categoryId is null or f.categoryId = :categoryId)
            order by f.id""")
    List<Food> findActive(Long categoryId);

    // keyword đã được escape '%', '_' và '!' (ký tự escape) ở FoodService.
    @Query("""
            select f from Food f
            where f.status = 'ACTIVE' and (:categoryId is null or f.categoryId = :categoryId)
              and (lower(f.name) like lower(concat('%', :keyword, '%')) escape '!'
                   or lower(f.description) like lower(concat('%', :keyword, '%')) escape '!')
            order by f.id""")
    List<Food> searchActive(String keyword, Long categoryId);

    // Tên đã trim ở FoodService; collation _ci của MySQL nên so sánh = không phân biệt hoa thường (uq_foods_name).
    boolean existsByName(String name);
    boolean existsByNameAndIdNot(String name, Long id);
}

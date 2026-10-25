package org.example.food.dto;

import jakarta.validation.constraints.Digits;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;

import java.math.BigDecimal;

/**
 * Giới hạn độ dài khớp với cột trong schema.sql để dữ liệu quá dài trả 400 thay vì lỗi từ DB.
 * stockQuantity/status bỏ trống: khi tạo dùng mặc định (0, ACTIVE), khi cập nhật giữ nguyên.
 */
public record FoodRequest(
        @NotNull(message = "categoryId là bắt buộc")
        @Positive(message = "categoryId phải là số dương")
        Long categoryId,

        @NotBlank(message = "Tên món là bắt buộc")
        @Size(max = 150, message = "Tên món tối đa 150 ký tự")
        String name,

        // Cột TEXT tối đa 65.535 byte; 16.000 ký tự utf8mb4 luôn vừa.
        @Size(max = 16000, message = "Mô tả tối đa 16000 ký tự")
        String description,

        @NotNull(message = "Giá là bắt buộc")
        @Positive(message = "Giá phải lớn hơn 0")
        @Digits(integer = 13, fraction = 2, message = "Giá tối đa 13 chữ số phần nguyên và 2 chữ số thập phân")
        BigDecimal price,

        @Size(max = 2048, message = "imageUrl tối đa 2048 ký tự")
        String imageUrl,

        @Min(value = 0, message = "Tồn kho không được âm")
        Integer stockQuantity,

        @Pattern(regexp = "^(ACTIVE|INACTIVE)$", message = "Trạng thái phải là ACTIVE hoặc INACTIVE")
        String status) {
}

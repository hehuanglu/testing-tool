package org.example.food.entity;

import jakarta.persistence.*;

/** Chỉ dùng để kiểm tra danh mục tồn tại; danh mục được tạo bằng seed.sql, chưa có API quản lý. */
@Entity
@Table(name = "categories")
public class Category {
    @Id
    private Long id;
}

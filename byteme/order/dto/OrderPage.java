package org.example.order.dto;

import java.util.List;

public record OrderPage(List<OrderDto> content, int page, int size, long totalElements) {}

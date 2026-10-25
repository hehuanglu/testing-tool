package org.example.order.repository;

import org.example.order.domain.OrderStatus;
import org.example.order.domain.OrderType;
import org.example.order.entity.Order;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.Collection;
import java.util.List;

public interface OrderRepository extends JpaRepository<Order, Long> {
    String FILTER = """
            from Order o
            where (:userId is null or o.userId = :userId)
              and (:type is null or o.orderType = :type)
              and o.status in :statuses
            """;

    @Query("select o " + FILTER + " order by o.createdAt desc, o.id desc")
    List<Order> search(Long userId, Collection<OrderStatus> statuses, OrderType type, Pageable pageable);

    @Query("select count(o) " + FILTER)
    long countMatching(Long userId, Collection<OrderStatus> statuses, OrderType type);

    /** Phân trang bằng page/size số nguyên để tầng nghiệp vụ không phụ thuộc kiểu của Spring Data. */
    default List<Order> findPage(Long userId, Collection<OrderStatus> statuses, OrderType type, int page, int size) {
        return search(userId, statuses, type, PageRequest.of(page, size));
    }
}

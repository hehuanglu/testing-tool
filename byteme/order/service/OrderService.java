package org.example.order.service;

import lombok.RequiredArgsConstructor;
import org.example.cart.service.CartService;
import org.example.common.BusinessException;
import org.example.food.dto.FoodDto;
import org.example.food.service.FoodService;
import org.example.order.dto.CreateOrderRequest;
import org.example.order.dto.OrderDto;
import org.example.order.dto.OrderPage;
import org.example.order.domain.*;
import org.example.order.entity.*;
import org.example.order.repository.OrderRepository;
import org.example.shared.api.Role;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;

/**
 * Nghiệp vụ đơn hàng. Quyền theo vai trò đã được SecurityConfiguration kiểm tra;
 * service chỉ kiểm tra quyền sở hữu đơn và quy tắc nghiệp vụ.
 */
@Service
@RequiredArgsConstructor
public class OrderService {
    private static final List<OrderStatus> EMPLOYEE_QUEUE =
            List.of(OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PROCESSING, OrderStatus.SHIPPING);

    private final OrderRepository orders;
    private final CartService cartService;
    private final FoodService foodService;
    private final Clock clock;

    /**
     * Checkout trong một giao dịch: đọc giỏ, kiểm tra và trừ kho từng món, lưu đơn PENDING
     * với snapshot tên/giá rồi dọn giỏ. Lỗi ở bất kỳ bước nào rollback toàn bộ.
     */
    @Transactional
    public OrderDto create(long customerId, CreateOrderRequest request) {
        CreateOrderRequest input = applyOrderTypeRules(request);
        Map<Long, Integer> cart = cartService.getItemsForCheckout(customerId);
        if (cart.isEmpty()) throw BusinessException.invalid("EMPTY_CART", "Giỏ hàng đang rỗng.");

        Instant now = now();
        Order order = Order.builder()
                .userId(customerId)
                .orderType(input.orderType())
                .status(OrderStatus.PENDING)
                .tableNumber(input.tableNumber())
                .recipientName(input.recipientName())
                .shippingPhone(input.shippingPhone())
                .shippingAddress(input.shippingAddress())
                .paymentMethod(input.paymentMethod())
                .note(input.note())
                .createdAt(now)
                .updatedAt(now)
                .build();
        cart.forEach((foodId, quantity) -> {
            FoodDto food = foodService.reserveStock(foodId, quantity);
            order.getItems().add(OrderItem.builder()
                    .order(order)
                    .foodId(foodId)
                    .foodName(food.name())
                    .unitPrice(food.price())
                    .quantity(quantity)
                    .build());
        });
        Order saved = orders.save(order);
        cartService.clearCart(customerId);
        return OrderDto.fromEntity(saved);
    }

    /** CUSTOMER chỉ thấy đơn của mình; EMPLOYEE mặc định thấy các đơn đang cần xử lý. */
    @Transactional(readOnly = true)
    public OrderPage list(long userId, Role role, OrderStatus status, OrderType type, int page, int size) {
        if (page < 0 || size < 1 || size > 100 || page > Integer.MAX_VALUE / size) {
            throw BusinessException.invalid("VALIDATION_ERROR", "page >= 0; size từ 1 đến 100.");
        }
        List<OrderStatus> statuses;
        if (status != null) statuses = List.of(status);
        else if (role == Role.EMPLOYEE) statuses = EMPLOYEE_QUEUE;
        else statuses = List.of(OrderStatus.values());
        Long ownerId = role == Role.CUSTOMER ? userId : null;

        List<OrderDto> content = orders.findPage(ownerId, statuses, type, page, size).stream()
                .map(OrderDto::fromEntity).toList();
        return new OrderPage(content, page, size, orders.countMatching(ownerId, statuses, type));
    }

    @Transactional(readOnly = true)
    public OrderDto get(long userId, Role role, long orderId) {
        Order order = orders.findById(orderId).orElseThrow(OrderService::orderNotFound);
        if (role == Role.CUSTOMER) requireOwner(order, userId);
        return OrderDto.fromEntity(order);
    }

    /** Khách chỉ hủy đơn PENDING của chính mình. */
    @Transactional
    public OrderDto cancel(long customerId, long orderId) {
        Order order = orders.findById(orderId).orElseThrow(OrderService::orderNotFound);
        requireOwner(order, customerId);
        if (order.getStatus() != OrderStatus.PENDING) throw invalidTransition();
        return OrderDto.fromEntity(moveTo(order, OrderStatus.CANCELLED, customerId));
    }

    @Transactional
    public OrderDto confirm(long employeeId, long orderId) {
        return updateStatus(employeeId, orderId, OrderStatus.CONFIRMED);
    }

    @Transactional
    public OrderDto updateStatus(long employeeId, long orderId, OrderStatus next) {
        if (next == OrderStatus.PENDING)
            throw BusinessException.invalid("VALIDATION_ERROR", "Không thể chuyển đơn về PENDING.");
        Order order = orders.findById(orderId).orElseThrow(OrderService::orderNotFound);
        if (!canMove(order, next)) throw invalidTransition();
        return OrderDto.fromEntity(moveTo(order, next, employeeId));
    }

    /** PENDING → CONFIRMED → PROCESSING; DINE_IN → COMPLETED, DELIVERY → SHIPPING → COMPLETED. */
    private static boolean canMove(Order order, OrderStatus next) {
        return switch (order.getStatus()) {
            case PENDING -> next == OrderStatus.CONFIRMED || next == OrderStatus.CANCELLED;
            case CONFIRMED -> next == OrderStatus.PROCESSING || next == OrderStatus.CANCELLED;
            case PROCESSING -> next == OrderStatus.CANCELLED
                    || (order.getOrderType() == OrderType.DINE_IN && next == OrderStatus.COMPLETED)
                    || (order.getOrderType() == OrderType.DELIVERY && next == OrderStatus.SHIPPING);
            case SHIPPING -> next == OrderStatus.COMPLETED;
            case COMPLETED, CANCELLED -> false;
        };
    }

    /** Hủy đơn thì hoàn kho; CANCELLED là trạng thái cuối nên một đơn chỉ được hủy một lần. */
    private Order moveTo(Order order, OrderStatus next, long actorId) {
        Instant now = now();
        if (next == OrderStatus.CANCELLED) {
            order.getItems().forEach(item -> foodService.releaseStock(item.getFoodId(), item.getQuantity()));
            order.setCancelledAt(now);
        }
        if (next == OrderStatus.CONFIRMED) {
            order.setConfirmedBy(actorId);
            order.setConfirmedAt(now);
        }
        if (next == OrderStatus.COMPLETED) order.setCompletedAt(now);
        order.setStatus(next);
        order.setUpdatedAt(now);
        return order;
    }

    /**
     * DTO đã được @Valid kiểm tra bắt buộc/độ dài; ở đây là quy tắc theo loại đơn: DINE_IN cần số bàn,
     * DELIVERY cần thông tin giao hàng, và mỗi loại chỉ nhận phương thức thanh toán phù hợp.
     */
    private static CreateOrderRequest applyOrderTypeRules(CreateOrderRequest input) {
        String note = trimToNull(input.note());
        if (input.orderType() == OrderType.DINE_IN) {
            if (input.recipientName() != null || input.shippingPhone() != null || input.shippingAddress() != null
                    || input.paymentMethod() == PaymentMethod.COD)
                throw BusinessException.invalid("VALIDATION_ERROR", "DINE_IN không nhận thông tin giao hàng hoặc thanh toán COD.");
            return new CreateOrderRequest(input.orderType(), required(input.tableNumber(), "tableNumber"),
                    null, null, null, input.paymentMethod(), note);
        }
        if (input.tableNumber() != null || input.paymentMethod() == PaymentMethod.CASH)
            throw BusinessException.invalid("VALIDATION_ERROR", "DELIVERY không nhận tableNumber hoặc thanh toán CASH.");
        return new CreateOrderRequest(input.orderType(), null, required(input.recipientName(), "recipientName"),
                required(input.shippingPhone(), "shippingPhone"),
                required(input.shippingAddress(), "shippingAddress"), input.paymentMethod(), note);
    }

    private static String required(String value, String field) {
        String result = trimToNull(value);
        if (result == null) throw BusinessException.invalid("VALIDATION_ERROR", field + " là bắt buộc với loại đơn này.");
        return result;
    }

    private static String trimToNull(String value) {
        String result = value == null ? null : value.trim();
        return result == null || result.isEmpty() ? null : result;
    }

    private static void requireOwner(Order order, long customerId) {
        if (!order.getUserId().equals(customerId))
            throw BusinessException.forbidden("FORBIDDEN", "Đơn hàng không thuộc khách hàng hiện tại.");
    }

    private Instant now() {
        // DATETIME(6) lưu tới micro giây; cắt trước để giá trị trả về khớp với giá trị đọc lại.
        return clock.instant().truncatedTo(ChronoUnit.MICROS);
    }

    private static BusinessException orderNotFound() {
        return BusinessException.notFound("ORDER_NOT_FOUND", "Không tìm thấy đơn hàng.");
    }

    private static BusinessException invalidTransition() {
        return BusinessException.conflict("INVALID_ORDER_TRANSITION", "Không thể chuyển trạng thái đơn hàng.");
    }
}

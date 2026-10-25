package org.example.order.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.example.common.CurrentUser;
import org.example.order.dto.CreateOrderRequest;
import org.example.order.dto.OrderDto;
import org.example.order.dto.OrderPage;
import org.example.order.dto.StatusRequest;
import org.example.order.domain.OrderStatus;
import org.example.order.domain.OrderType;
import org.example.order.service.OrderService;
import org.example.shared.api.AuthenticatedUser;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.net.URI;

@RestController
@RequestMapping(path = "/api/orders", produces = MediaType.APPLICATION_JSON_VALUE)
@RequiredArgsConstructor
public class OrderController {

    // Xác thực và quyền theo vai trò do SecurityConfiguration kiểm tra trước khi vào controller.
    private final OrderService orderService;

    @PostMapping
    public ResponseEntity<OrderDto> create(@AuthenticationPrincipal AuthenticatedUser user,
            @Valid @RequestBody CreateOrderRequest request) {
        OrderDto order = orderService.create(CurrentUser.id(user), request);
        return ResponseEntity.created(URI.create("/api/orders/" + order.id()))
                .cacheControl(CacheControl.noStore()).body(order);
    }

    @GetMapping
    public ResponseEntity<OrderPage> list(@AuthenticationPrincipal AuthenticatedUser user,
            @RequestParam(required = false) OrderStatus status, @RequestParam(required = false) OrderType orderType,
            @RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore())
                .body(orderService.list(CurrentUser.id(user), user.role(), status, orderType, page, size));
    }

    @GetMapping("/{orderId}")
    public ResponseEntity<OrderDto> get(@AuthenticationPrincipal AuthenticatedUser user, @PathVariable long orderId) {
        return ok(orderService.get(CurrentUser.id(user), user.role(), orderId));
    }

    @DeleteMapping("/{orderId}")
    public ResponseEntity<OrderDto> cancel(@AuthenticationPrincipal AuthenticatedUser user, @PathVariable long orderId) {
        return ok(orderService.cancel(CurrentUser.id(user), orderId));
    }

    @PostMapping("/{orderId}/confirm")
    public ResponseEntity<OrderDto> confirm(@AuthenticationPrincipal AuthenticatedUser user, @PathVariable long orderId) {
        return ok(orderService.confirm(CurrentUser.id(user), orderId));
    }

    @PutMapping("/{orderId}/status")
    public ResponseEntity<OrderDto> updateStatus(@AuthenticationPrincipal AuthenticatedUser user,
            @PathVariable long orderId, @Valid @RequestBody StatusRequest request) {
        return ok(orderService.updateStatus(CurrentUser.id(user), orderId, request.status()));
    }

    private static ResponseEntity<OrderDto> ok(OrderDto order) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(order);
    }
}

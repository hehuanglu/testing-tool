package org.example.cart.service;

import lombok.RequiredArgsConstructor;
import org.example.cart.dto.AddToCartRequest;
import org.example.cart.dto.CartDto;
import org.example.cart.dto.CartItemDto;
import org.example.cart.dto.UpdateCartItemRequest;
import org.example.cart.entity.Cart;
import org.example.cart.entity.CartItem;
import org.example.cart.repository.CartRepository;
import org.example.common.BusinessException;
import org.example.food.dto.FoodDto;
import org.example.food.service.FoodService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class CartService {

    private final CartRepository cartRepository;
    private final FoodService foodService;

    /** Chưa có giỏ thì trả giỏ rỗng (id = null) mà không tạo hàng carts. */
    @Transactional(readOnly = true)
    public CartDto getCart(long userId) {
        return cartRepository.findByUserId(userId)
                .map(this::toCartDto)
                .orElseGet(() -> new CartDto(null, userId, List.of()));
    }

    /** Giỏ được tạo ở lần thêm món đầu tiên. */
    @Transactional
    public CartDto addToCart(long userId, AddToCartRequest request) {
        Cart cart = cartRepository.findByUserId(userId)
                .orElseGet(() -> cartRepository.save(Cart.builder().userId(userId).build()));
        FoodDto food = foodService.getAvailableFood(request.foodId());

        Optional<CartItem> existingItem = cart.getItems().stream()
                .filter(item -> item.getFoodId().equals(food.id()))
                .findFirst();

        if (existingItem.isPresent()) {
            CartItem item = existingItem.get();
            try {
                item.setQuantity(Math.addExact(item.getQuantity(), request.quantity()));
            } catch (ArithmeticException error) {
                throw BusinessException.invalid("VALIDATION_ERROR", "Số lượng quá lớn.");
            }
        } else {
            CartItem newItem = CartItem.builder()
                    .cart(cart)
                    .foodId(food.id())
                    .quantity(request.quantity())
                    .build();
            cart.getItems().add(newItem);
        }

        cartRepository.saveChanges(cart);
        return toCartDto(cart);
    }

    @Transactional
    public CartDto updateCartItem(long userId, Long cartItemId, UpdateCartItemRequest request) {
        Cart cart = cartRepository.findByUserId(userId).orElseThrow(CartService::cartItemNotFound);

        CartItem cartItem = cart.getItems().stream()
                .filter(item -> item.getId().equals(cartItemId))
                .findFirst()
                .orElseThrow(CartService::cartItemNotFound);

        cartItem.setQuantity(request.quantity());
        cartRepository.saveChanges(cart);
        return toCartDto(cart);
    }

    @Transactional
    public CartDto removeCartItem(long userId, Long cartItemId) {
        Cart cart = cartRepository.findByUserId(userId).orElseThrow(CartService::cartItemNotFound);

        boolean removed = cart.getItems().removeIf(item -> item.getId().equals(cartItemId));
        if (!removed) {
            throw cartItemNotFound();
        }

        cartRepository.saveChanges(cart);
        return toCartDto(cart);
    }

    // ----- Dùng bởi module Order, luôn trong giao dịch checkout -----

    /** foodId → số lượng theo thứ tự món trong giỏ; chưa có giỏ thì trả map rỗng. */
    @Transactional(readOnly = true)
    public Map<Long, Integer> getItemsForCheckout(long userId) {
        Map<Long, Integer> items = new LinkedHashMap<>();
        cartRepository.findByUserId(userId).ifPresent(cart ->
                cart.getItems().forEach(item -> items.put(item.getFoodId(), item.getQuantity())));
        return items;
    }

    /** Dọn giỏ sau khi tạo đơn; giữ lại hàng carts để khách tiếp tục thêm món. */
    @Transactional
    public void clearCart(long userId) {
        cartRepository.findByUserId(userId).ifPresent(cart -> {
            cart.getItems().clear();
            cartRepository.saveChanges(cart);
        });
    }

    private CartDto toCartDto(Cart cart) {
        Map<Long, FoodDto> foods = foodService.findByIds(
                cart.getItems().stream().map(CartItem::getFoodId).toList());
        List<CartItemDto> items = cart.getItems().stream()
                .map(item -> new CartItemDto(item.getId(), foods.get(item.getFoodId()), item.getQuantity()))
                .toList();
        return new CartDto(cart.getId(), cart.getUserId(), items);
    }

    private static BusinessException cartItemNotFound() {
        return BusinessException.notFound("CART_ITEM_NOT_FOUND", "Không tìm thấy món trong giỏ hàng.");
    }
}

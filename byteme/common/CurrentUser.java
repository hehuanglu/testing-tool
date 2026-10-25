package org.example.common;

import org.example.shared.api.AuthenticatedUser;

/**
 * Lấy ID tài khoản từ người dùng đã được JWT filter xác thực. Việc xác thực và phân quyền
 * nằm ở SecurityConfiguration; controller chỉ đổi subject của JWT sang ID số trong database.
 */
public final class CurrentUser {
    private CurrentUser() {}

    public static long id(AuthenticatedUser user) {
        try {
            long id = Long.parseLong(user.userId());
            if (id > 0) return id;
        } catch (NumberFormatException ignored) { }
        throw BusinessException.forbidden("FORBIDDEN", "JWT phải chứa ID tài khoản hợp lệ trong database.");
    }
}

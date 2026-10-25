package org.example.platform.security;
import java.io.IOException;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.web.filter.OncePerRequestFilter;
import org.example.common.ApiError;
public final class LoginIpFilter extends OncePerRequestFilter {
    private final LoginRateLimiter limiter;private final ObjectMapper json;
    public LoginIpFilter(LoginRateLimiter limiter,ObjectMapper json) { this.limiter=limiter;this.json=json; }
    @Override protected boolean shouldNotFilter(HttpServletRequest r) {
        return !r.getMethod().equals("POST") || !r.getServletPath().equals("/api/auth/token");
    }
    @Override protected void doFilterInternal(HttpServletRequest r,HttpServletResponse s,FilterChain chain) throws ServletException,IOException {
        try { limiter.ip(r.getRemoteAddr()); }
        catch(LoginRateLimiter.LimitExceeded e) {
            s.setStatus(429);s.setContentType("application/json");s.setHeader("Retry-After",Long.toString(e.retryAfter()));s.setHeader("Cache-Control","no-store");
            json.writeValue(s.getOutputStream(),new ApiError(429,"LOGIN_RATE_LIMITED","Vượt giới hạn đăng nhập.",r.getRequestURI()));return;
        }
        chain.doFilter(r,s);
    }
}

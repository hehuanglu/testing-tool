package org.example.config;
import java.util.List;
import org.springframework.http.HttpMethod;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.context.annotation.*;
import org.springframework.core.annotation.Order;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.example.platform.security.*;
import org.example.common.ApiError;
import org.example.shared.api.Role;
import org.example.shared.api.AuthenticatedUser;
@Configuration
public class SecurityConfiguration {
    @Bean @Order(1) SecurityFilterChain publicAuth(HttpSecurity http,LoginRateLimiter limiter,ObjectMapper json) throws Exception {
        return http.securityMatcher("/api/auth/register","/api/auth/token")
          .csrf(csrf->csrf.disable()).sessionManagement(s->s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
          .authorizeHttpRequests(auth->auth.anyRequest().permitAll())
          .addFilterBefore(new LoginIpFilter(limiter,json),UsernamePasswordAuthenticationFilter.class).build();
    }
    @Bean @Order(2) SecurityFilterChain protectedApi(HttpSecurity http,ObjectMapper json) throws Exception {
        return http.csrf(csrf->csrf.disable()).sessionManagement(s->s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
          .authorizeHttpRequests(auth->auth.requestMatchers("/error", "/openapi.yaml","/swagger-ui.html","/swagger-ui/**", "/v3/api-docs/swagger-config", "/actuator/health", "/actuator/health/**").permitAll()
              .requestMatchers(HttpMethod.GET, "/api/foods", "/api/foods/**").permitAll()
              .requestMatchers(HttpMethod.POST, "/api/foods").hasRole("ADMIN")
              .requestMatchers(HttpMethod.PUT, "/api/foods/*").hasRole("ADMIN")
              .requestMatchers(HttpMethod.DELETE, "/api/foods/*").hasRole("ADMIN")
              .requestMatchers("/api/cart", "/api/cart/**").hasRole("CUSTOMER")
              .requestMatchers(HttpMethod.POST, "/api/orders").hasRole("CUSTOMER")
              .requestMatchers(HttpMethod.DELETE, "/api/orders/*").hasRole("CUSTOMER")
              .requestMatchers(HttpMethod.POST, "/api/orders/*/confirm").hasRole("EMPLOYEE")
              .requestMatchers(HttpMethod.PUT, "/api/orders/*/status").hasRole("EMPLOYEE")
              .requestMatchers(HttpMethod.GET, "/api/orders", "/api/orders/**").hasAnyRole("CUSTOMER", "EMPLOYEE")
              .anyRequest().authenticated())
          .oauth2ResourceServer(resource->resource.jwt(jwt->jwt.jwtAuthenticationConverter(token->{
              Role role=Role.valueOf(token.getClaimAsString("role"));
              return UsernamePasswordAuthenticationToken.authenticated(new AuthenticatedUser(token.getSubject(),role),"",
                  List.of(new SimpleGrantedAuthority("ROLE_"+role.name())));
          })).authenticationEntryPoint((r,s,e)->{
              s.setStatus(401);s.setContentType("application/json");s.setHeader("WWW-Authenticate","Bearer");s.setHeader("Cache-Control","no-store");
              json.writeValue(s.getOutputStream(),new ApiError(401,"UNAUTHENTICATED","Cần token hợp lệ.",r.getRequestURI()));
          }).accessDeniedHandler((r,s,e)->{
              s.setStatus(403);s.setContentType("application/json");s.setHeader("Cache-Control","no-store");
              json.writeValue(s.getOutputStream(),new ApiError(403,"FORBIDDEN","Không có quyền truy cập.",r.getRequestURI()));
          })).build();
    }
}

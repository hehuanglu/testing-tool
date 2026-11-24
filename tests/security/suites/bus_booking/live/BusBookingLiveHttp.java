package com.example.busbooking.api;

import com.example.busbooking.security.JwtProperties;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import tools.jackson.databind.json.JsonMapper;

import java.io.IOException;
import java.net.ProxySelector;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Clock;
import java.time.Duration;
import java.util.Map;

public final class BusBookingLiveHttp {
    private static final URI ORIGIN = URI.create("http://127.0.0.1:8085");

    private BusBookingLiveHttp() {}

    public static void main(String[] args) throws Exception {
        var client = HttpClient.newBuilder().proxy(ProxySelector.of(null)).followRedirects(HttpClient.Redirect.NEVER)
                .version(HttpClient.Version.HTTP_1_1).connectTimeout(Duration.ofSeconds(3)).build();
        awaitApplication(client);
        var database = new DriverManagerDataSource("jdbc:postgresql://127.0.0.1:5432/bus_pilot",
                "postgres", System.getenv("DB_PASSWORD"));
        var json = JsonMapper.builder().build();
        var properties = new JwtProperties();
        properties.setSecret(System.getenv("JWT_SECRET"));
        new BusBookingAuthorizationContract(new JdbcTemplate(database), json, new BCryptPasswordEncoder(10),
                properties, Clock.systemUTC()) {
            @Override
            Response call(String method, String path, Map<String, Object> body, String... headers) throws Exception {
                URI target = ORIGIN.resolve(path);
                if (!path.startsWith("/api/") || !ORIGIN.getAuthority().equals(target.getAuthority())
                        || target.getQuery() != null || target.getFragment() != null) {
                    throw new IllegalArgumentException("request outside the reviewed application origin");
                }
                var request = HttpRequest.newBuilder(target).timeout(Duration.ofSeconds(8));
                for (String header : headers) request.header("Authorization", header);
                if (body != null) request.header("Content-Type", "application/json");
                var publisher = body == null ? HttpRequest.BodyPublishers.noBody()
                        : HttpRequest.BodyPublishers.ofByteArray(json.writeValueAsBytes(body));
                var response = client.send(request.method(method, publisher).build(), HttpResponse.BodyHandlers.ofByteArray());
                boolean sessionCookie = response.headers().allValues("Set-Cookie").stream()
                        .anyMatch(value -> value.regionMatches(true, 0, "JSESSIONID=", 0, 11));
                return response(response.statusCode(), response.body(),
                        response.headers().firstValue("Content-Type").orElse(null),
                        response.headers().firstValue("WWW-Authenticate").orElse("").equals("Bearer"),
                        sessionCookie, null, path);
            }
        }.recordTheAuthorizationContract();
    }

    private static void awaitApplication(HttpClient client) throws Exception {
        var request = HttpRequest.newBuilder(ORIGIN.resolve("/api/locations")).timeout(Duration.ofSeconds(3)).GET().build();
        long deadline = System.nanoTime() + Duration.ofSeconds(45).toNanos();
        while (System.nanoTime() < deadline) {
            try {
                if (client.send(request, HttpResponse.BodyHandlers.discarding()).statusCode() == 200) return;
            } catch (IOException startup) {
                // A new container can accept connections only after application initialization.
            }
            Thread.sleep(500);
        }
        throw new IllegalStateException("application readiness check did not pass");
    }
}

package org.example.platform.security;

import java.time.Clock;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import com.nimbusds.jose.jwk.source.ImmutableJWKSet;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.RSAKey;
import org.springframework.security.oauth2.jose.jws.SignatureAlgorithm;
import org.springframework.security.oauth2.jwt.*;
import org.example.auth.dto.AccessToken;
import org.example.auth.service.TokenIssuer;
import org.example.shared.api.AuthenticatedUser;

/** RS256 cho tích hợp local với mock; chưa chốt chính sách signing production. */
public final class LocalRsaTokenIssuer implements TokenIssuer {
    public static final String ISSUER = "sa-local-dev";
    public static final String AUDIENCE = "sa-mock-api";
    private final JwtEncoder encoder;
    private final Clock clock;
    private final long ttl;
    public LocalRsaTokenIssuer(RSAKey key, Clock clock, long ttl) {
        if (!key.isPrivate() || key.size() < 2048 || ttl <= 0)
            throw new IllegalArgumentException("Cần RSA private key >=2048 bit và TTL dương");
        this.encoder = new NimbusJwtEncoder(new ImmutableJWKSet<>(new JWKSet(key)));
        this.clock = clock;
        this.ttl = ttl;
    }
    @Override public AccessToken issue(AuthenticatedUser user) {
        Instant now = clock.instant().truncatedTo(ChronoUnit.SECONDS);
        Instant expiry = now.plusSeconds(ttl);
        var claims = JwtClaimsSet.builder().issuer(ISSUER).audience(List.of(AUDIENCE))
                .subject(user.userId()).claim("role", user.role().name())
                .issuedAt(now).expiresAt(expiry).build();
        String token = encoder.encode(JwtEncoderParameters.from(
                JwsHeader.with(SignatureAlgorithm.RS256).build(), claims)).getTokenValue();
        return new AccessToken(token, ttl, expiry);
    }
}

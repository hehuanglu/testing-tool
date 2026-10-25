package org.example.platform.config;
import java.nio.file.*;
import java.security.*;
import java.security.interfaces.*;
import java.security.spec.*;
import java.time.Clock;
import java.util.Base64;
import com.nimbusds.jose.jwk.RSAKey;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.*;
import org.springframework.security.oauth2.jwt.*;
import org.springframework.security.oauth2.core.*;
import org.springframework.security.oauth2.jose.jws.SignatureAlgorithm;
import org.example.auth.dto.*;
import org.example.auth.repository.AccountRepository;
import org.example.auth.service.*;
import org.example.platform.security.*;
@Configuration
public class AdapterConfiguration {
    @Bean Clock clock() { return Clock.systemUTC(); }
    @Bean PasswordHasher passwordHasher() { return new BCryptPasswordHasher(); }
    @Bean RSAKey rsaKey(@Value("${auth.private-key-file}") String privateFile,@Value("${auth.public-key-file}") String publicFile) throws Exception {
        var factory=KeyFactory.getInstance("RSA");
        var pub=(RSAPublicKey)factory.generatePublic(new X509EncodedKeySpec(pem(publicFile)));
        var priv=(RSAPrivateKey)factory.generatePrivate(new PKCS8EncodedKeySpec(pem(privateFile)));
        if(!pub.getModulus().equals(priv.getModulus())) throw new IllegalArgumentException("Cặp khóa RSA không khớp");
        return new RSAKey.Builder(pub).privateKey(priv).build();
    }
    private static byte[] pem(String file) throws Exception {
        return Base64.getDecoder().decode(Files.readString(Path.of(file)).replaceAll("-----[^\\n]+-----","").replaceAll("\\s",""));
    }
    @Bean TokenIssuer tokenIssuer(RSAKey key,Clock clock,@Value("${auth.ttl-seconds}") long ttl) {
        return new LocalRsaTokenIssuer(key,clock,ttl);
    }
    @Bean JwtDecoder jwtDecoder(RSAKey key,Clock clock) throws Exception {
        var decoder=NimbusJwtDecoder.withPublicKey(key.toRSAPublicKey()).signatureAlgorithm(SignatureAlgorithm.RS256).build();
        decoder.setJwtValidator(jwt->{
            try {
                var issued=jwt.getIssuedAt();var expiry=jwt.getExpiresAt();var now=clock.instant();
                if(issued==null || expiry==null || issued.isAfter(now) || !expiry.isAfter(issued) || !now.isBefore(expiry)
                   || jwt.getSubject()==null || jwt.getSubject().isBlank()
                   || !LocalRsaTokenIssuer.ISSUER.equals(jwt.getClaimAsString("iss"))
                   || !jwt.getAudience().contains(LocalRsaTokenIssuer.AUDIENCE)
                   || (jwt.getNotBefore()!=null && now.isBefore(jwt.getNotBefore()))) throw new IllegalArgumentException();
                org.example.shared.api.Role.valueOf(jwt.getClaimAsString("role"));
                return OAuth2TokenValidatorResult.success();
            } catch(RuntimeException e) { return OAuth2TokenValidatorResult.failure(new OAuth2Error("invalid_token","JWT không hợp lệ",null)); }
        });return decoder;
    }
    @Bean LoginRateLimiter loginRateLimiter(Clock clock,@Value("${auth.login.email-limit}") int email,
         @Value("${auth.login.ip-limit}") int ip,@Value("${auth.login.window-seconds}") long window) {
        return new LoginRateLimiter(clock,email,ip,window);
    }
}

package mcp.server.zap.core.gateway;

import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.MessageDigest;
import java.security.interfaces.RSAPublicKey;
import java.security.spec.X509EncodedKeySpec;
import java.time.Instant;
import java.util.Base64;
import java.util.HexFormat;
import java.util.regex.Pattern;
import org.springframework.security.oauth2.jose.jws.SignatureAlgorithm;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;

/** Explicit research identity: a verified wire JWT plus an independently protected probe. */
public record SignedJwtIdentity(String publicKeyFile, String publicKeySha256, String issuer,
        String audience, String roleClaim, String expectedRole, int expectedStatus,
        String responsePointer, String responseValue) {
    public SignedJwtIdentity {
        for (String value : new String[]{publicKeyFile, publicKeySha256, issuer, audience,
                roleClaim, expectedRole, responsePointer, responseValue}) {
            if (value == null || value.isBlank()) throw new IllegalArgumentException("Signed JWT identity field missing");
        }
        if (!publicKeySha256.matches("[0-9a-f]{64}") || !Path.of(publicKeyFile).isAbsolute()
                || !roleClaim.matches("[A-Za-z_][A-Za-z0-9_-]{0,127}")
                || !responsePointer.startsWith("/") || responsePointer.equals("/")
                || (expectedStatus != 200 && expectedStatus != 403)) {
            throw new IllegalArgumentException("Unsupported signed JWT identity contract");
        }
    }

    public boolean matches(String requestHeaders, String responseHeaders, String responseBody,
            String verificationUrl, String expectedSubject) {
        try {
            if (requestHeaders == null || responseHeaders == null || responseBody == null || expectedSubject == null) return false;
            String[] first = requestHeaders.split("\\r?\\n", 2)[0].split(" ");
            URI expected = URI.create(verificationUrl);
            if (first.length != 3 || !first[0].equals("GET") || !URI.create(first[1]).equals(expected)) return false;
            if (!responseHeaders.matches("(?s)^HTTP/\\S+ " + expectedStatus + "(?: [^\\r\\n]*)?\\r?\\n.*")
                    || !Pattern.compile("(?im)^Content-Type: application/json(?:[;\\r\\n]|$)").matcher(responseHeaders).find()) return false;
            var auth = Pattern.compile("(?im)^Authorization: Bearer ([A-Za-z0-9_.-]+)\\r?$").matcher(requestHeaders);
            var headers = Pattern.compile("(?im)^Authorization:").matcher(requestHeaders);
            if (!headers.find() || headers.find()) return false;
            if (!auth.find()) return false;
            String token = auth.group(1);
            if (auth.find()) return false;
            Path path = Path.of(publicKeyFile);
            if (Files.isSymbolicLink(path)) return false;
            byte[] pem = Files.readAllBytes(path);
            if (!HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(pem)).equals(publicKeySha256)) return false;
            String encoded = new String(pem, java.nio.charset.StandardCharsets.US_ASCII)
                    .replace("-----BEGIN PUBLIC KEY-----", "").replace("-----END PUBLIC KEY-----", "").replaceAll("\\s", "");
            var key = (RSAPublicKey) KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(Base64.getDecoder().decode(encoded)));
            if (key.getModulus().bitLength() < 2048) return false;
            var decoder = NimbusJwtDecoder.withPublicKey(key).signatureAlgorithm(SignatureAlgorithm.RS256).build();
            // Enforce exact source contract, without the decoder's default clock-skew allowance.
            decoder.setJwtValidator(jwt -> org.springframework.security.oauth2.core.OAuth2TokenValidatorResult.success());
            var jwt = decoder.decode(token);Instant now = Instant.now();
            if (!issuer.equals(jwt.getClaimAsString("iss")) || !jwt.getAudience().contains(audience)
                    || !expectedSubject.equals(jwt.getSubject()) || !expectedRole.equals(jwt.getClaimAsString(roleClaim))
                    || jwt.getIssuedAt() == null || jwt.getExpiresAt() == null || jwt.getIssuedAt().isAfter(now)
                    || !jwt.getExpiresAt().isAfter(jwt.getIssuedAt()) || !now.isBefore(jwt.getExpiresAt())
                    || (jwt.getNotBefore() != null && now.isBefore(jwt.getNotBefore()))) return false;
            var node = new tools.jackson.databind.ObjectMapper().readTree(responseBody).at(responsePointer);
            return node.isValueNode() && !node.isNull() && responseValue.equals(node.asText());
        } catch (Exception failure) {
            return false; // No token, claim or parser diagnostics escape this identity boundary.
        }
    }
}

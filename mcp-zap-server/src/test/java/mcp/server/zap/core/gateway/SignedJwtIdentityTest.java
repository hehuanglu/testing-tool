package mcp.server.zap.core.gateway;

import static org.junit.jupiter.api.Assertions.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.MessageDigest;
import java.security.Signature;
import java.time.Instant;
import java.util.Base64;
import java.util.HexFormat;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class SignedJwtIdentityTest {
    @TempDir Path directory;
    KeyPair pair;Path publicKey;SignedJwtIdentity identity;
    final String url="http://owned:18080/access";
    @BeforeEach void setup() throws Exception {
        var generator=KeyPairGenerator.getInstance("RSA");generator.initialize(2048);pair=generator.generateKeyPair();
        publicKey=directory.resolve("public.pem");
        Files.writeString(publicKey,"-----BEGIN PUBLIC KEY-----\n"+Base64.getMimeEncoder(64,new byte[]{10}).encodeToString(pair.getPublic().getEncoded())+"\n-----END PUBLIC KEY-----\n");
        identity=spec(200,"/meta/state","present");
    }
    SignedJwtIdentity spec(int status,String pointer,String value) throws Exception {
        return new SignedJwtIdentity(publicKey.toString(),HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(publicKey))),
                "owned-issuer","owned-api","tier","CURATOR",status,pointer,value);
    }
    String claims(String subject,String role,long issued,long expires) {
        return "{\"iss\":\"owned-issuer\",\"aud\":[\"owned-api\"],\"sub\":\""+subject+"\",\"tier\":\""+role+"\",\"iat\":"+issued+",\"exp\":"+expires+"}";
    }
    String token(KeyPair key,String claims,String algorithm) throws Exception {
        var encoder=Base64.getUrlEncoder().withoutPadding();
        String data=encoder.encodeToString(("{\"alg\":\""+algorithm+"\"}").getBytes(StandardCharsets.UTF_8))+"."+encoder.encodeToString(claims.getBytes(StandardCharsets.UTF_8));
        var signer=Signature.getInstance("SHA256withRSA");signer.initSign(key.getPrivate());signer.update(data.getBytes(StandardCharsets.US_ASCII));
        return data+"."+encoder.encodeToString(signer.sign());
    }
    String request(String token) {return "GET "+url+" HTTP/1.1\r\nHost: owned:18080\r\nAuthorization: Bearer "+token+"\r\n\r\n";}
    String response(int status) {return "HTTP/1.1 "+status+"\r\nContent-Type: application/json\r\n\r\n";}
    @Test void requiresSignedWireIdentityAndProtectedEvidence() throws Exception {
        long now=Instant.now().getEpochSecond();String c=claims("member-42","CURATOR",now-1,now+300);String jwt=token(pair,c,"RS256");
        assertTrue(identity.matches(request(jwt),response(200),"{\"meta\":{\"state\":\"present\"}}",url,"member-42"));
        assertFalse(identity.matches(request(jwt),response(200),"{}",url,"member-42"));
        assertFalse(identity.matches(request(jwt),response(401),"{\"meta\":{\"state\":\"present\"}}",url,"member-42"));
        assertFalse(identity.matches(request(jwt),response(200),"{\"meta\":{\"state\":\"present\"}}",url,"member-43"));
        assertFalse(identity.matches(request(jwt).replace(url,"http://other/access"),response(200),"{\"meta\":{\"state\":\"present\"}}",url,"member-42"));
        var generator=KeyPairGenerator.getInstance("RSA");generator.initialize(2048);
        for (String bad : new String[]{token(generator.generateKeyPair(),c,"RS256"),token(pair,c,"none"),token(pair,c.replace("owned-issuer","other"),"RS256"),
                token(pair,c.replace("owned-api","other"),"RS256"),token(pair,claims("member-42","READER",now-1,now+300),"RS256"),
                token(pair,claims("member-42","CURATOR",now-300,now-1),"RS256"),token(pair,claims("member-42","CURATOR",now+20,now+300),"RS256")}) {
            assertFalse(identity.matches(request(bad),response(200),"{\"meta\":{\"state\":\"present\"}}",url,"member-42"));
        }
        Files.writeString(publicKey,"changed");assertFalse(identity.matches(request(jwt),response(200),"{\"meta\":{\"state\":\"present\"}}",url,"member-42"));
    }
    @Test void authenticatedDenialRequiresExactSignedPrincipalAndApplicationMarker() throws Exception {
        long now=Instant.now().getEpochSecond();String jwt=token(pair,claims("member-42","CURATOR",now-1,now+300),"RS256");
        var denied=spec(403,"/problem/key","role-denied");
        assertTrue(denied.matches(request(jwt),response(403),"{\"problem\":{\"key\":\"role-denied\"}}",url,"member-42"));
        assertFalse(denied.matches(request(jwt),response(200),"{\"problem\":{\"key\":\"role-denied\"}}",url,"member-42"));
        assertFalse(denied.matches("GET "+url+" HTTP/1.1\r\n",response(403),"{\"problem\":{\"key\":\"role-denied\"}}",url,"member-42"));
        assertFalse(denied.matches(request(jwt),response(403),"{\"problem\":{\"key\":\"other\"}}",url,"member-42"));
    }
}

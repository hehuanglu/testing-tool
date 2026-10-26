// Synthetic placeholder, never a usable credential.
function literalConfig() {
  // ruleid: nestjs-auth-hardcoded-jwt-secret
  return {secret: "synthetic-not-a-real-key"};
}
function externalConfig(config: any) {
  // ok: nestjs-auth-hardcoded-jwt-secret
  return {secret: config.getOrThrow("JWT_SIGNING_KEY")};
}
function fallbackOr(config: any) {
  // ruleid: nestjs-auth-hardcoded-jwt-secret
  return {secret: config.value || "synthetic-fallback-or"};
}
function fallbackNullish(config: any) {
  // ruleid: nestjs-auth-hardcoded-jwt-secret
  return {secretOrKey: config.value ?? "synthetic-fallback-nullish"};
}
function externalMember(config: any) {
  // ok: nestjs-auth-hardcoded-jwt-secret
  return {secret: config.jwtSecret};
}
function unrelatedLiteral() {
  // ok: nestjs-auth-hardcoded-jwt-secret
  return {name: "synthetic-public-name"};
}

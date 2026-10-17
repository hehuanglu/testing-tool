import { registerAs } from '@nestjs/config';

export default registerAs('app', () => ({
  nodeEnv: process.env.NODE_ENV ?? 'development',
  port: Number.parseInt(process.env.PORT ?? '3000', 10),
  corsOrigins: (process.env.CORS_ORIGINS ?? 'http://localhost:5173').split(',').map((origin) => origin.trim()).filter(Boolean),
  jwt: {
    secret: process.env.JWT_SECRET,
    expiresInSeconds: Number.parseInt(process.env.JWT_EXPIRES_IN_SECONDS ?? '3600', 10),
    issuer: process.env.JWT_ISSUER ?? 'security-vibe-coding',
    audience: process.env.JWT_AUDIENCE ?? 'security-vibe-coding-web',
  },
  authentication: {
    bcryptCost: Number.parseInt(process.env.BCRYPT_COST ?? '12', 10),
    maxAttempts: Number.parseInt(process.env.LOGIN_MAX_ATTEMPTS ?? '5', 10),
    attemptWindowSeconds: Number.parseInt(process.env.LOGIN_ATTEMPT_WINDOW_SECONDS ?? '900', 10),
    lockoutSeconds: Number.parseInt(process.env.LOGIN_LOCKOUT_SECONDS ?? '900', 10),
  },
  accountNumberProtection: {
    encryptionKeyBase64: process.env.ACCOUNT_NUMBER_ENCRYPTION_KEY_BASE64,
    hmacKeyBase64: process.env.ACCOUNT_NUMBER_HMAC_KEY_BASE64,
    keyVersion: Number.parseInt(process.env.ACCOUNT_NUMBER_KEY_VERSION ?? '1', 10),
  },
}));

interface Environment {
  NODE_ENV?: string;
  PORT?: string;
  CORS_ORIGINS?: string;
  DB_HOST?: string;
  DB_PORT?: string;
  DB_USERNAME?: string;
  DB_PASSWORD?: string;
  DB_DATABASE?: string;
  JWT_SECRET?: string;
  [key: string]: string | undefined;
}

const required = ['DB_HOST', 'DB_USERNAME', 'DB_PASSWORD', 'DB_DATABASE', 'JWT_SECRET'] as const;

const integerSettings = [
  ['PORT', '3000', 1, 65_535],
  ['DB_PORT', '3306', 1, 65_535],
  ['JWT_EXPIRES_IN_SECONDS', '3600', 300, 86_400],
  ['BCRYPT_COST', '12', 10, 14],
  ['LOGIN_MAX_ATTEMPTS', '5', 1, 20],
  ['LOGIN_ATTEMPT_WINDOW_SECONDS', '900', 60, 86_400],
  ['LOGIN_LOCKOUT_SECONDS', '900', 60, 86_400],
  ['ACCOUNT_NUMBER_KEY_VERSION', '1', 1, 65_535],
] as const;

function requireBase64Key(environment: Environment, name: string): void {
  const encoded = environment[name]?.trim();
  if (!encoded || !/^[A-Za-z0-9+/]{43}=$/.test(encoded) || Buffer.from(encoded, 'base64').length !== 32) {
    throw new Error(`${name} must be a base64-encoded 32-byte key`);
  }
}

export function validateEnvironment(environment: Environment): Environment {
  const missing = required.filter((key) => !environment[key]?.trim());
  if (missing.length > 0) throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
  const nodeEnv = environment.NODE_ENV ?? 'development';
  if (nodeEnv !== 'development') throw new Error('NODE_ENV must be development for this research runtime');
  for (const [name, fallback, minimum, maximum] of integerSettings) {
    const value = environment[name] ?? fallback;
    const port = Number(value);
    if (!Number.isInteger(port) || port < minimum || port > maximum) throw new Error(`${name} is outside the allowed range`);
  }
  const secret = environment.JWT_SECRET;
  if (!secret || secret.length < 32 || secret.startsWith('replace-') || secret.startsWith('change-')) {
    throw new Error('JWT_SECRET must be a strong external secret');
  }
  requireBase64Key(environment, 'ACCOUNT_NUMBER_ENCRYPTION_KEY_BASE64');
  requireBase64Key(environment, 'ACCOUNT_NUMBER_HMAC_KEY_BASE64');
  if (environment.ACCOUNT_NUMBER_ENCRYPTION_KEY_BASE64 === environment.ACCOUNT_NUMBER_HMAC_KEY_BASE64) {
    throw new Error('Account-number encryption and HMAC keys must be different');
  }
  const origins = environment.CORS_ORIGINS?.split(',').map((value) => value.trim()) ?? [];
  if (origins.length === 0 || origins.includes('*')) throw new Error('CORS_ORIGINS must contain explicit trusted origins');
  for (const name of ['JWT_ISSUER', 'JWT_AUDIENCE']) {
    const value = environment[name];
    if (value !== undefined && !/^[A-Za-z0-9._:-]{3,128}$/.test(value)) throw new Error(`${name} has an invalid format`);
  }
  return environment;
}

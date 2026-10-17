import { createCipheriv, createHmac, randomBytes } from 'node:crypto';
import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

export interface ProtectedAccountNumber {
  readonly ciphertext: Buffer;
  readonly iv: Buffer;
  readonly authTag: Buffer;
  readonly keyVersion: number;
  readonly lookupHash: Buffer;
  readonly last4: string;
}

@Injectable()
export class AccountNumberCryptoService {
  constructor(private readonly config: ConfigService) {}

  protect(accountNumber: string): ProtectedAccountNumber {
    const encryptionKey = Buffer.from(this.config.getOrThrow<string>('app.accountNumberProtection.encryptionKeyBase64'), 'base64');
    const hmacKey = Buffer.from(this.config.getOrThrow<string>('app.accountNumberProtection.hmacKeyBase64'), 'base64');
    const plaintext = Buffer.from(accountNumber, 'ascii');
    try {
      const iv = randomBytes(12);
      const cipher = createCipheriv('aes-256-gcm', encryptionKey, iv);
      const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
      return {
        ciphertext,
        iv,
        authTag: cipher.getAuthTag(),
        keyVersion: this.config.getOrThrow<number>('app.accountNumberProtection.keyVersion'),
        lookupHash: createHmac('sha256', hmacKey).update(plaintext).digest(),
        last4: accountNumber.slice(-4),
      };
    } finally {
      plaintext.fill(0);
      encryptionKey.fill(0);
      hmacKey.fill(0);
    }
  }
}

import { Logger } from '@nestjs/common';
function logValues(logger, user, redact, audit) {
  // Fixed text remains an inventory candidate, not evidence of a credential value.
  // ruleid: nestjs-public-sensitive-logger-usage
  logger.warn('Password confirmation did not match');
  // ruleid: nestjs-public-sensitive-logger-usage
  logger.warn(user.password);
  // ruleid: nestjs-public-sensitive-logger-usage
  logger.warn(`Password=${user.password}`);
  const alias = user.password;
  // ok: nestjs-public-sensitive-logger-usage
  logger.warn(alias); // Naming detector cannot establish alias content.
  // ruleid: nestjs-public-sensitive-logger-usage
  logger.warn(redact(user.password)); // Function name is no proof of redaction.
  // ok: nestjs-public-sensitive-logger-usage
  audit.write(user.password); // Wrapper needs caller/implementation review.
  // Synthetic placeholder only; do not exclude all literal arguments.
  // ruleid: nestjs-public-sensitive-logger-usage
  logger.warn('credential=SYNTHETIC_PLACEHOLDER');
}
class Logging {
  private logger = new Logger('Synthetic');
  emit(user, redact) {
    // ruleid: nestjs-public-sensitive-logger-usage, nestjs-public-nest-logger-sensitive-argument
    this.logger.warn('Password confirmation did not match');
    // ruleid: nestjs-public-sensitive-logger-usage, nestjs-public-nest-logger-sensitive-argument
    this.logger.warn(user.password);
    // ruleid: nestjs-public-sensitive-logger-usage, nestjs-public-nest-logger-sensitive-argument
    this.logger.warn(`Password=${user.password}`);
    const alias = user.password;
    // ok: nestjs-public-sensitive-logger-usage, nestjs-public-nest-logger-sensitive-argument
    this.logger.warn(alias);
    // ruleid: nestjs-public-sensitive-logger-usage, nestjs-public-nest-logger-sensitive-argument
    this.logger.warn(redact(user.password));
  }
}

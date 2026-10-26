import { Controller, Get } from '@nestjs/common';
function configFactory(config) {
  // ruleid: nestjs-auth-password-field-in-response
  return { password: config.get('DB_PASSWORD') };
}
function dbOptions(config) {
  // ruleid: nestjs-auth-password-field-in-response
  return { host: 'db', password: config.password };
}
function helper(user) {
  // ruleid: nestjs-auth-password-field-in-response
  return { passwordHash: user.passwordHash };
}
@Controller()
class Api {
  @Get('direct') direct(user) {
    // ruleid: nestjs-auth-password-field-in-response
    return { passwordHash: user.passwordHash };
  }
  @Get('indirect') indirect(user) {
    // ok: nestjs-auth-password-field-in-response
    return helper(user); // Broad return rule does not follow caller across functions.
  }
  @Get('safe') safe(user) {
    // ok: nestjs-auth-password-field-in-response
    return { id: user.id, label: user.label };
  }
}

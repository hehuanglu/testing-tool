import { MinLength } from 'class-validator';
class RegisterDto {
  // ruleid: nestjs-auth-password-min-length-under-eight
  @MinLength(4)
  password: string;
}
class LoginDto {
  // ruleid: nestjs-auth-password-min-length-under-eight
  @MinLength(4)
  password: string;
}
class ChangeDto {
  // ruleid: nestjs-auth-password-min-length-under-eight
  @MinLength(6)
  password: string;
}
class ResetDto {
  // ruleid: nestjs-auth-password-min-length-under-eight
  @MinLength(7)
  passphrase: string;
}
class SharedDto {
  // ruleid: nestjs-auth-password-min-length-under-eight
  @MinLength(1)
  password: string; // Trace both enrollment and verification consumers.
}
class DifferentValidatorDto {
  // ok: nestjs-auth-password-min-length-under-eight
  @MinLength(12)
  password: string;
}
class AlternativeControlDto {
  // ruleid: nestjs-auth-password-min-length-under-eight
  @MinLength(4)
  @ReviewedEnrollmentPolicy()
  password: string; // Inventory still matches; read actual validator implementation.
}
class LabelDto {
  // ok: nestjs-auth-password-min-length-under-eight
  @MinLength(2)
  label: string;
}

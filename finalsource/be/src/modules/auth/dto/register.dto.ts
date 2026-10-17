import { ApiProperty } from '@nestjs/swagger';
import { IsEmail, IsString, Matches, MaxLength, MinLength } from 'class-validator';

export class RegisterDto {
  @ApiProperty({ example: 'Nguyen Van A', minLength: 1, maxLength: 120 })
  @IsString()
  @MinLength(1)
  @MaxLength(120)
  @Matches(/\S/, { message: 'Full name is required.' })
  declare readonly fullName: string;

  @ApiProperty({ example: 'example@email.com', maxLength: 254 })
  @IsEmail()
  @MaxLength(254)
  declare readonly email: string;

  @ApiProperty({ format: 'password', writeOnly: true, minLength: 1, maxLength: 72 })
  @IsString()
  @MinLength(1)
  @MaxLength(72)
  declare readonly password: string;

  @ApiProperty({ format: 'password', writeOnly: true, minLength: 1, maxLength: 72 })
  @IsString()
  @MinLength(1)
  @MaxLength(72)
  declare readonly 'confirm Password': string;
}

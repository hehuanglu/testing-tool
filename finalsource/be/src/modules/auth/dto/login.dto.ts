import { ApiProperty } from '@nestjs/swagger';
import { IsEmail, IsString, MaxLength, MinLength } from 'class-validator';

export class LoginDto {
  @ApiProperty({ example: 'johndoe@email.com', maxLength: 254 })
  @IsEmail()
  @MaxLength(254)
  declare readonly email: string;

  @ApiProperty({ format: 'password', writeOnly: true, minLength: 1, maxLength: 72 })
  @IsString()
  @MinLength(1)
  @MaxLength(72)
  declare readonly password: string;
}

import { ApiProperty } from '@nestjs/swagger';
import { AuthenticatedUserDto } from './login-response.dto';

export class RegisterResponseDto {
  @ApiProperty({ description: 'Short-lived JWT access token' })
  declare token: string;

  @ApiProperty({ type: AuthenticatedUserDto })
  declare user: AuthenticatedUserDto;
}

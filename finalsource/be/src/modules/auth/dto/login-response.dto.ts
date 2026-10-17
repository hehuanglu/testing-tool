import { ApiProperty } from '@nestjs/swagger';

export class AuthenticatedUserDto {
  @ApiProperty({ example: 1 })
  declare id: number;

  @ApiProperty({ example: 'John Doe' })
  declare fullName: string;

  @ApiProperty({ example: 'johndoe@email.com' })
  declare email: string;
}

export class LoginResponseDto {
  @ApiProperty({ description: 'Short-lived JWT access token' })
  declare accessToken: string;

  @ApiProperty({ type: AuthenticatedUserDto })
  declare user: AuthenticatedUserDto;
}

import { ApiProperty } from '@nestjs/swagger';

export class CreatedAccountDto {
  @ApiProperty() declare id: number;
  @ApiProperty() declare user_id: number;
  @ApiProperty() declare bank_name: string;
  @ApiProperty() declare account_type: string;
  @ApiProperty() declare branch_name: string;
  @ApiProperty({ minLength: 4, maxLength: 4 }) declare account_number_last_4: string;
  @ApiProperty() declare balance: number;
}

export class CreateAccountResponseDto {
  @ApiProperty({ type: CreatedAccountDto }) declare account: CreatedAccountDto;
}

export class CreateAccountEnvelopeDto {
  @ApiProperty({ enum: [true] }) declare success: true;
  @ApiProperty({ example: 'Account created successfully' }) declare message: string;
  @ApiProperty({ type: CreateAccountResponseDto }) declare data: CreateAccountResponseDto;
}

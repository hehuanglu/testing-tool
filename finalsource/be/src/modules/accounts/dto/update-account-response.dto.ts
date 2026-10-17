import { ApiProperty } from '@nestjs/swagger';

export class UpdatedAccountDto {
  @ApiProperty() declare account_id: number;
  @ApiProperty() declare user_id: number;
  @ApiProperty() declare bank_name: string;
  @ApiProperty() declare account_type: string;
  @ApiProperty() declare branch_name: string;
  @ApiProperty({ minLength: 4, maxLength: 4 }) declare account_number_last_4: string;
  @ApiProperty() declare balance: number;
  @ApiProperty({ format: 'date-time' }) declare updated_at: string;
}

export class UpdateAccountResponseDto {
  @ApiProperty({ type: UpdatedAccountDto }) declare account: UpdatedAccountDto;
}

export class UpdateAccountEnvelopeDto {
  @ApiProperty({ enum: [true] }) declare success: true;
  @ApiProperty({ example: 'Account updated successfully' }) declare message: string;
  @ApiProperty({ type: UpdateAccountResponseDto }) declare data: UpdateAccountResponseDto;
}

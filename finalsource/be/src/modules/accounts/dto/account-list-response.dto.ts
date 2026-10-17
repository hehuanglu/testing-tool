import { ApiProperty } from '@nestjs/swagger';

export class AccountResponseDto {
  @ApiProperty() declare id: number;
  @ApiProperty() declare bank_name: string;
  @ApiProperty() declare account_type: string;
  @ApiProperty() declare branch_name: string;
  @ApiProperty({ minLength: 4, maxLength: 4 }) declare account_number_last_4: string;
  @ApiProperty() declare balance: number;
}

export class AccountListResponseDto {
  @ApiProperty() declare user_id: number;
  @ApiProperty({ type: [AccountResponseDto] }) declare accounts: AccountResponseDto[];
}

export class AccountListEnvelopeDto {
  @ApiProperty({ enum: [true] }) declare success: true;
  @ApiProperty() declare message: string;
  @ApiProperty({ type: AccountListResponseDto }) declare data: AccountListResponseDto;
}

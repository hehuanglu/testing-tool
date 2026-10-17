import { ApiProperty } from '@nestjs/swagger';

export class DeleteAccountResponseDto {
  @ApiProperty({ example: 1 }) declare deleted_account_id: number;
}

export class DeleteAccountEnvelopeDto {
  @ApiProperty({ enum: [true] }) declare success: true;
  @ApiProperty({ example: 'Account deleted successfully' }) declare message: string;
  @ApiProperty({ type: DeleteAccountResponseDto }) declare data: DeleteAccountResponseDto;
}

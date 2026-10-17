import { ApiProperty } from '@nestjs/swagger';

export class BillResponseDto {
  @ApiProperty() declare billId: number;
  @ApiProperty() declare userId: number;
  @ApiProperty() declare itemDescription: string;
  @ApiProperty() declare logoUrl: string;
  @ApiProperty({ format: 'date' }) declare dueDate: string;
  @ApiProperty({ format: 'date' }) declare lastChargeDate: string;
  @ApiProperty() declare Amount: number;
}

export class BillsPayloadDto {
  @ApiProperty({ type: [BillResponseDto] }) declare data: BillResponseDto[];
}

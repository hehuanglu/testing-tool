import { ApiProperty } from '@nestjs/swagger';

export class MonthlySavingsDto {
  @ApiProperty({ example: '01', pattern: '^(0[1-9]|1[0-2])$' })
  declare month: string;

  @ApiProperty({ example: 1500000, description: 'Net savings: total Revenue minus total Expense' })
  declare amount: number;
}

export class SavingsSeriesDto {
  @ApiProperty({ type: [MonthlySavingsDto] })
  declare this_year: MonthlySavingsDto[];

  @ApiProperty({ type: [MonthlySavingsDto] })
  declare last_year: MonthlySavingsDto[];
}

export class SavingsSummaryResponseDto {
  @ApiProperty({ example: 1 })
  declare user_id: number;

  @ApiProperty({ example: 2025 })
  declare year: number;

  @ApiProperty({ type: SavingsSeriesDto })
  declare summary: SavingsSeriesDto;
}

import { ApiProperty } from '@nestjs/swagger';

export class MonthlyExpenseDto {
  @ApiProperty({ example: 'Jan', enum: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] })
  declare month: string;

  @ApiProperty({ example: 1250 })
  declare totalExpense: number;
}

export class ExpenseSummaryResponseDto {
  @ApiProperty({ type: [MonthlyExpenseDto] })
  declare data: MonthlyExpenseDto[];
}

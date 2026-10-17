import { ApiProperty } from '@nestjs/swagger';

export class ExpenseBreakdownItemDto {
  @ApiProperty({ name: 'item_description', example: 'House Rent' })
  declare item_description: string;

  @ApiProperty({ example: 230 })
  declare amount: number;

  @ApiProperty({ example: '2025-05-17', pattern: '^\\d{4}-\\d{2}-\\d{2}$' })
  declare date: string;
}

export class ExpenseBreakdownCategoryDto {
  @ApiProperty({ example: 'Housing' })
  declare category: string;

  @ApiProperty({ name: 'Total', example: 250 })
  declare Total: number;

  @ApiProperty({ example: 15 })
  declare changePercent: number;

  @ApiProperty({ type: [ExpenseBreakdownItemDto] })
  declare subCategories: ExpenseBreakdownItemDto[];
}

export class ExpenseBreakdownResponseDto {
  @ApiProperty({ type: [ExpenseBreakdownCategoryDto] })
  declare data: ExpenseBreakdownCategoryDto[];
}

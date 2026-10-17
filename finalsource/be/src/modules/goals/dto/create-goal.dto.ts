import { Transform, Type, type TransformFnParams } from 'class-transformer';
import { IsDateString, IsDecimal, IsIn, IsInt, IsOptional, Matches, Min } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import type { GoalType } from '../entities/goal.entity';

function normalizeDecimalInput({ value }: TransformFnParams): unknown {
  return typeof value === 'number' || typeof value === 'string' ? String(value) : value;
}

export class CreateGoalDto {
  @ApiProperty({ name: 'goal_type', enum: ['Saving', 'Expense'], example: 'Saving' })
  @IsIn(['Saving', 'Expense'])
  declare readonly goal_type: GoalType;

  @ApiPropertyOptional({ name: 'category_id', nullable: true, example: null })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  declare readonly category_id?: number | null;

  @ApiProperty({ name: 'target_amount', example: 80000000, type: Number })
  @Transform(normalizeDecimalInput)
  @IsDecimal({ decimal_digits: '0,4', force_decimal: false })
  @Matches(/^(?!0+(?:\.0+)?$)(?:0|[1-9]\d{0,14})(?:\.\d{1,4})?$/)
  declare readonly target_amount: string;

  @ApiProperty({ name: 'start_date', example: '2025-05-01' })
  @Matches(/^\d{4}-\d{2}-\d{2}$/)
  @IsDateString({ strict: true })
  declare readonly start_date: string;

  @ApiProperty({ name: 'end_date', example: '2025-12-31' })
  @Matches(/^\d{4}-\d{2}-\d{2}$/)
  @IsDateString({ strict: true })
  declare readonly end_date: string;
}

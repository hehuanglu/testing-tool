import { ApiProperty } from '@nestjs/swagger';
import { Transform, type TransformFnParams } from 'class-transformer';
import { IsDecimal, Matches } from 'class-validator';

function normalizeDecimalInput({ value }: TransformFnParams): unknown {
  return typeof value === 'number' || typeof value === 'string' ? String(value) : value;
}

export class UpdateGoalDto {
  @ApiProperty({ name: 'target_amount', example: 70000000, type: Number })
  @Transform(normalizeDecimalInput)
  @IsDecimal({ decimal_digits: '0,4', force_decimal: false }, { message: 'target_amount must be a positive number' })
  @Matches(/^(?!0+(?:\.0+)?$)(?:0|[1-9]\d{0,11})(?:\.\d{1,4})?$/, { message: 'target_amount must be a positive number' })
  declare readonly target_amount: string;
}

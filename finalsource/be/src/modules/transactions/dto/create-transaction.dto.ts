import { Transform, Type, type TransformFnParams } from 'class-transformer';
import { IsDateString, IsDecimal, IsIn, IsInt, IsNotEmpty, IsString, Matches, MaxLength, Min } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';
import type { TransactionType } from '../entities/transaction.entity';

function normalizeDecimalInput({ value }: TransformFnParams): unknown {
  return typeof value === 'number' || typeof value === 'string' ? String(value) : value;
}

export class CreateTransactionDto {
  @ApiProperty({ example: 3 })
  @Type(() => Number)
  @IsInt()
  @Min(1)
  declare readonly accountId: number;

  @ApiProperty({ example: '2023-05-17T00:00:00Z' })
  @IsDateString({ strict: true })
  declare readonly transactionDate: string;

  @ApiProperty({ enum: ['Revenue', 'Expense'], example: 'Expense' })
  @IsIn(['Revenue', 'Expense'])
  declare readonly type: TransactionType;

  @ApiProperty({ example: 'Movie Ticket', maxLength: 255 })
  @IsString()
  @IsNotEmpty()
  @MaxLength(255)
  declare readonly itemDescription: string;

  @ApiProperty({ name: 'category_id', example: 3 })
  @Type(() => Number)
  @IsInt()
  @Min(1)
  declare readonly category_id: number;

  @ApiProperty({ example: 'Inox', maxLength: 160 })
  @IsString()
  @IsNotEmpty()
  @MaxLength(160)
  declare readonly shopName: string;

  @ApiProperty({ example: 150000, type: Number })
  @Transform(normalizeDecimalInput)
  @IsDecimal({ decimal_digits: '0,4', force_decimal: false })
  @Matches(/^(?!0+(?:\.0+)?$)(?:0|[1-9]\d{0,14})(?:\.\d{1,4})?$/)
  declare readonly amount: string;

  @ApiProperty({ example: 'Credit Card', maxLength: 64 })
  @IsString()
  @IsNotEmpty()
  @MaxLength(64)
  declare readonly paymentMethod: string;

  @ApiProperty({ example: 'Complete', maxLength: 32 })
  @IsString()
  @IsNotEmpty()
  @MaxLength(32)
  declare readonly status: string;
}

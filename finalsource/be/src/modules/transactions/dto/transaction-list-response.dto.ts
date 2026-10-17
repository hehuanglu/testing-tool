import { ApiProperty } from '@nestjs/swagger';
import type { TransactionType } from '../entities/transaction.entity';

export class TransactionListItemDto {
  @ApiProperty({ example: 1 })
  declare transactionId: number;

  @ApiProperty({ example: 3 })
  declare accountId: number;

  @ApiProperty({ example: '2023-05-17T00:00:00.000Z' })
  declare transactionDate: string;

  @ApiProperty({ enum: ['Revenue', 'Expense'], example: 'Expense' })
  declare type: TransactionType;

  @ApiProperty({ example: 'GTR 5' })
  declare itemDescription: string;

  @ApiProperty({ example: 'Gadget & Gear' })
  declare shopName: string;

  @ApiProperty({ example: 160 })
  declare amount: number;

  @ApiProperty({ example: 'Credit Card' })
  declare paymentMethod: string;

  @ApiProperty({ example: 'Complete' })
  declare status: string;

  @ApiProperty({ example: null, nullable: true, type: String })
  declare receiptId: string | null;

  @ApiProperty({ example: '2023-05-17T08:12:00.000Z' })
  declare createdAt: string;
}

export class TransactionListResponseDto {
  @ApiProperty({ type: [TransactionListItemDto] })
  declare data: TransactionListItemDto[];

  @ApiProperty({ example: 1 })
  declare total: number;

  @ApiProperty({ example: false })
  declare hasMore: boolean;
}

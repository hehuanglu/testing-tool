import { ApiProperty } from '@nestjs/swagger';
import type { TransactionType } from '../../transactions/entities/transaction.entity';

export class RecentAccountTransactionDto {
  @ApiProperty({ example: '2025-10-31', pattern: '^\\d{4}-\\d{2}-\\d{2}$' }) declare date: string;
  @ApiProperty({ example: -500000 }) declare amount: number;
  @ApiProperty({ example: 'Transfer from Momo' }) declare description: string;
  @ApiProperty({ example: 'Complete' }) declare status: string;
  @ApiProperty({ example: 'RCP001', nullable: true }) declare receipt_id: string | null;
  @ApiProperty({ enum: ['Revenue', 'Expense'], example: 'Expense' }) declare type: TransactionType;
}

export class AccountDetailResponseDto {
  @ApiProperty({ example: 1 }) declare id: number;
  @ApiProperty({ example: 'Vietcombank' }) declare bank_name: string;
  @ApiProperty({ example: 'Checking' }) declare account_type: string;
  @ApiProperty({ example: 'District 1' }) declare branch_name: string;
  @ApiProperty({ minLength: 4, maxLength: 4, example: '0123' }) declare account_number_last_4: string;
  @ApiProperty({ example: 5200000 }) declare balance: number;
  @ApiProperty({ type: () => [RecentAccountTransactionDto] }) declare recent_transactions: RecentAccountTransactionDto[];
}

export class AccountDetailEnvelopeDto {
  @ApiProperty({ example: true }) declare success: true;
  @ApiProperty({ example: 'Account details retrieved successfully' }) declare message: string;
  @ApiProperty({ type: () => AccountDetailResponseDto }) declare data: AccountDetailResponseDto;
}

import { HttpException, Injectable, InternalServerErrorException, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { TransactionEntity } from '../transactions/entities/transaction.entity';
import { MonthlySavingsDto, SavingsSummaryResponseDto } from './dto/savings-summary-response.dto';

interface MonthlySavingsRow {
  yearNumber: string;
  monthNumber: string;
  netSavings: string;
}

@Injectable()
export class SavingsService {
  private readonly logger = new Logger(SavingsService.name);

  constructor(@InjectRepository(TransactionEntity) private readonly transactions: Repository<TransactionEntity>) {}

  async summary(userId: number, year: number): Promise<SavingsSummaryResponseDto> {
    const previousYear = year - 1;
    const rangeStart = new Date(Date.UTC(previousYear, 0, 1));
    const rangeEnd = new Date(Date.UTC(year + 1, 0, 1));

    try {
      const rows = await this.transactions
        .createQueryBuilder('transaction')
        .innerJoin('transaction.account', 'account')
        .select('YEAR(transaction.transactionDate)', 'yearNumber')
        .addSelect('MONTH(transaction.transactionDate)', 'monthNumber')
        .addSelect(
          "SUM(CASE WHEN transaction.type = :revenueType THEN transaction.amount WHEN transaction.type = :expenseType THEN -transaction.amount ELSE 0 END)",
          'netSavings',
        )
        .where('account.userId = :userId', { userId })
        .andWhere('transaction.type IN (:...types)', { types: ['Revenue', 'Expense'] })
        .andWhere('transaction.transactionDate >= :rangeStart', { rangeStart })
        .andWhere('transaction.transactionDate < :rangeEnd', { rangeEnd })
        .setParameters({ revenueType: 'Revenue', expenseType: 'Expense' })
        .groupBy('YEAR(transaction.transactionDate)')
        .addGroupBy('MONTH(transaction.transactionDate)')
        .orderBy('YEAR(transaction.transactionDate)', 'ASC')
        .addOrderBy('MONTH(transaction.transactionDate)', 'ASC')
        .getRawMany<MonthlySavingsRow>();

      const series = new Map<string, number>();
      for (const row of rows) {
        const rowYear = Number(row.yearNumber);
        const month = Number(row.monthNumber);
        const amount = Number(row.netSavings);
        if (
          (rowYear !== previousYear && rowYear !== year) ||
          !Number.isInteger(month) ||
          month < 1 ||
          month > 12 ||
          !Number.isFinite(amount) ||
          Math.abs(amount) > Number.MAX_SAFE_INTEGER ||
          !Number.isSafeInteger(amount * 10_000)
        ) {
          throw new InternalServerErrorException('An internal server error occurred while processing the Savings highlighting.');
        }
        series.set(`${rowYear}-${month}`, amount);
      }

      const hasData = rows.length > 0;
      const thisYear = hasData ? this.toSeries(year, series) : [];
      const lastYear = hasData ? this.toSeries(previousYear, series) : [];
      this.logger.log('Savings summary request completed');
      return { user_id: userId, year, summary: { this_year: thisYear, last_year: lastYear } };
    } catch (error: unknown) {
      if (error instanceof HttpException) throw error;
      this.logger.error('Savings summary aggregation failed');
      throw new InternalServerErrorException('An internal server error occurred while processing the Savings highlighting.');
    }
  }

  private toSeries(year: number, values: ReadonlyMap<string, number>): MonthlySavingsDto[] {
    return Array.from({ length: 12 }, (_, index) => ({
      month: String(index + 1).padStart(2, '0'),
      amount: values.get(`${year}-${index + 1}`) ?? 0,
    }));
  }
}

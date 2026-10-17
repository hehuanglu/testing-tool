import { BadRequestException, HttpException, Injectable, InternalServerErrorException, Logger, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { DataSource, Repository } from 'typeorm';
import { CreateTransactionDto } from './dto/create-transaction.dto';
import { CreateTransactionResponseDto } from './dto/create-transaction-response.dto';
import { ListTransactionsQueryDto } from './dto/list-transactions-query.dto';
import { TransactionListItemDto, TransactionListResponseDto } from './dto/transaction-list-response.dto';
import { AccountOptionDto, CategoryOptionDto } from './dto/transaction-option.dto';
import { Account } from './entities/account.entity';
import { Category } from './entities/category.entity';
import { TransactionEntity, type TransactionType } from './entities/transaction.entity';
import { ExpenseSummaryResponseDto, MonthlyExpenseDto } from './dto/expense-summary-response.dto';
import { ExpenseBreakdownCategoryDto, ExpenseBreakdownResponseDto } from './dto/expense-breakdown-response.dto';

const transactionTypes: readonly TransactionType[] = ['Revenue', 'Expense'];

function isTransactionType(value: string): value is TransactionType {
  return transactionTypes.includes(value as TransactionType);
}

@Injectable()
export class TransactionsService {
  private readonly logger = new Logger(TransactionsService.name);

  constructor(
    @InjectRepository(TransactionEntity) private readonly transactions: Repository<TransactionEntity>,
    @InjectRepository(Account) private readonly accounts: Repository<Account>,
    @InjectRepository(Category) private readonly categories: Repository<Category>,
    private readonly dataSource: DataSource,
  ) {}

  async list(userId: number, query: ListTransactionsQueryDto): Promise<TransactionListResponseDto> {
    if (query.type !== 'All' && !isTransactionType(query.type)) {
      throw new BadRequestException('Invalid type parameter');
    }

    const builder = this.transactions
      .createQueryBuilder('transaction')
      .innerJoin('transaction.account', 'account')
      .select([
        'transaction.id',
        'transaction.accountId',
        'transaction.transactionDate',
        'transaction.type',
        'transaction.itemDescription',
        'transaction.shopName',
        'transaction.amount',
        'transaction.paymentMethod',
        'transaction.status',
        'transaction.receiptId',
        'transaction.createdAt',
      ])
      .where('account.userId = :userId', { userId })
      .andWhere('transaction.status = :status', { status: 'Complete' })
      .orderBy('transaction.transactionDate', 'DESC')
      .addOrderBy('transaction.id', 'DESC')
      .skip(query.offset)
      .take(query.limit);

    if (query.type !== 'All') {
      builder.andWhere('transaction.type = :type', { type: query.type });
    }

    const [entities, total] = await builder.getManyAndCount();
    const data = entities.map((transaction) => this.toResponseItem(transaction));
    this.logger.log('Transaction list request completed');
    return { data, total, hasMore: query.offset + data.length < total };
  }

  async expenseSummary(userId: number): Promise<ExpenseSummaryResponseDto> {
    const currentYear = new Date().getUTCFullYear();
    const yearStart = new Date(Date.UTC(currentYear, 0, 1));
    const nextYearStart = new Date(Date.UTC(currentYear + 1, 0, 1));

    try {
      const rows = await this.transactions
        .createQueryBuilder('transaction')
        .innerJoin('transaction.account', 'account')
        .select('MONTH(transaction.transactionDate)', 'monthNumber')
        .addSelect('SUM(transaction.amount)', 'totalExpense')
        .where('account.userId = :userId', { userId })
        .andWhere('transaction.type = :type', { type: 'Expense' })
        .andWhere('transaction.transactionDate >= :yearStart', { yearStart })
        .andWhere('transaction.transactionDate < :nextYearStart', { nextYearStart })
        .groupBy('MONTH(transaction.transactionDate)')
        .orderBy('MONTH(transaction.transactionDate)', 'ASC')
        .getRawMany<{ monthNumber: string; totalExpense: string }>();

      const data = rows.map((row) => this.toMonthlyExpense(row));
      this.logger.log('Monthly expense summary request completed');
      return { data };
    } catch (error: unknown) {
      if (error instanceof InternalServerErrorException) throw error;
      this.logger.error('Monthly expense summary query failed');
      throw new InternalServerErrorException('Cannot load data for Expense.');
    }
  }

  async expenseBreakdown(userId: number, month: string): Promise<ExpenseBreakdownResponseDto> {
    const [yearText, monthText] = month.split('-');
    const year = Number(yearText);
    const monthIndex = Number(monthText) - 1;
    const monthStart = new Date(Date.UTC(year, monthIndex, 1));
    const nextMonthStart = new Date(Date.UTC(year, monthIndex + 1, 1));
    const previousMonthStart = new Date(Date.UTC(year, monthIndex - 1, 1));

    try {
      const currentQuery = this.transactions
        .createQueryBuilder('transaction')
        .innerJoin('transaction.account', 'account')
        .innerJoin('transaction.category', 'category')
        .select('category.id', 'categoryId')
        .addSelect('category.name', 'category')
        .addSelect('transaction.id', 'transactionId')
        .addSelect('transaction.itemDescription', 'itemDescription')
        .addSelect('transaction.amount', 'amount')
        .addSelect('transaction.transactionDate', 'transactionDate')
        .addSelect('SUM(transaction.amount) OVER (PARTITION BY category.id)', 'currentTotal')
        .where('account.userId = :userId', { userId })
        .andWhere('category.userId = :userId', { userId })
        .andWhere('transaction.type = :type', { type: 'Expense' })
        .andWhere('transaction.transactionDate >= :monthStart', { monthStart })
        .andWhere('transaction.transactionDate < :nextMonthStart', { nextMonthStart })
        .orderBy('category.name', 'ASC')
        .addOrderBy('category.id', 'ASC')
        .addOrderBy('transaction.transactionDate', 'DESC')
        .addOrderBy('transaction.id', 'DESC');

      const previousQuery = this.transactions
        .createQueryBuilder('transaction')
        .innerJoin('transaction.account', 'account')
        .innerJoin('transaction.category', 'category')
        .select('category.id', 'categoryId')
        .addSelect('SUM(transaction.amount)', 'previousTotal')
        .where('account.userId = :userId', { userId })
        .andWhere('category.userId = :userId', { userId })
        .andWhere('transaction.type = :type', { type: 'Expense' })
        .andWhere('transaction.transactionDate >= :previousMonthStart', { previousMonthStart })
        .andWhere('transaction.transactionDate < :monthStart', { monthStart })
        .groupBy('category.id');

      const [currentRows, previousRows] = await Promise.all([
        currentQuery.getRawMany<CurrentExpenseRow>(),
        previousQuery.getRawMany<PreviousExpenseRow>(),
      ]);
      if (currentRows.length === 0) throw new NotFoundException('No input data for this month.');

      const previousTotals = new Map(previousRows.map((row) => [row.categoryId, this.safeFinancialNumber(row.previousTotal)]));
      const grouped = new Map<string, ExpenseBreakdownCategoryDto>();
      for (const row of currentRows) {
        const amount = this.safeFinancialNumber(row.amount);
        const currentTotal = this.safeFinancialNumber(row.currentTotal);
        let category = grouped.get(row.categoryId);
        if (!category) {
          const previousTotal = previousTotals.get(row.categoryId) ?? 0;
          const changePercent = previousTotal === 0 ? 100 : ((currentTotal - previousTotal) / previousTotal) * 100;
          if (!Number.isFinite(changePercent) || !Number.isSafeInteger(Number(row.categoryId))) {
            throw new InternalServerErrorException('Internal server error');
          }
          category = { category: row.category, Total: currentTotal, changePercent, subCategories: [] };
          grouped.set(row.categoryId, category);
        }
        const date = new Date(row.transactionDate);
        if (Number.isNaN(date.getTime())) throw new InternalServerErrorException('Internal server error');
        category.subCategories.push({ item_description: row.itemDescription, amount, date: date.toISOString().slice(0, 10) });
      }

      this.logger.log('Expense breakdown request completed');
      return { data: [...grouped.values()] };
    } catch (error: unknown) {
      if (error instanceof HttpException) throw error;
      this.logger.error('Expense breakdown query failed');
      throw new InternalServerErrorException('Internal server error');
    }
  }

  async listAccountOptions(userId: number): Promise<AccountOptionDto[]> {
    const accounts = await this.accounts.find({ select: { id: true }, where: { userId }, order: { id: 'ASC' } });
    return accounts.map((account) => ({ accountId: account.id }));
  }

  async listCategoryOptions(userId: number): Promise<CategoryOptionDto[]> {
    const categories = await this.categories.find({ select: { id: true, name: true }, where: { userId }, order: { id: 'ASC' } });
    return categories.map((category) => ({ category_id: category.id, name: category.name }));
  }

  async create(userId: number, dto: CreateTransactionDto): Promise<CreateTransactionResponseDto> {
    const created = await this.dataSource.transaction('READ COMMITTED', async (manager) => {
      const category = await manager.getRepository(Category).findOne({ select: { id: true }, where: { id: dto.category_id, userId } });
      if (!category) throw new BadRequestException('Invalid or missing transaction data');

      const account = await manager
        .getRepository(Account)
        .createQueryBuilder('account')
        .setLock('pessimistic_write')
        .where('account.id = :accountId', { accountId: dto.accountId })
        .andWhere('account.userId = :userId', { userId })
        .getOne();
      if (!account) throw new BadRequestException('Invalid or missing transaction data');

      const balanceExpression = dto.type === 'Expense' ? '`balance` - :amount' : '`balance` + :amount';
      const balanceUpdate = manager
        .createQueryBuilder()
        .update(Account)
        .set({ balance: () => balanceExpression })
        .where('id = :accountId', { accountId: account.id })
        .andWhere('user_id = :userId', { userId })
        .setParameter('amount', dto.amount);
      if (dto.type === 'Expense') balanceUpdate.andWhere('balance >= :amount');
      const updateResult = await balanceUpdate.execute();
      if (updateResult.affected !== 1) throw new BadRequestException('Invalid or missing transaction data');

      const transaction = manager.getRepository(TransactionEntity).create({
        accountId: account.id,
        categoryId: category.id,
        transactionDate: new Date(dto.transactionDate),
        type: dto.type,
        itemDescription: dto.itemDescription.trim(),
        shopName: dto.shopName.trim(),
        amount: dto.amount,
        paymentMethod: dto.paymentMethod.trim(),
        status: dto.status.trim(),
        receiptId: null,
      });
      return manager.getRepository(TransactionEntity).save(transaction);
    });

    this.logger.log('Transaction creation completed');
    return this.toCreateResponse(created);
  }

  private toResponseItem(transaction: TransactionEntity): TransactionListItemDto {
    const amount = Number(transaction.amount);
    if (!Number.isFinite(amount)) {
      throw new InternalServerErrorException('Internal server error');
    }
    return {
      transactionId: transaction.id,
      accountId: transaction.accountId,
      transactionDate: transaction.transactionDate.toISOString(),
      type: transaction.type,
      itemDescription: transaction.itemDescription,
      shopName: transaction.shopName,
      amount,
      paymentMethod: transaction.paymentMethod,
      status: transaction.status,
      receiptId: transaction.receiptId,
      createdAt: transaction.createdAt.toISOString(),
    };
  }

  private toCreateResponse(transaction: TransactionEntity): CreateTransactionResponseDto {
    const amount = Number(transaction.amount);
    if (!Number.isFinite(amount)) throw new InternalServerErrorException('Internal server error');
    return {
      transactionId: transaction.id,
      accountId: transaction.accountId,
      transactionDate: transaction.transactionDate.toISOString(),
      type: transaction.type,
      itemDescription: transaction.itemDescription,
      shopName: transaction.shopName,
      amount,
      paymentMethod: transaction.paymentMethod,
      status: transaction.status,
      receiptId: transaction.receiptId,
      createdAt: transaction.createdAt.toISOString(),
      category_id: transaction.categoryId,
    };
  }

  private toMonthlyExpense(row: { monthNumber: string; totalExpense: string }): MonthlyExpenseDto {
    const monthNumber = Number(row.monthNumber);
    const totalExpense = Number(row.totalExpense);
    const month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][monthNumber - 1];
    if (!month || !Number.isFinite(totalExpense) || totalExpense < 0 || totalExpense > Number.MAX_SAFE_INTEGER) {
      throw new InternalServerErrorException('Cannot load data for Expense.');
    }
    return { month, totalExpense };
  }

  private safeFinancialNumber(value: string): number {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed < 0 || parsed > Number.MAX_SAFE_INTEGER) {
      throw new InternalServerErrorException('Internal server error');
    }
    return parsed;
  }
}

interface CurrentExpenseRow {
  categoryId: string;
  category: string;
  transactionId: string;
  itemDescription: string;
  amount: string;
  transactionDate: Date | string;
  currentTotal: string;
}

interface PreviousExpenseRow {
  categoryId: string;
  previousTotal: string;
}

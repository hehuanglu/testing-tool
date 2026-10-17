import { BadRequestException, ForbiddenException, HttpException, Injectable, InternalServerErrorException, Logger, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Category } from '../transactions/entities/category.entity';
import { TransactionEntity } from '../transactions/entities/transaction.entity';
import { CreateGoalDto } from './dto/create-goal.dto';
import { CreateGoalResponseDto } from './dto/create-goal-response.dto';
import { ExpenseGoalDto, GoalsResponseDto, SavingGoalDto } from './dto/goals-response.dto';
import { UpdateGoalDto } from './dto/update-goal.dto';
import { UpdateGoalResponseDto } from './dto/update-goal-response.dto';
import { GoalEntity } from './entities/goal.entity';

@Injectable()
export class GoalsService {
  private readonly logger = new Logger(GoalsService.name);
  constructor(
    @InjectRepository(GoalEntity) private readonly goals: Repository<GoalEntity>,
    @InjectRepository(TransactionEntity) private readonly transactions: Repository<TransactionEntity>,
    @InjectRepository(Category) private readonly categories: Repository<Category>,
  ) {}

  async list(userId: number): Promise<GoalsResponseDto> {
    const now = new Date();
    const monthStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
    const nextMonthStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1));
    const periodMonth = monthStart.toISOString().slice(0, 10);
    try {
      const saving = await this.goals.createQueryBuilder('goal')
        .select(['goal.id', 'goal.goalType', 'goal.targetAmount', 'goal.startDate', 'goal.endDate'])
        .where('goal.userId = :userId', { userId }).andWhere('goal.goalType = :savingType', { savingType: 'Saving' })
        .andWhere('goal.startDate < :nextMonth', { nextMonth: periodDate(nextMonthStart) })
        .andWhere('goal.endDate >= :monthStart', { monthStart: periodMonth })
        .orderBy('goal.startDate', 'DESC').addOrderBy('goal.id', 'DESC').getOne();
      const expenseGoals = await this.goals.createQueryBuilder('goal')
        .innerJoin('goal.category', 'category', 'category.userId = :userId', { userId })
        .select(['goal.id', 'goal.targetAmount', 'category.name'])
        .where('goal.userId = :userId', { userId }).andWhere('goal.goalType = :expenseType', { expenseType: 'Expense' })
        .andWhere('goal.startDate < :nextMonth', { nextMonth: periodDate(nextMonthStart) })
        .andWhere('goal.endDate >= :monthStart', { monthStart: periodMonth })
        .orderBy('category.name', 'ASC').addOrderBy('goal.id', 'ASC').getMany();
      const totals = await this.transactions.createQueryBuilder('transaction').innerJoin('transaction.account', 'account')
        .select("COALESCE(SUM(CASE WHEN transaction.type = 'Revenue' THEN transaction.amount ELSE 0 END), 0)", 'income')
        .addSelect("COALESCE(SUM(CASE WHEN transaction.type = 'Expense' THEN transaction.amount ELSE 0 END), 0)", 'expense')
        .where('account.userId = :userId', { userId }).andWhere('transaction.status = :status', { status: 'Complete' })
        .andWhere('transaction.transactionDate >= :monthStart', { monthStart })
        .andWhere('transaction.transactionDate < :nextMonthStart', { nextMonthStart })
        .getRawOne<{ income: string; expense: string }>();
      const targetAchieved = this.money((totals ? Number(totals.income) - Number(totals.expense) : 0).toString(), true);
      this.logger.log('Goals list request completed');
      return { savingGoal: saving ? this.savingDto(saving, targetAchieved) : null, expenseGoals: expenseGoals.map((goal) => this.expenseDto(goal)) };
    } catch (error: unknown) {
      if (error instanceof InternalServerErrorException) throw error;
      this.logger.error('Goals list query failed');
      throw new InternalServerErrorException('500 Internal Server Error. Try again.');
    }
  }

  async create(userId: number, dto: CreateGoalDto): Promise<CreateGoalResponseDto> {
    try {
      if (!isValidDateOnly(dto.start_date) || !isValidDateOnly(dto.end_date) || dto.end_date <= dto.start_date) {
        this.logger.warn('Goal date validation rejected');
        throw new BadRequestException('End date must be after start date.');
      }

      let categoryId: number | null = null;
      let periodMonth: string | null = null;
      if (dto.goal_type === 'Expense') {
        if (dto.category_id === undefined || dto.category_id === null) {
          this.logger.warn('Goal category validation rejected');
          throw new BadRequestException('Please select an expense category.');
        }
        const category = await this.categories.findOne({ select: { id: true }, where: { id: dto.category_id, userId } });
        if (!category) {
          this.logger.warn('Goal category ownership rejected');
          throw new BadRequestException('Please select a valid expense category.');
        }
        categoryId = category.id;
        periodMonth = `${dto.start_date.slice(0, 7)}-01`;
      } else if (dto.category_id !== undefined && dto.category_id !== null) {
        this.logger.warn('Saving goal category validation rejected');
        throw new BadRequestException('Category is not allowed for an overall savings goal.');
      }

      const goal = this.goals.create({
        userId,
        goalType: dto.goal_type,
        targetAmount: dto.target_amount,
        categoryId,
        periodMonth,
        startDate: dto.start_date,
        endDate: dto.end_date,
      });
      const created = await this.goals.save(goal);
      this.logger.log('Goal creation completed');
      return { goal_id: created.id };
    } catch (error: unknown) {
      if (error instanceof HttpException) throw error;
      this.logger.error('Goal creation failed');
      throw new InternalServerErrorException('Cannot add Goals right now. Try again.');
    }
  }

  async update(userId: number, goalId: number, dto: UpdateGoalDto): Promise<UpdateGoalResponseDto> {
    try {
      if (!Number.isSafeInteger(goalId) || goalId <= 0) throw new BadRequestException('Invalid goal identifier.');
      const goal = await this.goals.findOne({ select: { id: true, userId: true }, where: { id: goalId } });
      if (!goal) {
        this.logger.warn('Goal adjustment lookup rejected');
        throw new NotFoundException('Goal not found.');
      }
      if (goal.userId !== userId) {
        this.logger.warn('Goal adjustment ownership rejected');
        throw new ForbiddenException('You do not have permission to edit this target.');
      }

      await this.goals.save({ ...goal, targetAmount: dto.target_amount });
      this.logger.log('Goal adjustment completed');
      return { updated_goal: { goal_id: goalId, target_amount: this.money(dto.target_amount) } };
    } catch (error: unknown) {
      if (error instanceof HttpException) throw error;
      this.logger.error('Goal adjustment failed');
      throw new InternalServerErrorException('Cannot update now. Try again.');
    }
  }

  private savingDto(goal: GoalEntity, targetAchieved: number): SavingGoalDto {
    if (goal.goalType !== 'Saving' || !goal.startDate || !goal.endDate) throw new InternalServerErrorException('500 Internal Server Error. Try again.');
    return { goal_id: goal.id, goal_type: 'Saving', target_amount: this.money(goal.targetAmount), target_achieved: targetAchieved, start_date: goal.startDate, end_date: goal.endDate };
  }
  private expenseDto(goal: GoalEntity): ExpenseGoalDto {
    if (!goal.category?.name) throw new InternalServerErrorException('500 Internal Server Error. Try again.');
    return { goal_id: goal.id, category: goal.category.name, target_amount: this.money(goal.targetAmount) };
  }
  private money(value: string, allowNegative = false): number {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || (!allowNegative && parsed <= 0) || Math.abs(parsed) > Number.MAX_SAFE_INTEGER || !Number.isSafeInteger(parsed * 10_000)) throw new InternalServerErrorException('500 Internal Server Error. Try again.');
    return parsed;
  }
}

function periodDate(value: Date): string { return value.toISOString().slice(0, 10); }
function isValidDateOnly(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

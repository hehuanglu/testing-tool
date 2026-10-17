import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AuthModule } from '../auth/auth.module';
import { Account } from './entities/account.entity';
import { Category } from './entities/category.entity';
import { TransactionEntity } from './entities/transaction.entity';
import { AccountOptionsController, CategoryOptionsController } from './transaction-options.controller';
import { TransactionsController } from './transactions.controller';
import { TransactionsService } from './transactions.service';
import { ExpensesController } from './expenses.controller';

@Module({
  imports: [TypeOrmModule.forFeature([Account, Category, TransactionEntity]), AuthModule],
  controllers: [TransactionsController, ExpensesController, AccountOptionsController, CategoryOptionsController],
  providers: [TransactionsService],
})
export class TransactionsModule {}

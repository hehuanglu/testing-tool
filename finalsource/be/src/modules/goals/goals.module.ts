import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Category } from '../transactions/entities/category.entity';
import { TransactionEntity } from '../transactions/entities/transaction.entity';
import { GoalEntity } from './entities/goal.entity';
import { GoalsController } from './goals.controller';
import { GoalsService } from './goals.service';

@Module({ imports: [TypeOrmModule.forFeature([GoalEntity, TransactionEntity, Category])], controllers: [GoalsController], providers: [GoalsService] })
export class GoalsModule {}

import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AuthModule } from '../auth/auth.module';
import { TransactionEntity } from '../transactions/entities/transaction.entity';
import { SavingsController } from './savings.controller';
import { SavingsService } from './savings.service';

@Module({
  imports: [TypeOrmModule.forFeature([TransactionEntity]), AuthModule],
  controllers: [SavingsController],
  providers: [SavingsService],
})
export class SavingsModule {}

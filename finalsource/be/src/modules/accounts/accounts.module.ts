import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AuthModule } from '../auth/auth.module';
import { Account } from '../transactions/entities/account.entity';
import { TransactionEntity } from '../transactions/entities/transaction.entity';
import { AccountsController } from './accounts.controller';
import { AccountsService } from './accounts.service';
import { AccountNumberCryptoService } from './account-number-crypto.service';

@Module({
  imports: [AuthModule, TypeOrmModule.forFeature([Account, TransactionEntity])],
  controllers: [AccountsController],
  providers: [AccountsService, AccountNumberCryptoService],
})
export class AccountsModule {}

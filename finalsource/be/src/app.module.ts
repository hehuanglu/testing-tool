import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import appConfig from './config/app.config';
import databaseConfig from './config/database.config';
import { validateEnvironment } from './config/environment.validation';
import { DatabaseModule } from './database/database.module';
import { HealthController } from './health.controller';
import { AuthModule } from './modules/auth/auth.module';
import { BillsModule } from './modules/bills/bills.module';
import { TransactionsModule } from './modules/transactions/transactions.module';
import { AccountsModule } from './modules/accounts/accounts.module';
import { GoalsModule } from './modules/goals/goals.module';
import { SavingsModule } from './modules/savings/savings.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true, cache: true, load: [appConfig, databaseConfig], validate: validateEnvironment }),
    DatabaseModule,
    AuthModule,
    BillsModule,
    TransactionsModule,
    AccountsModule,
    GoalsModule,
    SavingsModule,
  ],
  controllers: [HealthController],
})
export class AppModule {}

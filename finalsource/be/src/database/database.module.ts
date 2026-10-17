import { Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { CreateUsers1791135661000 } from './migrations/1791135661000-create-users';
import { CreateAccountsAndTransactions1791270599000 } from './migrations/1791270599000-create-accounts-and-transactions';
import { AddTransactionCreationSchema1791310100000 } from './migrations/1791310100000-add-transaction-creation-schema';
import { AddAccountDisplayFields1791345000000 } from './migrations/1791345000000-add-account-display-fields';
import { AddEncryptedAccountNumber1791347800000 } from './migrations/1791347800000-add-encrypted-account-number';
import { CreateBills1791600000000 } from './migrations/1791600000000-create-bills';
import { CreateGoals1791728321000 } from './migrations/1791728321000-create-goals';
import { AlignGoalsDateRanges1791746799000 } from './migrations/1791746799000-align-goals-date-ranges';

@Module({
  imports: [
    TypeOrmModule.forRootAsync({
      inject: [ConfigService],
      useFactory: (config: ConfigService) => ({
        type: 'mysql' as const,
        host: config.getOrThrow<string>('database.host'),
        port: config.getOrThrow<number>('database.port'),
        username: config.getOrThrow<string>('database.username'),
        password: config.getOrThrow<string>('database.password'),
        database: config.getOrThrow<string>('database.database'),
        autoLoadEntities: true,
        migrations: [
          CreateUsers1791135661000,
          CreateAccountsAndTransactions1791270599000,
          AddTransactionCreationSchema1791310100000,
          AddAccountDisplayFields1791345000000,
          AddEncryptedAccountNumber1791347800000,
          CreateBills1791600000000,
          CreateGoals1791728321000,
          AlignGoalsDateRanges1791746799000,
        ],
        migrationsRun: true,
        synchronize: false,
        logging: false,
      }),
    }),
  ],
})
export class DatabaseModule {}

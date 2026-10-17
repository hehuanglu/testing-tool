import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AuthModule } from '../auth/auth.module';
import { BillsController } from './bills.controller';
import { BillsService } from './bills.service';
import { Bill } from './entities/bill.entity';

@Module({ imports: [AuthModule, TypeOrmModule.forFeature([Bill])], controllers: [BillsController], providers: [BillsService] })
export class BillsModule {}

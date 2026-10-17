import { Injectable, InternalServerErrorException, Logger, UnauthorizedException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Between, Repository } from 'typeorm';
import { Bill } from './entities/bill.entity';
import { BillsPayloadDto } from './dto/bill-response.dto';

@Injectable()
export class BillsService {
  private readonly logger = new Logger(BillsService.name);
  constructor(@InjectRepository(Bill) private readonly bills: Repository<Bill>) {}

  async upcoming(userId: number): Promise<BillsPayloadDto> {
    if (!Number.isSafeInteger(userId) || userId < 1) throw new UnauthorizedException();
    const today = new Date();
    const start = today.toISOString().slice(0, 10);
    today.setUTCDate(today.getUTCDate() + 30);
    const end = today.toISOString().slice(0, 10);
    try {
      const rows = await this.bills.find({
        where: { userId, dueDate: Between(start, end) },
        order: { dueDate: 'ASC', id: 'ASC' },
        select: { id: true, userId: true, itemDescription: true, logoUrl: true, dueDate: true, lastChargeDate: true, amount: true },
      });
      const data = rows.map((bill) => ({
        billId: bill.id, userId: bill.userId, itemDescription: bill.itemDescription,
        logoUrl: bill.logoUrl, dueDate: bill.dueDate, lastChargeDate: bill.lastChargeDate,
        Amount: this.serializeAmount(bill.amount),
      }));
      this.logger.log('Owner-scoped bills read succeeded');
      return { data };
    } catch {
      this.logger.error('Owner-scoped bills read failed');
      throw new InternalServerErrorException('Failed to fetch bills');
    }
  }

  private serializeAmount(value: string): number {
    // Preserve four decimal places within the exact safe scaled-integer domain.
    if (!/^\d{1,15}\.\d{4}$/.test(value)) throw new Error('Invalid monetary representation');
    const scaled = BigInt(value.replace('.', ''));
    const amount = Number(value);
    if (scaled <= 0n || scaled > BigInt(Number.MAX_SAFE_INTEGER) || !Number.isFinite(amount) || amount <= 0) {
      throw new Error('Unsafe monetary representation');
    }
    return amount;
  }
}

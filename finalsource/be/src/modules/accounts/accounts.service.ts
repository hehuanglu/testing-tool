import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  Injectable,
  InternalServerErrorException,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { DataSource, Repository } from 'typeorm';
import { Account } from '../transactions/entities/account.entity';
import { TransactionEntity } from '../transactions/entities/transaction.entity';
import { AccountListResponseDto } from './dto/account-list-response.dto';
import { AccountDetailResponseDto } from './dto/account-detail-response.dto';
import { AccountNumberCryptoService, type ProtectedAccountNumber } from './account-number-crypto.service';
import { CreateAccountDto } from './dto/create-account.dto';
import { CreateAccountResponseDto } from './dto/create-account-response.dto';
import { UpdateAccountDto } from './dto/update-account.dto';
import { UpdateAccountResponseDto } from './dto/update-account-response.dto';

const safeSystemError = 'A system error has occurred, please try again later.';
const safeCreateSystemError = 'Unable to add account at this time. Please try again later.';
const duplicateMessage = 'This account already exists in your list.';
const forbiddenUpdateMessage = 'You do not have permission to edit this account information.';
const safeUpdateSystemError = 'An error occurred while saving the data. Please try again later.';
const forbiddenDeleteMessage = 'You do not have permission to perform this operation.';
const notFoundDeleteMessage = 'Account not found or not owned by current user';
const safeDeleteSystemError = 'A system error occurred; it was not possible to delete the account and related transactions.';
const forbiddenDetailMessage = 'You do not have permission to view this account information.';
const notFoundDetailMessage = 'This account was not found.';
const safeDetailSystemError = 'An error occurred, data could not be loaded.';

function serializeBalance(value: string): number {
  const result = Number(value);
  // Numeric JSON is the UC contract. Reject precision loss rather than round it silently.
  const exact = value.replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
  if (!Number.isFinite(result) || result < 0 || String(result) !== (exact || '0')) {
    throw new InternalServerErrorException(safeSystemError);
  }
  return result;
}

@Injectable()
export class AccountsService {
  private readonly logger = new Logger(AccountsService.name);

  constructor(
    @InjectRepository(Account) private readonly accounts: Repository<Account>,
    @InjectRepository(TransactionEntity) private readonly transactions: Repository<TransactionEntity>,
    private readonly accountNumbers: AccountNumberCryptoService,
    private readonly dataSource: DataSource,
  ) {}

  async list(userId: number): Promise<AccountListResponseDto> {
    try {
      const accounts = await this.accounts.find({
        where: { userId },
        select: { id: true, bankName: true, accountType: true, branchName: true, accountNumberLast4: true, balance: true },
        order: { id: 'ASC' },
      });
      return {
        user_id: userId,
        accounts: accounts.map((account) => ({
          id: account.id,
          bank_name: account.bankName,
          account_type: account.accountType,
          branch_name: account.branchName,
          account_number_last_4: account.accountNumberLast4,
          balance: serializeBalance(account.balance),
        })),
      };
    } catch {
      throw new InternalServerErrorException(safeSystemError);
    }
  }

  async detail(userId: number, accountId: number): Promise<AccountDetailResponseDto> {
    if (!Number.isSafeInteger(accountId) || accountId <= 0) throw new BadRequestException('Invalid account identifier');

    try {
      const account = await this.accounts.findOne({
        where: { id: accountId },
        select: {
          id: true,
          userId: true,
          bankName: true,
          accountType: true,
          branchName: true,
          accountNumberLast4: true,
          balance: true,
        },
      });
      if (!account) throw new NotFoundException(notFoundDetailMessage);
      if (account.userId !== userId) {
        this.logger.warn('Account detail access rejected by ownership check');
        throw new ForbiddenException(forbiddenDetailMessage);
      }

      const recentTransactions = await this.transactions.find({
        where: { accountId },
        select: {
          id: true,
          transactionDate: true,
          amount: true,
          itemDescription: true,
          status: true,
          receiptId: true,
          type: true,
        },
        order: { transactionDate: 'DESC', id: 'DESC' },
        take: 5,
      });

      this.logger.log('Account details retrieved for authenticated owner');
      return {
        id: account.id,
        bank_name: account.bankName,
        account_type: account.accountType,
        branch_name: account.branchName,
        account_number_last_4: account.accountNumberLast4,
        balance: serializeBalance(account.balance),
        recent_transactions: recentTransactions.map((transaction) => ({
          date: transaction.transactionDate.toISOString().slice(0, 10),
          amount: serializeTransactionAmount(transaction.amount, transaction.type),
          description: transaction.itemDescription,
          status: transaction.status,
          receipt_id: transaction.receiptId,
          type: transaction.type,
        })),
      };
    } catch (error: unknown) {
      if (error instanceof BadRequestException || error instanceof ForbiddenException || error instanceof NotFoundException) throw error;
      this.logger.error('Account detail retrieval failed');
      throw new InternalServerErrorException(safeDetailSystemError);
    }
  }

  async create(userId: number, input: CreateAccountDto): Promise<CreateAccountResponseDto> {
    const protectedNumber = this.accountNumbers.protect(input.account_number_full);
    try {
      const duplicate = await this.accounts
        .createQueryBuilder('account')
        .select('account.id')
        .where('account.user_id = :userId', { userId })
        .andWhere('account.account_number_lookup_hash = :lookupHash', { lookupHash: protectedNumber.lookupHash })
        .getOne();
      if (duplicate) {
        this.logger.warn('Account creation rejected because the owner already linked this account');
        throw new ConflictException(duplicateMessage);
      }

      const entity = this.accounts.create({
        userId,
        bankName: input.bank_name,
        accountType: input.account_type,
        branchName: input.branch_name ?? '',
        accountNumberLast4: protectedNumber.last4,
        balance: input.balance.toFixed(4),
        accountNumberCiphertext: protectedNumber.ciphertext,
        accountNumberIv: protectedNumber.iv,
        accountNumberAuthTag: protectedNumber.authTag,
        accountNumberKeyVersion: protectedNumber.keyVersion,
        accountNumberLookupHash: protectedNumber.lookupHash,
      });
      const saved = await this.accounts.save(entity);
      this.logger.log('Account created for authenticated owner');
      return {
        account: {
          id: saved.id,
          user_id: userId,
          bank_name: saved.bankName,
          account_type: saved.accountType,
          branch_name: saved.branchName,
          account_number_last_4: saved.accountNumberLast4,
          balance: serializeBalance(saved.balance),
        },
      };
    } catch (error: unknown) {
      if (error instanceof ConflictException || isDuplicateEntry(error)) throw new ConflictException(duplicateMessage);
      this.logger.error('Account creation failed');
      throw new InternalServerErrorException(safeCreateSystemError);
    } finally {
      protectedNumber.ciphertext.fill(0);
      protectedNumber.iv.fill(0);
      protectedNumber.authTag.fill(0);
      protectedNumber.lookupHash.fill(0);
    }
  }

  async update(userId: number, accountId: number, input: UpdateAccountDto): Promise<UpdateAccountResponseDto> {
    let protectedNumber: ProtectedAccountNumber | undefined;
    try {
      const result = await this.dataSource.transaction('READ COMMITTED', async (manager) => {
        const repository = manager.getRepository(Account);
        const account = await repository
          .createQueryBuilder('account')
          .where('account.id = :accountId', { accountId })
          .setLock('pessimistic_write')
          .getOne();

        if (!account) throw new NotFoundException('Account not found.');
        if (account.userId !== userId) {
          this.logger.warn('Account update rejected by ownership check');
          throw new ForbiddenException(forbiddenUpdateMessage);
        }

        if (input.account_number_full) {
          protectedNumber = this.accountNumbers.protect(input.account_number_full);
          if (input.account_number_last_4 && input.account_number_last_4 !== protectedNumber.last4) {
            throw new BadRequestException('account_number_last_4 must match account_number_full');
          }
          const duplicate = await repository
            .createQueryBuilder('candidate')
            .select('candidate.id')
            .where('candidate.user_id = :userId', { userId })
            .andWhere('candidate.id <> :accountId', { accountId })
            .andWhere('candidate.account_number_lookup_hash = :lookupHash', { lookupHash: protectedNumber.lookupHash })
            .getOne();
          if (duplicate) {
            this.logger.warn('Account update rejected because the owner already linked the replacement account');
            throw new ConflictException(duplicateMessage);
          }
        } else if (input.account_number_last_4 && input.account_number_last_4 !== account.accountNumberLast4) {
          throw new BadRequestException('account_number_last_4 must match the current account number');
        }

        account.bankName = input.bank_name;
        account.accountType = input.account_type;
        account.branchName = input.branch_name ?? account.branchName;
        account.balance = input.balance.toFixed(4);
        if (protectedNumber) {
          account.accountNumberLast4 = protectedNumber.last4;
          account.accountNumberCiphertext = protectedNumber.ciphertext;
          account.accountNumberIv = protectedNumber.iv;
          account.accountNumberAuthTag = protectedNumber.authTag;
          account.accountNumberKeyVersion = protectedNumber.keyVersion;
          account.accountNumberLookupHash = protectedNumber.lookupHash;
        }

        const saved = await repository.save(account);
        return {
          account: {
            account_id: saved.id,
            user_id: saved.userId,
            bank_name: saved.bankName,
            account_type: saved.accountType,
            branch_name: saved.branchName,
            account_number_last_4: saved.accountNumberLast4,
            balance: serializeBalance(saved.balance),
            updated_at: saved.updatedAt.toISOString(),
          },
        };
      });
      this.logger.log('Account updated for authenticated owner');
      return result;
    } catch (error: unknown) {
      if (
        error instanceof BadRequestException ||
        error instanceof ConflictException ||
        error instanceof ForbiddenException ||
        error instanceof NotFoundException
      ) {
        throw error;
      }
      if (isDuplicateEntry(error)) throw new ConflictException(duplicateMessage);
      this.logger.error('Account update failed');
      throw new InternalServerErrorException(safeUpdateSystemError);
    } finally {
      if (protectedNumber) clearProtectedNumber(protectedNumber);
    }
  }

  async remove(userId: number, accountId: number): Promise<{ deleted_account_id: number }> {
    if (!Number.isSafeInteger(accountId) || accountId <= 0) throw new BadRequestException('Invalid account identifier');

    try {
      const deletedAccountId = await this.dataSource.transaction('READ COMMITTED', async (manager) => {
        const account = await manager
          .getRepository(Account)
          .createQueryBuilder('account')
          .select(['account.id', 'account.userId'])
          .where('account.id = :accountId', { accountId })
          .setLock('pessimistic_write')
          .getOne();

        if (!account) throw new NotFoundException(notFoundDeleteMessage);
        if (account.userId !== userId) {
          this.logger.warn('Account deletion rejected by ownership check');
          throw new ForbiddenException(forbiddenDeleteMessage);
        }

        await manager
          .createQueryBuilder()
          .delete()
          .from(TransactionEntity)
          .where('account_id = :accountId', { accountId })
          .execute();

        const deletion = await manager
          .createQueryBuilder()
          .delete()
          .from(Account)
          .where('id = :accountId', { accountId })
          .andWhere('user_id = :userId', { userId })
          .execute();
        if (deletion.affected !== 1) throw new Error('Account deletion did not affect exactly one row');
        return accountId;
      });

      this.logger.log('Account and related transactions deleted for authenticated owner');
      return { deleted_account_id: deletedAccountId };
    } catch (error: unknown) {
      if (error instanceof BadRequestException || error instanceof ForbiddenException || error instanceof NotFoundException) throw error;
      this.logger.error('Account deletion failed and was rolled back');
      throw new InternalServerErrorException(safeDeleteSystemError);
    }
  }
}

function clearProtectedNumber(value: ProtectedAccountNumber): void {
  value.ciphertext.fill(0);
  value.iv.fill(0);
  value.authTag.fill(0);
  value.lookupHash.fill(0);
}

function serializeTransactionAmount(value: string, type: TransactionEntity['type']): number {
  const magnitude = serializeBalance(value);
  return type === 'Expense' ? -magnitude : magnitude;
}

function isDuplicateEntry(error: unknown): boolean {
  if (typeof error !== 'object' || error === null) return false;
  return ('errno' in error && error.errno === 1062) || ('code' in error && error.code === 'ER_DUP_ENTRY');
}

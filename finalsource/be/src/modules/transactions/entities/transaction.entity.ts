import { Check, Column, CreateDateColumn, Entity, Index, JoinColumn, ManyToOne, PrimaryGeneratedColumn, UpdateDateColumn } from 'typeorm';
import { Account } from './account.entity';
import { Category } from './category.entity';

export type TransactionType = 'Revenue' | 'Expense';

@Entity({ name: 'transactions' })
@Check('chk_transactions_type', "`type` IN ('Revenue', 'Expense')")
@Check('chk_transactions_amount_positive', '`amount` > 0')
@Index('idx_transactions_account_date_id', ['accountId', 'transactionDate', 'id'])
@Index('idx_transactions_account_type_date_id', ['accountId', 'type', 'transactionDate', 'id'])
@Index('idx_transactions_category_id', ['categoryId'])
export class TransactionEntity {
  @PrimaryGeneratedColumn({ type: 'int', unsigned: true, name: 'id', primaryKeyConstraintName: 'pk_transactions' })
  declare id: number;

  @Column({ type: 'int', unsigned: true, name: 'account_id' })
  declare accountId: number;

  @ManyToOne(() => Account, { nullable: false, onDelete: 'RESTRICT' })
  @JoinColumn({ name: 'account_id', foreignKeyConstraintName: 'fk_transactions_accounts' })
  declare account: Account;

  @Column({ type: 'int', unsigned: true, name: 'category_id' })
  declare categoryId: number;

  @ManyToOne(() => Category, { nullable: false, onDelete: 'RESTRICT' })
  @JoinColumn({ name: 'category_id', foreignKeyConstraintName: 'fk_transactions_categories' })
  declare category: Category;

  @Column({ type: 'datetime', precision: 3, name: 'transaction_date' })
  declare transactionDate: Date;

  @Column({ type: 'varchar', length: 16, name: 'type' })
  declare type: TransactionType;

  @Column({ type: 'varchar', length: 255, name: 'item_description' })
  declare itemDescription: string;

  @Column({ type: 'varchar', length: 160, name: 'shop_name' })
  declare shopName: string;

  @Column({ type: 'decimal', precision: 19, scale: 4, name: 'amount' })
  declare amount: string;

  @Column({ type: 'varchar', length: 64, name: 'payment_method' })
  declare paymentMethod: string;

  @Column({ type: 'varchar', length: 32, name: 'status' })
  declare status: string;

  @Column({ type: 'varchar', length: 255, name: 'receipt_id', nullable: true })
  declare receiptId: string | null;

  @CreateDateColumn({ type: 'datetime', precision: 3, name: 'created_at', default: () => 'CURRENT_TIMESTAMP(3)' })
  declare createdAt: Date;

  @UpdateDateColumn({ type: 'datetime', precision: 3, name: 'updated_at', default: () => 'CURRENT_TIMESTAMP(3)', onUpdate: 'CURRENT_TIMESTAMP(3)' })
  declare updatedAt: Date;
}

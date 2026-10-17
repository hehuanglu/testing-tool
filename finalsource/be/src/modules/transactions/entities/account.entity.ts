import { Check, Column, CreateDateColumn, Entity, Index, JoinColumn, ManyToOne, PrimaryGeneratedColumn, UpdateDateColumn } from 'typeorm';
import { User } from '../../auth/entities/user.entity';

@Entity({ name: 'accounts' })
@Check('chk_accounts_balance_nonnegative', '`balance` >= 0')
@Check('chk_accounts_number_last4', "`account_number_last_4` REGEXP '^[0-9]{4}$'")
@Check(
  'chk_accounts_number_crypto_group',
  '(`account_number_ciphertext` IS NULL AND `account_number_iv` IS NULL AND `account_number_auth_tag` IS NULL AND `account_number_key_version` IS NULL AND `account_number_lookup_hash` IS NULL) OR (`account_number_ciphertext` IS NOT NULL AND `account_number_iv` IS NOT NULL AND `account_number_auth_tag` IS NOT NULL AND `account_number_key_version` IS NOT NULL AND `account_number_lookup_hash` IS NOT NULL)',
)
@Index('idx_accounts_user_id', ['userId', 'id'])
@Index('uq_accounts_user_number_hash', ['userId', 'accountNumberLookupHash'], { unique: true })
export class Account {
  @PrimaryGeneratedColumn({ type: 'int', unsigned: true, name: 'id', primaryKeyConstraintName: 'pk_accounts' })
  declare id: number;

  @Column({ type: 'int', unsigned: true, name: 'user_id' })
  declare userId: number;

  @ManyToOne(() => User, { nullable: false, onDelete: 'RESTRICT' })
  @JoinColumn({ name: 'user_id', foreignKeyConstraintName: 'fk_accounts_users' })
  declare user: User;

  @Column({ type: 'decimal', precision: 19, scale: 4, name: 'balance', default: '0.0000' })
  declare balance: string;

  @Column({ type: 'varchar', length: 160, name: 'bank_name' })
  declare bankName: string;

  @Column({ type: 'varchar', length: 64, name: 'account_type' })
  declare accountType: string;

  @Column({ type: 'varchar', length: 160, name: 'branch_name' })
  declare branchName: string;

  @Column({ type: 'char', length: 4, name: 'account_number_last_4' })
  declare accountNumberLast4: string;

  @Column({ type: 'varbinary', length: 256, name: 'account_number_ciphertext', nullable: true, select: false })
  declare accountNumberCiphertext: Buffer | null;

  @Column({ type: 'binary', length: 12, name: 'account_number_iv', nullable: true, select: false })
  declare accountNumberIv: Buffer | null;

  @Column({ type: 'binary', length: 16, name: 'account_number_auth_tag', nullable: true, select: false })
  declare accountNumberAuthTag: Buffer | null;

  @Column({ type: 'smallint', unsigned: true, name: 'account_number_key_version', nullable: true, select: false })
  declare accountNumberKeyVersion: number | null;

  @Column({ type: 'binary', length: 32, name: 'account_number_lookup_hash', nullable: true, select: false })
  declare accountNumberLookupHash: Buffer | null;

  @CreateDateColumn({ type: 'datetime', precision: 3, name: 'created_at', default: () => 'CURRENT_TIMESTAMP(3)' })
  declare createdAt: Date;

  @UpdateDateColumn({ type: 'datetime', precision: 3, name: 'updated_at', default: () => 'CURRENT_TIMESTAMP(3)', onUpdate: 'CURRENT_TIMESTAMP(3)' })
  declare updatedAt: Date;
}

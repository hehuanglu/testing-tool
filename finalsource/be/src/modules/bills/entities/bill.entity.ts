import { Check, Column, CreateDateColumn, Entity, Index, JoinColumn, ManyToOne, PrimaryGeneratedColumn, UpdateDateColumn } from 'typeorm';
import { User } from '../../auth/entities/user.entity';

@Entity({ name: 'bills' })
@Index('idx_bills_user_due_id', ['userId', 'dueDate', 'id'])
@Check('chk_bills_amount_positive', 'amount > 0')
export class Bill {
  @PrimaryGeneratedColumn({ name: 'id', type: 'int', unsigned: true, primaryKeyConstraintName: 'pk_bills' })
  declare id: number;

  @Column({ name: 'user_id', type: 'int', unsigned: true })
  declare userId: number;

  @ManyToOne(() => User, { nullable: false, onDelete: 'RESTRICT', cascade: false })
  @JoinColumn({ name: 'user_id', foreignKeyConstraintName: 'fk_bills_users' })
  declare user: User;

  @Column({ name: 'item_description', type: 'varchar', length: 255 })
  declare itemDescription: string;

  @Column({ name: 'logo_url', type: 'varchar', length: 2048 })
  declare logoUrl: string;

  @Column({ name: 'due_date', type: 'date' })
  declare dueDate: string;

  @Column({ name: 'last_charge_date', type: 'date' })
  declare lastChargeDate: string;

  @Column({ name: 'amount', type: 'decimal', precision: 19, scale: 4 })
  declare amount: string;

  @CreateDateColumn({ name: 'created_at', type: 'datetime', precision: 3, default: () => 'CURRENT_TIMESTAMP(3)' })
  declare createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'datetime', precision: 3, default: () => 'CURRENT_TIMESTAMP(3)', onUpdate: 'CURRENT_TIMESTAMP(3)' })
  declare updatedAt: Date;
}

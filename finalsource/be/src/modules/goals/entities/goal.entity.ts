import { Check, Column, CreateDateColumn, Entity, Index, JoinColumn, ManyToOne, PrimaryGeneratedColumn, UpdateDateColumn } from 'typeorm';
import { User } from '../../auth/entities/user.entity';
import { Category } from '../../transactions/entities/category.entity';

export type GoalType = 'Saving' | 'Expense';

@Entity({ name: 'goals' })
@Check('chk_goals_type', "`goal_type` IN ('Saving', 'Expense')")
@Check('chk_goals_target_amount_positive', '`target_amount` > 0')
@Check('chk_goals_shape', "(`goal_type` = 'Saving' AND `category_id` IS NULL AND `period_month` IS NULL AND `start_date` IS NOT NULL AND `end_date` IS NOT NULL) OR (`goal_type` = 'Expense' AND `category_id` IS NOT NULL AND `period_month` IS NOT NULL AND `start_date` IS NOT NULL AND `end_date` IS NOT NULL)")
@Check('chk_goals_date_range', '`end_date` > `start_date`')
@Check('chk_goals_period_month_first_day', '`period_month` IS NULL OR DAY(`period_month`) = 1')
@Index('idx_goals_user_type_period', ['userId', 'goalType', 'periodMonth', 'id'])
@Index('idx_goals_user_type_dates', ['userId', 'goalType', 'startDate', 'endDate', 'id'])
@Index('uq_goals_user_category_period', ['userId', 'categoryId', 'periodMonth'], { unique: true })
export class GoalEntity {
  @PrimaryGeneratedColumn({ type: 'int', unsigned: true, name: 'id', primaryKeyConstraintName: 'pk_goals' }) declare id: number;
  @Column({ type: 'int', unsigned: true, name: 'user_id' }) declare userId: number;
  @ManyToOne(() => User, { nullable: false, onDelete: 'RESTRICT' })
  @JoinColumn({ name: 'user_id', foreignKeyConstraintName: 'fk_goals_users' }) declare user: User;
  @Column({ type: 'varchar', length: 16, name: 'goal_type' }) declare goalType: GoalType;
  @Column({ type: 'decimal', precision: 19, scale: 4, name: 'target_amount' }) declare targetAmount: string;
  @Column({ type: 'int', unsigned: true, name: 'category_id', nullable: true }) declare categoryId: number | null;
  @ManyToOne(() => Category, { nullable: true, onDelete: 'RESTRICT' })
  @JoinColumn({ name: 'category_id', foreignKeyConstraintName: 'fk_goals_categories' }) declare category: Category | null;
  @Column({ type: 'date', name: 'period_month', nullable: true }) declare periodMonth: string | null;
  @Column({ type: 'date', name: 'start_date', nullable: true }) declare startDate: string | null;
  @Column({ type: 'date', name: 'end_date', nullable: true }) declare endDate: string | null;
  @CreateDateColumn({ type: 'datetime', precision: 3, name: 'created_at', default: () => 'CURRENT_TIMESTAMP(3)' }) declare createdAt: Date;
  @UpdateDateColumn({ type: 'datetime', precision: 3, name: 'updated_at', default: () => 'CURRENT_TIMESTAMP(3)', onUpdate: 'CURRENT_TIMESTAMP(3)' }) declare updatedAt: Date;
}

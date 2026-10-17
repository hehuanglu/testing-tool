import { Column, CreateDateColumn, Entity, Index, JoinColumn, ManyToOne, PrimaryGeneratedColumn, UpdateDateColumn } from 'typeorm';
import { User } from '../../auth/entities/user.entity';

@Entity({ name: 'categories' })
@Index('idx_categories_user_id', ['userId', 'id'])
export class Category {
  @PrimaryGeneratedColumn({ type: 'int', unsigned: true, name: 'id', primaryKeyConstraintName: 'pk_categories' })
  declare id: number;

  @Column({ type: 'int', unsigned: true, name: 'user_id' })
  declare userId: number;

  @ManyToOne(() => User, { nullable: false, onDelete: 'RESTRICT' })
  @JoinColumn({ name: 'user_id', foreignKeyConstraintName: 'fk_categories_users' })
  declare user: User;

  @Column({ type: 'varchar', length: 160, name: 'name' })
  declare name: string;

  @CreateDateColumn({ type: 'datetime', precision: 3, name: 'created_at', default: () => 'CURRENT_TIMESTAMP(3)' })
  declare createdAt: Date;

  @UpdateDateColumn({ type: 'datetime', precision: 3, name: 'updated_at', default: () => 'CURRENT_TIMESTAMP(3)', onUpdate: 'CURRENT_TIMESTAMP(3)' })
  declare updatedAt: Date;
}

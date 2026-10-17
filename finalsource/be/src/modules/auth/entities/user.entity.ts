import { Column, CreateDateColumn, Entity, Index, PrimaryGeneratedColumn, UpdateDateColumn } from 'typeorm';

@Entity({ name: 'users' })
@Index('uq_users_email', ['email'], { unique: true })
export class User {
  @PrimaryGeneratedColumn({ type: 'int', unsigned: true, name: 'id', primaryKeyConstraintName: 'pk_users' })
  declare id: number;

  @Column({ type: 'varchar', length: 254, name: 'email' })
  declare email: string;

  @Column({ type: 'varchar', length: 120, name: 'full_name' })
  declare fullName: string;

  @Column({ type: 'varchar', length: 60, name: 'password_hash', select: false })
  declare passwordHash: string;

  @CreateDateColumn({ type: 'datetime', precision: 3, name: 'created_at', default: () => 'CURRENT_TIMESTAMP(3)' })
  declare createdAt: Date;

  @UpdateDateColumn({ type: 'datetime', precision: 3, name: 'updated_at', default: () => 'CURRENT_TIMESTAMP(3)', onUpdate: 'CURRENT_TIMESTAMP(3)' })
  declare updatedAt: Date;
}

import { MigrationInterface, QueryRunner, Table, TableIndex } from 'typeorm';

export class CreateUsers1791135661000 implements MigrationInterface {
  name = 'CreateUsers1791135661000';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.createTable(new Table({
      name: 'users',
      columns: [
        { name: 'id', type: 'int', unsigned: true, isPrimary: true, isGenerated: true, generationStrategy: 'increment', primaryKeyConstraintName: 'pk_users' },
        { name: 'email', type: 'varchar', length: '254', isNullable: false },
        { name: 'full_name', type: 'varchar', length: '120', isNullable: false },
        { name: 'password_hash', type: 'varchar', length: '60', isNullable: false },
        { name: 'created_at', type: 'datetime', precision: 3, default: 'CURRENT_TIMESTAMP(3)', isNullable: false },
        { name: 'updated_at', type: 'datetime', precision: 3, default: 'CURRENT_TIMESTAMP(3)', onUpdate: 'CURRENT_TIMESTAMP(3)', isNullable: false },
      ],
    }), true);
    const usersTable = await queryRunner.getTable('users');
    const emailIndexExists = usersTable?.indices.some((index) => index.name === 'uq_users_email') ?? false;

    if (!emailIndexExists) {
      await queryRunner.createIndex('users', new TableIndex({ name: 'uq_users_email', columnNames: ['email'], isUnique: true }));
    }
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.dropTable('users');
  }
}

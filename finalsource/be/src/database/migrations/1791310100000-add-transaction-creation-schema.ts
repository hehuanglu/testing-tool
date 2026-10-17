import { MigrationInterface, QueryRunner, Table, TableColumn, TableForeignKey, TableIndex } from 'typeorm';

function readCount(rows: unknown): number {
  if (!Array.isArray(rows) || rows.length !== 1) {
    throw new Error('Could not verify transaction migration precondition');
  }
  const first: unknown = rows[0];
  if (typeof first !== 'object' || first === null || !('count' in first)) {
    throw new Error('Could not verify transaction migration precondition');
  }
  const value: unknown = first.count;
  if (typeof value !== 'string' && typeof value !== 'number') throw new Error('Could not verify transaction migration precondition');
  const count = Number(value);
  if (!Number.isSafeInteger(count) || count < 0) throw new Error('Could not verify transaction migration precondition');
  return count;
}

async function constraintExists(queryRunner: QueryRunner, tableName: string, constraintName: string): Promise<boolean> {
  const rows: unknown = await queryRunner.query(
    'SELECT COUNT(*) AS `count` FROM `information_schema`.`TABLE_CONSTRAINTS` WHERE `TABLE_SCHEMA` = DATABASE() AND `TABLE_NAME` = ? AND `CONSTRAINT_NAME` = ?',
    [tableName, constraintName],
  );
  return readCount(rows) > 0;
}

export class AddTransactionCreationSchema1791310100000 implements MigrationInterface {
  name = 'AddTransactionCreationSchema1791310100000';

  async up(queryRunner: QueryRunner): Promise<void> {
    const rows: unknown = await queryRunner.query('SELECT COUNT(*) AS `count` FROM `transactions`');
    if (readCount(rows) !== 0) {
      throw new Error('UC-004 migration requires an approved category backfill for existing transactions');
    }

    if (!(await queryRunner.hasColumn('accounts', 'balance'))) {
      await queryRunner.addColumn('accounts', new TableColumn({
        name: 'balance',
        type: 'decimal',
        precision: 19,
        scale: 4,
        isNullable: false,
        default: '0.0000',
      }));
    }
    if (!(await constraintExists(queryRunner, 'accounts', 'chk_accounts_balance_nonnegative'))) {
      await queryRunner.query('ALTER TABLE `accounts` ADD CONSTRAINT `chk_accounts_balance_nonnegative` CHECK (`balance` >= 0)');
    }

    if (!(await queryRunner.hasTable('categories'))) {
      await queryRunner.createTable(new Table({
        name: 'categories',
        columns: [
          { name: 'id', type: 'int', unsigned: true, isPrimary: true, isGenerated: true, generationStrategy: 'increment', primaryKeyConstraintName: 'pk_categories' },
          { name: 'user_id', type: 'int', unsigned: true, isNullable: false },
          { name: 'name', type: 'varchar', length: '160', isNullable: false },
          { name: 'created_at', type: 'datetime', precision: 3, default: 'CURRENT_TIMESTAMP(3)', isNullable: false },
          { name: 'updated_at', type: 'datetime', precision: 3, default: 'CURRENT_TIMESTAMP(3)', onUpdate: 'CURRENT_TIMESTAMP(3)', isNullable: false },
        ],
        foreignKeys: [{ name: 'fk_categories_users', columnNames: ['user_id'], referencedTableName: 'users', referencedColumnNames: ['id'], onDelete: 'RESTRICT' }],
      }), true);
    }
    const categories = await queryRunner.getTable('categories');
    if (!categories?.indices.some((index) => index.name === 'idx_categories_user_id')) {
      await queryRunner.createIndex('categories', new TableIndex({ name: 'idx_categories_user_id', columnNames: ['user_id', 'id'] }));
    }

    if (!(await queryRunner.hasColumn('transactions', 'category_id'))) {
      await queryRunner.addColumn('transactions', new TableColumn({ name: 'category_id', type: 'int', unsigned: true, isNullable: false }));
    }
    let transactions = await queryRunner.getTable('transactions');
    if (!transactions?.indices.some((index) => index.name === 'idx_transactions_category_id')) {
      await queryRunner.createIndex('transactions', new TableIndex({ name: 'idx_transactions_category_id', columnNames: ['category_id'] }));
    }
    transactions = await queryRunner.getTable('transactions');
    if (!transactions?.foreignKeys.some((foreignKey) => foreignKey.name === 'fk_transactions_categories')) {
      await queryRunner.createForeignKey('transactions', new TableForeignKey({
        name: 'fk_transactions_categories',
        columnNames: ['category_id'],
        referencedTableName: 'categories',
        referencedColumnNames: ['id'],
        onDelete: 'RESTRICT',
      }));
    }
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.dropForeignKey('transactions', 'fk_transactions_categories');
    await queryRunner.dropIndex('transactions', 'idx_transactions_category_id');
    await queryRunner.dropColumn('transactions', 'category_id');
    await queryRunner.dropTable('categories');
    if (await constraintExists(queryRunner, 'accounts', 'chk_accounts_balance_nonnegative')) {
      await queryRunner.query('ALTER TABLE `accounts` DROP CHECK `chk_accounts_balance_nonnegative`');
    }
    await queryRunner.dropColumn('accounts', 'balance');
  }
}

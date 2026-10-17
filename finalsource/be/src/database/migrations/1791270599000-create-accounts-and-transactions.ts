import { MigrationInterface, QueryRunner, Table, TableIndex } from 'typeorm';

export class CreateAccountsAndTransactions1791270599000 implements MigrationInterface {
  name = 'CreateAccountsAndTransactions1791270599000';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.createTable(new Table({
      name: 'accounts',
      columns: [
        { name: 'id', type: 'int', unsigned: true, isPrimary: true, isGenerated: true, generationStrategy: 'increment', primaryKeyConstraintName: 'pk_accounts' },
        { name: 'user_id', type: 'int', unsigned: true, isNullable: false },
        { name: 'created_at', type: 'datetime', precision: 3, default: 'CURRENT_TIMESTAMP(3)', isNullable: false },
        { name: 'updated_at', type: 'datetime', precision: 3, default: 'CURRENT_TIMESTAMP(3)', onUpdate: 'CURRENT_TIMESTAMP(3)', isNullable: false },
      ],
      foreignKeys: [{ name: 'fk_accounts_users', columnNames: ['user_id'], referencedTableName: 'users', referencedColumnNames: ['id'], onDelete: 'RESTRICT' }],
    }), true);
    await queryRunner.createIndex('accounts', new TableIndex({ name: 'idx_accounts_user_id', columnNames: ['user_id', 'id'] }));

    await queryRunner.createTable(new Table({
      name: 'transactions',
      columns: [
        { name: 'id', type: 'int', unsigned: true, isPrimary: true, isGenerated: true, generationStrategy: 'increment', primaryKeyConstraintName: 'pk_transactions' },
        { name: 'account_id', type: 'int', unsigned: true, isNullable: false },
        { name: 'transaction_date', type: 'datetime', precision: 3, isNullable: false },
        { name: 'type', type: 'varchar', length: '16', isNullable: false },
        { name: 'item_description', type: 'varchar', length: '255', isNullable: false },
        { name: 'shop_name', type: 'varchar', length: '160', isNullable: false },
        { name: 'amount', type: 'decimal', precision: 19, scale: 4, isNullable: false },
        { name: 'payment_method', type: 'varchar', length: '64', isNullable: false },
        { name: 'status', type: 'varchar', length: '32', isNullable: false },
        { name: 'receipt_id', type: 'varchar', length: '255', isNullable: true, default: null },
        { name: 'created_at', type: 'datetime', precision: 3, default: 'CURRENT_TIMESTAMP(3)', isNullable: false },
        { name: 'updated_at', type: 'datetime', precision: 3, default: 'CURRENT_TIMESTAMP(3)', onUpdate: 'CURRENT_TIMESTAMP(3)', isNullable: false },
      ],
      checks: [
        { name: 'chk_transactions_type', expression: "`type` IN ('Revenue', 'Expense')" },
        { name: 'chk_transactions_amount_positive', expression: '`amount` > 0' },
      ],
      foreignKeys: [{ name: 'fk_transactions_accounts', columnNames: ['account_id'], referencedTableName: 'accounts', referencedColumnNames: ['id'], onDelete: 'RESTRICT' }],
    }), true);
    await queryRunner.createIndex('transactions', new TableIndex({ name: 'idx_transactions_account_date_id', columnNames: ['account_id', 'transaction_date', 'id'] }));
    await queryRunner.createIndex('transactions', new TableIndex({ name: 'idx_transactions_account_type_date_id', columnNames: ['account_id', 'type', 'transaction_date', 'id'] }));
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.dropTable('transactions');
    await queryRunner.dropTable('accounts');
  }
}

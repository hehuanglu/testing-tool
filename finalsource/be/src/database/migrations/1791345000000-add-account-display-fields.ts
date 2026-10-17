import { MigrationInterface, QueryRunner, TableColumn } from 'typeorm';

export class AddAccountDisplayFields1791345000000 implements MigrationInterface {
  name = 'AddAccountDisplayFields1791345000000';

  async up(queryRunner: QueryRunner): Promise<void> {
    const rows: unknown = await queryRunner.query('SELECT COUNT(*) AS `count` FROM `accounts`');
    if (!Array.isArray(rows) || rows.length !== 1) throw new Error('Could not verify account migration prerequisite');
    const row: unknown = rows[0];
    if (typeof row !== 'object' || row === null || !('count' in row) || String(row.count) !== '0') {
      throw new Error('UC-005 migration requires separately approved account metadata backfill for existing rows');
    }
    await queryRunner.addColumns('accounts', [
      new TableColumn({ name: 'bank_name', type: 'varchar', length: '160', isNullable: false }),
      new TableColumn({ name: 'account_type', type: 'varchar', length: '64', isNullable: false }),
      new TableColumn({ name: 'branch_name', type: 'varchar', length: '160', isNullable: false }),
      new TableColumn({ name: 'account_number_last_4', type: 'char', length: '4', isNullable: false }),
    ]);
    await queryRunner.query("ALTER TABLE `accounts` ADD CONSTRAINT `chk_accounts_number_last4` CHECK (`account_number_last_4` REGEXP '^[0-9]{4}$')");
  }

  down(): Promise<void> {
    return Promise.reject(new Error('Dropping account display metadata requires separate destructive rollback approval'));
  }
}

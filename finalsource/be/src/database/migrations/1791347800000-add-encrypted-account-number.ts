import { MigrationInterface, QueryRunner, TableColumn, TableIndex } from 'typeorm';

export class AddEncryptedAccountNumber1791347800000 implements MigrationInterface {
  name = 'AddEncryptedAccountNumber1791347800000';

  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.addColumns('accounts', [
      new TableColumn({ name: 'account_number_ciphertext', type: 'varbinary', length: '256', isNullable: true }),
      new TableColumn({ name: 'account_number_iv', type: 'binary', length: '12', isNullable: true }),
      new TableColumn({ name: 'account_number_auth_tag', type: 'binary', length: '16', isNullable: true }),
      new TableColumn({ name: 'account_number_key_version', type: 'smallint', unsigned: true, isNullable: true }),
      new TableColumn({ name: 'account_number_lookup_hash', type: 'binary', length: '32', isNullable: true }),
    ]);
    await queryRunner.query(
      'ALTER TABLE `accounts` ADD CONSTRAINT `chk_accounts_number_crypto_group` CHECK ((`account_number_ciphertext` IS NULL AND `account_number_iv` IS NULL AND `account_number_auth_tag` IS NULL AND `account_number_key_version` IS NULL AND `account_number_lookup_hash` IS NULL) OR (`account_number_ciphertext` IS NOT NULL AND `account_number_iv` IS NOT NULL AND `account_number_auth_tag` IS NOT NULL AND `account_number_key_version` IS NOT NULL AND `account_number_lookup_hash` IS NOT NULL))',
    );
    await queryRunner.createIndex(
      'accounts',
      new TableIndex({ name: 'uq_accounts_user_number_hash', columnNames: ['user_id', 'account_number_lookup_hash'], isUnique: true }),
    );
  }

  down(): Promise<void> {
    return Promise.reject(new Error('Dropping encrypted account-number data requires separate destructive rollback approval'));
  }
}

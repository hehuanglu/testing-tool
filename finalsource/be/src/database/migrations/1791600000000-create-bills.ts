import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateBills1791600000000 implements MigrationInterface {
  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`CREATE TABLE bills (
      id INT UNSIGNED NOT NULL AUTO_INCREMENT,
      user_id INT UNSIGNED NOT NULL,
      item_description VARCHAR(255) NOT NULL,
      logo_url VARCHAR(2048) NOT NULL,
      due_date DATE NOT NULL,
      last_charge_date DATE NOT NULL,
      amount DECIMAL(19,4) NOT NULL,
      created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
      updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
      CONSTRAINT pk_bills PRIMARY KEY (id),
      CONSTRAINT fk_bills_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
      CONSTRAINT chk_bills_amount_positive CHECK (amount > 0),
      INDEX idx_bills_user_due_id (user_id, due_date, id)
    ) ENGINE=InnoDB`);
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query('DROP TABLE bills');
  }
}

import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateGoals1791728321000 implements MigrationInterface {
  name = 'CreateGoals1791728321000';
  async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`CREATE TABLE \`goals\` (
      \`id\` int unsigned NOT NULL AUTO_INCREMENT, \`user_id\` int unsigned NOT NULL,
      \`goal_type\` varchar(16) NOT NULL, \`target_amount\` decimal(19,4) NOT NULL,
      \`category_id\` int unsigned NULL, \`period_month\` date NULL, \`start_date\` date NULL, \`end_date\` date NULL,
      \`created_at\` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
      \`updated_at\` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
      CONSTRAINT \`pk_goals\` PRIMARY KEY (\`id\`),
      CONSTRAINT \`fk_goals_users\` FOREIGN KEY (\`user_id\`) REFERENCES \`users\` (\`id\`) ON DELETE RESTRICT,
      CONSTRAINT \`fk_goals_categories\` FOREIGN KEY (\`category_id\`) REFERENCES \`categories\` (\`id\`) ON DELETE RESTRICT,
      CONSTRAINT \`chk_goals_type\` CHECK (\`goal_type\` IN ('Saving','Expense')),
      CONSTRAINT \`chk_goals_target_amount_positive\` CHECK (\`target_amount\` > 0),
      CONSTRAINT \`chk_goals_shape\` CHECK ((\`goal_type\`='Saving' AND \`category_id\` IS NULL AND \`period_month\` IS NULL AND \`start_date\` IS NOT NULL AND \`end_date\` IS NOT NULL) OR (\`goal_type\`='Expense' AND \`category_id\` IS NOT NULL AND \`period_month\` IS NOT NULL AND \`start_date\` IS NULL AND \`end_date\` IS NULL)),
      CONSTRAINT \`chk_goals_saving_date_range\` CHECK (\`goal_type\` <> 'Saving' OR \`end_date\` >= \`start_date\`),
      CONSTRAINT \`chk_goals_period_month_first_day\` CHECK (\`period_month\` IS NULL OR DAY(\`period_month\`)=1),
      UNIQUE INDEX \`uq_goals_user_category_period\` (\`user_id\`,\`category_id\`,\`period_month\`),
      INDEX \`idx_goals_user_type_period\` (\`user_id\`,\`goal_type\`,\`period_month\`,\`id\`),
      INDEX \`idx_goals_user_type_dates\` (\`user_id\`,\`goal_type\`,\`start_date\`,\`end_date\`,\`id\`)
    ) ENGINE=InnoDB`);
  }
  async down(queryRunner: QueryRunner): Promise<void> {
    const rows: unknown = await queryRunner.query('SELECT COUNT(*) AS `count` FROM `goals`');
    const row: unknown = Array.isArray(rows) ? (rows as unknown[])[0] : undefined;
    if (rows === null || !Array.isArray(rows) || rows.length !== 1 || typeof row !== 'object' || row === null || !('count' in row) || Number(row.count) !== 0) {
      throw new Error('Dropping non-empty goals requires separate destructive rollback approval');
    }
    await queryRunner.dropTable('goals');
  }
}

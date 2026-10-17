import { MigrationInterface, QueryRunner } from 'typeorm';

export class AlignGoalsDateRanges1791746799000 implements MigrationInterface {
  name = 'AlignGoalsDateRanges1791746799000';

  async up(queryRunner: QueryRunner): Promise<void> {
    const invalidSavingRows: unknown = await queryRunner.query(
      "SELECT COUNT(*) AS `count` FROM `goals` WHERE `goal_type` = 'Saving' AND `end_date` <= `start_date`",
    );
    if (singleCount(invalidSavingRows) !== 0) {
      throw new Error('UC-014 migration requires resolution of non-increasing Saving goal date ranges');
    }

    await queryRunner.query('ALTER TABLE `goals` DROP CHECK `chk_goals_shape`');
    await queryRunner.query('ALTER TABLE `goals` DROP CHECK `chk_goals_saving_date_range`');
    await queryRunner.query(
      "UPDATE `goals` SET `start_date` = `period_month`, `end_date` = LAST_DAY(`period_month`) WHERE `goal_type` = 'Expense' AND `start_date` IS NULL AND `end_date` IS NULL",
    );
    await queryRunner.query(
      "ALTER TABLE `goals` ADD CONSTRAINT `chk_goals_shape` CHECK ((`goal_type`='Saving' AND `category_id` IS NULL AND `period_month` IS NULL AND `start_date` IS NOT NULL AND `end_date` IS NOT NULL) OR (`goal_type`='Expense' AND `category_id` IS NOT NULL AND `period_month` IS NOT NULL AND `start_date` IS NOT NULL AND `end_date` IS NOT NULL))",
    );
    await queryRunner.query('ALTER TABLE `goals` ADD CONSTRAINT `chk_goals_date_range` CHECK (`end_date` > `start_date`)');
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    const nonReversibleRows: unknown = await queryRunner.query(
      "SELECT COUNT(*) AS `count` FROM `goals` WHERE `goal_type` = 'Expense' AND (`start_date` <> `period_month` OR `end_date` <> LAST_DAY(`period_month`))",
    );
    if (singleCount(nonReversibleRows) !== 0) {
      throw new Error('Rollback would discard approved Expense goal date ranges');
    }
    await queryRunner.query('ALTER TABLE `goals` DROP CHECK `chk_goals_date_range`');
    await queryRunner.query('ALTER TABLE `goals` DROP CHECK `chk_goals_shape`');
    await queryRunner.query("UPDATE `goals` SET `start_date` = NULL, `end_date` = NULL WHERE `goal_type` = 'Expense'");
    await queryRunner.query(
      "ALTER TABLE `goals` ADD CONSTRAINT `chk_goals_shape` CHECK ((`goal_type`='Saving' AND `category_id` IS NULL AND `period_month` IS NULL AND `start_date` IS NOT NULL AND `end_date` IS NOT NULL) OR (`goal_type`='Expense' AND `category_id` IS NOT NULL AND `period_month` IS NOT NULL AND `start_date` IS NULL AND `end_date` IS NULL))",
    );
    await queryRunner.query("ALTER TABLE `goals` ADD CONSTRAINT `chk_goals_saving_date_range` CHECK (`goal_type` <> 'Saving' OR `end_date` >= `start_date`)");
  }
}

function singleCount(rows: unknown): number | null {
  if (!Array.isArray(rows) || rows.length !== 1) return null;
  const row: unknown = rows[0];
  if (typeof row !== 'object' || row === null || !('count' in row)) return null;
  const count = Number(row.count);
  return Number.isSafeInteger(count) && count >= 0 ? count : null;
}

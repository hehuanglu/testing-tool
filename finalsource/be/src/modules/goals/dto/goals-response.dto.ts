import { ApiProperty } from '@nestjs/swagger';

export class SavingGoalDto {
  @ApiProperty({ example: 1 }) declare goal_id: number;
  @ApiProperty({ example: 'Saving' }) declare goal_type: 'Saving';
  @ApiProperty({ example: 60000000 }) declare target_amount: number;
  @ApiProperty({ example: 10000000 }) declare target_achieved: number;
  @ApiProperty({ example: '2025-01-01', format: 'date' }) declare start_date: string;
  @ApiProperty({ example: '2025-12-31', format: 'date' }) declare end_date: string;
}

export class ExpenseGoalDto {
  @ApiProperty({ example: 2 }) declare goal_id: number;
  @ApiProperty({ example: 'Food' }) declare category: string;
  @ApiProperty({ example: 3000000 }) declare target_amount: number;
}

export class GoalsResponseDto {
  @ApiProperty({ type: SavingGoalDto, nullable: true }) declare savingGoal: SavingGoalDto | null;
  @ApiProperty({ type: [ExpenseGoalDto] }) declare expenseGoals: ExpenseGoalDto[];
}

import { ApiProperty } from '@nestjs/swagger';

export class UpdatedGoalDto {
  @ApiProperty({ name: 'goal_id', example: 1 })
  declare goal_id: number;

  @ApiProperty({ name: 'target_amount', example: 70000000 })
  declare target_amount: number;
}

export class UpdateGoalResponseDto {
  @ApiProperty({ name: 'updated_goal', type: UpdatedGoalDto })
  declare updated_goal: UpdatedGoalDto;
}

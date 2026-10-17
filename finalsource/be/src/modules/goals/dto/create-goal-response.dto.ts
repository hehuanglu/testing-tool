import { ApiProperty } from '@nestjs/swagger';

export class CreateGoalResponseDto {
  @ApiProperty({ name: 'goal_id', example: 9 })
  declare goal_id: number;
}

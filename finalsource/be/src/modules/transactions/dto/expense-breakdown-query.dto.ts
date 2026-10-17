import { ApiProperty } from '@nestjs/swagger';
import { IsString, Matches } from 'class-validator';

export class ExpenseBreakdownQueryDto {
  @ApiProperty({ example: '2025-11', pattern: '^[1-9]\\d{3}-(0[1-9]|1[0-2])$' })
  @IsString()
  @Matches(/^[1-9]\d{3}-(0[1-9]|1[0-2])$/)
  declare readonly month: string;
}

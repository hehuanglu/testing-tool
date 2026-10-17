import { ApiPropertyOptional } from '@nestjs/swagger';
import { Type } from 'class-transformer';
import { IsInt, IsOptional, Max, Min } from 'class-validator';

export class SavingsSummaryQueryDto {
  @ApiPropertyOptional({ example: 2025, minimum: 1000, maximum: 9999, description: 'Calendar year; defaults to the current UTC year' })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1000)
  @Max(9999)
  declare readonly year?: number;
}

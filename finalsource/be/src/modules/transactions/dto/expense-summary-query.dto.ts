import { Type } from 'class-transformer';
import { IsInt, IsOptional, Min } from 'class-validator';

export class ExpenseSummaryQueryDto {
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  declare userId?: number;
}

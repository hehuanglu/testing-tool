import { Type } from 'class-transformer';
import { IsInt, IsString, Max, Min } from 'class-validator';

export class ListTransactionsQueryDto {
  @IsString()
  declare readonly type: string;

  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  readonly limit: number = 10;

  @Type(() => Number)
  @IsInt()
  @Min(0)
  readonly offset: number = 0;
}

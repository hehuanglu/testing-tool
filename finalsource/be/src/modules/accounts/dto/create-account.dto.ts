import { Transform, Type } from 'class-transformer';
import { IsNotEmpty, IsNumber, IsOptional, IsString, Length, Matches, MaxLength, Min } from 'class-validator';

const trim = ({ value }: { value: unknown }): unknown => (typeof value === 'string' ? value.trim() : value);

export class CreateAccountDto {
  @Transform(trim)
  @IsString()
  @IsNotEmpty()
  @MaxLength(160)
  declare readonly bank_name: string;

  @Transform(trim)
  @IsString()
  @IsNotEmpty()
  @MaxLength(64)
  declare readonly account_type: string;

  @Transform(trim)
  @IsOptional()
  @IsString()
  @MaxLength(160)
  declare readonly branch_name?: string;

  @Transform(trim)
  @IsString()
  @Length(4, 34)
  @Matches(/^[0-9]+$/, { message: 'account_number_full must contain only ASCII digits' })
  declare readonly account_number_full: string;

  @Type(() => Number)
  @IsNumber({ allowInfinity: false, allowNaN: false, maxDecimalPlaces: 4 })
  @Min(0)
  declare readonly balance: number;
}

import { Transform, Type } from 'class-transformer';
import { IsNotEmpty, IsNumber, IsOptional, IsString, Matches, Max, MaxLength, Min } from 'class-validator';

const trim = ({ value }: { value: unknown }): unknown => (typeof value === 'string' ? value.trim() : value);
const trimOptionalSensitive = ({ value }: { value: unknown }): unknown => {
  if (typeof value !== 'string') return value;
  const trimmed = value.trim();
  return trimmed.length === 0 ? undefined : trimmed;
};

export class UpdateAccountDto {
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

  @Transform(trimOptionalSensitive)
  @IsOptional()
  @IsString()
  @Matches(/^[0-9]{4,34}$/, { message: 'account_number_full must contain 4 to 34 ASCII digits' })
  declare readonly account_number_full?: string;

  @Transform(trimOptionalSensitive)
  @IsOptional()
  @IsString()
  @Matches(/^[0-9]{4}$/, { message: 'account_number_last_4 must contain exactly 4 ASCII digits' })
  declare readonly account_number_last_4?: string;

  @Type(() => Number)
  @IsNumber({ allowInfinity: false, allowNaN: false, maxDecimalPlaces: 4 })
  @Min(0)
  @Max(999_999_999_999_999)
  declare readonly balance: number;
}

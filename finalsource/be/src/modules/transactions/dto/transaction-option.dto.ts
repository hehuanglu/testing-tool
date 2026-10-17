import { ApiProperty } from '@nestjs/swagger';

export class AccountOptionDto {
  @ApiProperty({ example: 3 })
  declare accountId: number;
}

export class CategoryOptionDto {
  @ApiProperty({ name: 'category_id', example: 3 })
  declare category_id: number;

  @ApiProperty({ example: 'Entertainment' })
  declare name: string;
}

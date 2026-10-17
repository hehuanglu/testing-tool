import { Controller, Get, Header, Req, UseGuards } from '@nestjs/common';
import { ApiBearerAuth, ApiOkResponse, ApiOperation, ApiTags, ApiUnauthorizedResponse } from '@nestjs/swagger';
import type { Request } from 'express';
import { ResponseMessage } from '../../common/decorators/response-message.decorator';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import type { AuthenticatedPrincipal } from '../auth/jwt.strategy';
import { AccountOptionDto, CategoryOptionDto } from './dto/transaction-option.dto';
import { TransactionsService } from './transactions.service';

type AuthenticatedRequest = Request & { user: AuthenticatedPrincipal };

@ApiTags('Accounts')
@ApiBearerAuth()
@Controller('v1/accounts')
@UseGuards(JwtAuthGuard)
export class AccountOptionsController {
  constructor(private readonly transactionsService: TransactionsService) {}

  @Get('options')
  @Header('Cache-Control', 'no-store')
  @ResponseMessage('Account options retrieved successfully.')
  @ApiOperation({ summary: 'List account identifiers owned by the authenticated user' })
  @ApiOkResponse({ type: [AccountOptionDto] })
  @ApiUnauthorizedResponse({ description: 'Authentication is required' })
  list(@Req() request: AuthenticatedRequest): Promise<AccountOptionDto[]> {
    return this.transactionsService.listAccountOptions(request.user.userId);
  }
}

@ApiTags('Categories')
@ApiBearerAuth()
@Controller('v1/categories')
@UseGuards(JwtAuthGuard)
export class CategoryOptionsController {
  constructor(private readonly transactionsService: TransactionsService) {}

  @Get('options')
  @Header('Cache-Control', 'no-store')
  @ResponseMessage('Category options retrieved successfully.')
  @ApiOperation({ summary: 'List category identifiers and names owned by the authenticated user' })
  @ApiOkResponse({ type: [CategoryOptionDto] })
  @ApiUnauthorizedResponse({ description: 'Authentication is required' })
  list(@Req() request: AuthenticatedRequest): Promise<CategoryOptionDto[]> {
    return this.transactionsService.listCategoryOptions(request.user.userId);
  }
}

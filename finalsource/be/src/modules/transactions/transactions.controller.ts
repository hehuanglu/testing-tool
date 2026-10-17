import { Body, Controller, Get, Header, Post, Query, Req, UseGuards } from '@nestjs/common';
import { ApiBadRequestResponse, ApiBearerAuth, ApiCreatedResponse, ApiOkResponse, ApiOperation, ApiTags, ApiUnauthorizedResponse } from '@nestjs/swagger';
import type { Request } from 'express';
import { ResponseMessage } from '../../common/decorators/response-message.decorator';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import type { AuthenticatedPrincipal } from '../auth/jwt.strategy';
import { CreateTransactionDto } from './dto/create-transaction.dto';
import { CreateTransactionResponseDto } from './dto/create-transaction-response.dto';
import { ListTransactionsQueryDto } from './dto/list-transactions-query.dto';
import { TransactionListResponseDto } from './dto/transaction-list-response.dto';
import { TransactionsService } from './transactions.service';

type AuthenticatedRequest = Request & { user: AuthenticatedPrincipal };

@ApiTags('Transactions')
@ApiBearerAuth()
@Controller('v1/transactions')
@UseGuards(JwtAuthGuard)
export class TransactionsController {
  constructor(private readonly transactionsService: TransactionsService) {}

  @Get()
  @Header('Cache-Control', 'no-store')
  @ResponseMessage('Transaction list retrieved successfully.')
  @ApiOperation({ summary: 'List completed transactions owned by the authenticated user' })
  @ApiOkResponse({ type: TransactionListResponseDto, description: 'Transaction list retrieved' })
  @ApiBadRequestResponse({ description: 'Invalid type parameter' })
  @ApiUnauthorizedResponse({ description: 'Authentication is required' })
  list(@Req() request: AuthenticatedRequest, @Query() query: ListTransactionsQueryDto): Promise<TransactionListResponseDto> {
    return this.transactionsService.list(request.user.userId, query);
  }

  @Post()
  @Header('Cache-Control', 'no-store')
  @ResponseMessage('Transaction created successfully')
  @ApiOperation({ summary: 'Create a transaction and atomically update an owned account balance' })
  @ApiCreatedResponse({ type: CreateTransactionResponseDto, description: 'Transaction created' })
  @ApiBadRequestResponse({ description: 'Invalid or missing transaction data' })
  @ApiUnauthorizedResponse({ description: 'Authentication is required' })
  create(@Req() request: AuthenticatedRequest, @Body() dto: CreateTransactionDto): Promise<CreateTransactionResponseDto> {
    return this.transactionsService.create(request.user.userId, dto);
  }
}

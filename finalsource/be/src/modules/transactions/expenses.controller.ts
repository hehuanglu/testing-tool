import { Controller, Get, Header, Query, Req, UseGuards } from '@nestjs/common';
import { ApiBadRequestResponse, ApiBearerAuth, ApiInternalServerErrorResponse, ApiNotFoundResponse, ApiOkResponse, ApiOperation, ApiTags, ApiUnauthorizedResponse } from '@nestjs/swagger';
import type { Request } from 'express';
import { ResponseMessage } from '../../common/decorators/response-message.decorator';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import type { AuthenticatedPrincipal } from '../auth/jwt.strategy';
import { ExpenseBreakdownQueryDto } from './dto/expense-breakdown-query.dto';
import { ExpenseBreakdownResponseDto } from './dto/expense-breakdown-response.dto';
import { ExpenseSummaryQueryDto } from './dto/expense-summary-query.dto';
import { ExpenseSummaryResponseDto } from './dto/expense-summary-response.dto';
import { TransactionsService } from './transactions.service';

type AuthenticatedRequest = Request & { user: AuthenticatedPrincipal };

@ApiTags('Expenses')
@ApiBearerAuth()
@Controller('v1/expenses')
@UseGuards(JwtAuthGuard)
export class ExpensesController {
  constructor(private readonly transactionsService: TransactionsService) {}

  @Get('summary')
  @Header('Cache-Control', 'no-store')
  @ResponseMessage('Expense summary loaded successfully')
  @ApiOperation({ summary: 'Get current-year monthly expenses for the authenticated user' })
  @ApiOkResponse({ type: ExpenseSummaryResponseDto, description: 'Monthly expense summary loaded' })
  @ApiUnauthorizedResponse({ description: 'Authentication is required' })
  @ApiInternalServerErrorResponse({ description: 'Cannot load data for Expense.' })
  summary(@Req() request: AuthenticatedRequest, @Query() query: ExpenseSummaryQueryDto): Promise<ExpenseSummaryResponseDto> {
    void query.userId;
    return this.transactionsService.expenseSummary(request.user.userId);
  }

  @Get('breakdown')
  @Header('Cache-Control', 'no-store')
  @ResponseMessage('Expense breakdown loaded successfully')
  @ApiOperation({ summary: 'Get expense details grouped by category for an authenticated user and month' })
  @ApiOkResponse({ type: ExpenseBreakdownResponseDto, description: 'Expense breakdown loaded' })
  @ApiBadRequestResponse({ description: 'The month query must use YYYY-MM' })
  @ApiUnauthorizedResponse({ description: 'Authentication is required' })
  @ApiNotFoundResponse({ description: 'No input data for this month.' })
  @ApiInternalServerErrorResponse({ description: 'Internal server error' })
  breakdown(@Req() request: AuthenticatedRequest, @Query() query: ExpenseBreakdownQueryDto): Promise<ExpenseBreakdownResponseDto> {
    return this.transactionsService.expenseBreakdown(request.user.userId, query.month);
  }
}

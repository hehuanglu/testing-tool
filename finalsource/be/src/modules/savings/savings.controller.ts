import { Controller, Get, Header, Query, Req, UseGuards } from '@nestjs/common';
import { ApiBadRequestResponse, ApiBearerAuth, ApiInternalServerErrorResponse, ApiOkResponse, ApiOperation, ApiTags, ApiUnauthorizedResponse } from '@nestjs/swagger';
import type { Request } from 'express';
import { ResponseMessage } from '../../common/decorators/response-message.decorator';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import type { AuthenticatedPrincipal } from '../auth/jwt.strategy';
import { SavingsSummaryQueryDto } from './dto/savings-summary-query.dto';
import { SavingsSummaryResponseDto } from './dto/savings-summary-response.dto';
import { SavingsService } from './savings.service';

type AuthenticatedRequest = Request & { user: AuthenticatedPrincipal };

@ApiTags('Savings')
@ApiBearerAuth()
@Controller('v1/savings')
@UseGuards(JwtAuthGuard)
export class SavingsController {
  constructor(private readonly savingsService: SavingsService) {}

  @Get('summary')
  @Header('Cache-Control', 'no-store, max-age=0')
  @Header('Pragma', 'no-cache')
  @Header('Expires', '0')
  @ResponseMessage('Savings summary retrieved successfully.')
  @ApiOperation({ summary: 'Get monthly net savings for the selected and previous year' })
  @ApiOkResponse({ type: SavingsSummaryResponseDto })
  @ApiBadRequestResponse({ description: 'The year query must be a four-digit integer' })
  @ApiUnauthorizedResponse({ description: 'Authentication is required' })
  @ApiInternalServerErrorResponse({ description: 'An internal server error occurred while processing the Savings highlighting.' })
  summary(@Req() request: AuthenticatedRequest, @Query() query: SavingsSummaryQueryDto): Promise<SavingsSummaryResponseDto> {
    return this.savingsService.summary(request.user.userId, query.year ?? new Date().getUTCFullYear());
  }
}

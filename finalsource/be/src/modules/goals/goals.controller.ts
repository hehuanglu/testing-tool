import { Body, Controller, Get, Header, Param, ParseIntPipe, Post, Put, Req, UseGuards } from '@nestjs/common';
import { ApiBadRequestResponse, ApiBearerAuth, ApiCreatedResponse, ApiForbiddenResponse, ApiInternalServerErrorResponse, ApiNotFoundResponse, ApiOkResponse, ApiOperation, ApiTags, ApiUnauthorizedResponse } from '@nestjs/swagger';
import type { Request } from 'express';
import { ResponseMessage } from '../../common/decorators/response-message.decorator';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import type { AuthenticatedPrincipal } from '../auth/jwt.strategy';
import { CreateGoalDto } from './dto/create-goal.dto';
import { CreateGoalResponseDto } from './dto/create-goal-response.dto';
import { GoalsResponseDto } from './dto/goals-response.dto';
import { UpdateGoalDto } from './dto/update-goal.dto';
import { UpdateGoalResponseDto } from './dto/update-goal-response.dto';
import { GoalsService } from './goals.service';

type AuthenticatedRequest = Request & { user: AuthenticatedPrincipal };

@ApiTags('Goals') @ApiBearerAuth() @Controller('v1/goals') @UseGuards(JwtAuthGuard)
export class GoalsController {
  constructor(private readonly goalsService: GoalsService) {}
  @Get() @Header('Cache-Control', 'no-store, max-age=0') @Header('Pragma', 'no-cache') @Header('Expires', '0')
  @ResponseMessage('Goals loaded successfully.')
  @ApiOperation({ summary: 'View current goals for the authenticated user' })
  @ApiOkResponse({ type: GoalsResponseDto }) @ApiUnauthorizedResponse({ description: 'Authentication is required' })
  @ApiInternalServerErrorResponse({ description: '500 Internal Server Error. Try again.' })
  list(@Req() request: AuthenticatedRequest): Promise<GoalsResponseDto> { return this.goalsService.list(request.user.userId); }

  @Post() @Header('Cache-Control', 'no-store, max-age=0') @Header('Pragma', 'no-cache') @Header('Expires', '0')
  @ResponseMessage('Goal created successfully')
  @ApiOperation({ summary: 'Create a goal owned by the authenticated user' })
  @ApiCreatedResponse({ type: CreateGoalResponseDto })
  @ApiBadRequestResponse({ description: 'Invalid goal data' })
  @ApiUnauthorizedResponse({ description: 'Authentication is required' })
  @ApiInternalServerErrorResponse({ description: 'Cannot add Goals right now. Try again.' })
  create(@Req() request: AuthenticatedRequest, @Body() dto: CreateGoalDto): Promise<CreateGoalResponseDto> {
    return this.goalsService.create(request.user.userId, dto);
  }

  @Put(':goalId') @Header('Cache-Control', 'no-store, max-age=0') @Header('Pragma', 'no-cache') @Header('Expires', '0')
  @ResponseMessage('Goal updated successfully')
  @ApiOperation({ summary: 'Adjust a goal owned by the authenticated user' })
  @ApiOkResponse({ type: UpdateGoalResponseDto })
  @ApiBadRequestResponse({ description: 'Invalid goal identifier or target amount' })
  @ApiUnauthorizedResponse({ description: 'Authentication is required' })
  @ApiForbiddenResponse({ description: 'You do not have permission to edit this target.' })
  @ApiNotFoundResponse({ description: 'Goal not found.' })
  @ApiInternalServerErrorResponse({ description: 'Cannot update now. Try again.' })
  update(
    @Req() request: AuthenticatedRequest,
    @Param('goalId', ParseIntPipe) goalId: number,
    @Body() dto: UpdateGoalDto,
  ): Promise<UpdateGoalResponseDto> {
    return this.goalsService.update(request.user.userId, goalId, dto);
  }
}

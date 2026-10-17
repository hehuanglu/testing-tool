import { Body, Controller, Delete, Get, Header, HttpCode, HttpStatus, Param, ParseIntPipe, Post, Put, Req, UseGuards } from '@nestjs/common';
import {
  ApiBadRequestResponse,
  ApiBearerAuth,
  ApiConflictResponse,
  ApiCreatedResponse,
  ApiForbiddenResponse,
  ApiInternalServerErrorResponse,
  ApiNotFoundResponse,
  ApiOkResponse,
  ApiOperation,
  ApiTags,
  ApiUnauthorizedResponse,
} from '@nestjs/swagger';
import type { Request } from 'express';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import type { AuthenticatedPrincipal } from '../auth/jwt.strategy';
import { AccountsService } from './accounts.service';
import { AccountListEnvelopeDto, AccountListResponseDto } from './dto/account-list-response.dto';
import { AccountDetailEnvelopeDto, AccountDetailResponseDto } from './dto/account-detail-response.dto';
import { CreateAccountDto } from './dto/create-account.dto';
import { CreateAccountEnvelopeDto, CreateAccountResponseDto } from './dto/create-account-response.dto';
import { DeleteAccountEnvelopeDto, DeleteAccountResponseDto } from './dto/delete-account-response.dto';
import { UpdateAccountDto } from './dto/update-account.dto';
import { UpdateAccountEnvelopeDto, UpdateAccountResponseDto } from './dto/update-account-response.dto';
import { ResponseMessage } from '../../common/decorators/response-message.decorator';

@ApiTags('Accounts')
@ApiBearerAuth()
@Controller('v1/accounts')
@UseGuards(JwtAuthGuard)
export class AccountsController {
  constructor(private readonly accounts: AccountsService) {}

  @Get()
  @Header('Cache-Control', 'no-store')
  @ApiOperation({ summary: 'List accounts owned by the authenticated user' })
  @ApiOkResponse({ type: AccountListEnvelopeDto })
  @ApiUnauthorizedResponse({ description: 'Authentication is required' })
  @ApiInternalServerErrorResponse({ description: 'A system error has occurred, please try again later.' })
  list(@Req() request: Request & { user: AuthenticatedPrincipal }): Promise<AccountListResponseDto> {
    return this.accounts.list(request.user.userId);
  }

  @Get(':id')
  @Header('Cache-Control', 'no-store')
  @ResponseMessage('Account details retrieved successfully')
  @ApiOperation({ summary: 'View an owned account and its five most recent transactions' })
  @ApiOkResponse({ type: AccountDetailEnvelopeDto, description: 'Account details retrieved successfully' })
  @ApiBadRequestResponse({ description: 'Invalid account identifier' })
  @ApiUnauthorizedResponse({ description: 'Authentication is required' })
  @ApiForbiddenResponse({ description: 'You do not have permission to view this account information.' })
  @ApiNotFoundResponse({ description: 'This account was not found.' })
  @ApiInternalServerErrorResponse({ description: 'An error occurred, data could not be loaded.' })
  detail(
    @Req() request: Request & { user: AuthenticatedPrincipal },
    @Param('id', ParseIntPipe) accountId: number,
  ): Promise<AccountDetailResponseDto> {
    return this.accounts.detail(request.user.userId, accountId);
  }

  @Post()
  @HttpCode(HttpStatus.CREATED)
  @ResponseMessage('Account created successfully')
  @Header('Cache-Control', 'no-store')
  @ApiOperation({ summary: 'Create an account owned by the authenticated user' })
  @ApiCreatedResponse({ type: CreateAccountEnvelopeDto, description: 'Account created successfully' })
  @ApiBadRequestResponse({ description: 'Invalid account data' })
  @ApiUnauthorizedResponse({ description: 'Authentication is required' })
  @ApiConflictResponse({ description: 'This account already exists in your list.' })
  @ApiInternalServerErrorResponse({ description: 'Unable to add account at this time. Please try again later.' })
  create(
    @Req() request: Request & { user: AuthenticatedPrincipal },
    @Body() input: CreateAccountDto,
  ): Promise<CreateAccountResponseDto> {
    return this.accounts.create(request.user.userId, input);
  }

  @Put(':id')
  @HttpCode(HttpStatus.OK)
  @ResponseMessage('Account updated successfully')
  @Header('Cache-Control', 'no-store')
  @ApiOperation({ summary: 'Update an account after verifying ownership' })
  @ApiOkResponse({ type: UpdateAccountEnvelopeDto, description: 'Account updated successfully' })
  @ApiBadRequestResponse({ description: 'Invalid account data' })
  @ApiUnauthorizedResponse({ description: 'Authentication is required' })
  @ApiForbiddenResponse({ description: 'You do not have permission to edit this account information.' })
  @ApiNotFoundResponse({ description: 'Account not found.' })
  @ApiConflictResponse({ description: 'This account already exists in your list.' })
  @ApiInternalServerErrorResponse({ description: 'An error occurred while saving the data. Please try again later.' })
  update(
    @Req() request: Request & { user: AuthenticatedPrincipal },
    @Param('id', ParseIntPipe) accountId: number,
    @Body() input: UpdateAccountDto,
  ): Promise<UpdateAccountResponseDto> {
    return this.accounts.update(request.user.userId, accountId, input);
  }

  @Delete(':id')
  @HttpCode(HttpStatus.OK)
  @ResponseMessage('Account deleted successfully')
  @Header('Cache-Control', 'no-store')
  @ApiOperation({ summary: 'Delete an owned account and all of its transactions' })
  @ApiOkResponse({ type: DeleteAccountEnvelopeDto, description: 'Account deleted successfully' })
  @ApiBadRequestResponse({ description: 'Invalid account identifier' })
  @ApiUnauthorizedResponse({ description: 'Authentication is required' })
  @ApiForbiddenResponse({ description: 'You do not have permission to perform this operation.' })
  @ApiNotFoundResponse({ description: 'Account not found or not owned by current user' })
  @ApiInternalServerErrorResponse({ description: 'A system error occurred; it was not possible to delete the account and related transactions.' })
  remove(
    @Req() request: Request & { user: AuthenticatedPrincipal },
    @Param('id', ParseIntPipe) accountId: number,
  ): Promise<DeleteAccountResponseDto> {
    return this.accounts.remove(request.user.userId, accountId);
  }
}

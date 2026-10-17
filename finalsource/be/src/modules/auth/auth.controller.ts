import { Body, Controller, Header, HttpCode, HttpStatus, Post, Req } from '@nestjs/common';
import { ApiBadRequestResponse, ApiConflictResponse, ApiCreatedResponse, ApiOkResponse, ApiOperation, ApiTags, ApiUnauthorizedResponse } from '@nestjs/swagger';
import type { Request } from 'express';
import { ResponseMessage } from '../../common/decorators/response-message.decorator';
import { AuthService } from './auth.service';
import { LoginDto } from './dto/login.dto';
import { LoginResponseDto } from './dto/login-response.dto';
import { RegisterDto } from './dto/register.dto';
import { RegisterResponseDto } from './dto/register-response.dto';

@ApiTags('Authentication')
@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('login')
  @HttpCode(HttpStatus.OK)
  @Header('Cache-Control', 'no-store')
  @ResponseMessage('Login successful.')
  @ApiOperation({ summary: 'Authenticate with email and password' })
  @ApiOkResponse({ type: LoginResponseDto, description: 'Login succeeded' })
  @ApiUnauthorizedResponse({ description: 'Incorrect email or password.' })
  login(@Body() dto: LoginDto, @Req() request: Request): Promise<LoginResponseDto> {
    return this.authService.login(dto, request.ip ?? 'unknown');
  }

  @Post('register')
  @HttpCode(HttpStatus.CREATED)
  @Header('Cache-Control', 'no-store')
  @ResponseMessage('Registration successful')
  @ApiOperation({ summary: 'Create a user account and establish a login session' })
  @ApiCreatedResponse({ type: RegisterResponseDto, description: 'Registration succeeded' })
  @ApiBadRequestResponse({ description: 'Invalid registration data or passwords do not match.' })
  @ApiConflictResponse({ description: 'This email is already registered.' })
  register(@Body() dto: RegisterDto): Promise<RegisterResponseDto> {
    return this.authService.register(dto);
  }
}

import { BadRequestException, ConflictException, Injectable, Logger, OnModuleInit, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JwtService } from '@nestjs/jwt';
import { InjectRepository } from '@nestjs/typeorm';
import { compare, hash } from 'bcrypt';
import { createHash, randomBytes } from 'node:crypto';
import { QueryFailedError, Repository } from 'typeorm';
import { LoginDto } from './dto/login.dto';
import { LoginResponseDto } from './dto/login-response.dto';
import { RegisterDto } from './dto/register.dto';
import { RegisterResponseDto } from './dto/register-response.dto';
import { User } from './entities/user.entity';
import { LoginAttemptTracker } from './login-attempt-tracker.service';

@Injectable()
export class AuthService implements OnModuleInit {
  private readonly logger = new Logger(AuthService.name);
  private dummyPasswordHash?: string;

  constructor(
    @InjectRepository(User) private readonly users: Repository<User>,
    private readonly jwt: JwtService,
    private readonly config: ConfigService,
    private readonly attempts: LoginAttemptTracker,
  ) {}

  async onModuleInit(): Promise<void> {
    const cost = this.config.getOrThrow<number>('app.authentication.bcryptCost');
    this.dummyPasswordHash = await hash(randomBytes(32).toString('hex'), cost);
  }

  async login(dto: LoginDto, requestAddress: string): Promise<LoginResponseDto> {
    const email = dto.email.trim().toLowerCase();
    const attemptKey = createHash('sha256').update(`${requestAddress}\u0000${email}`).digest('hex');
    const dummyHash = this.requireDummyHash();

    if (this.attempts.isBlocked(attemptKey)) {
      await compare(dto.password, dummyHash);
      this.logger.warn('Authentication rejected by attempt policy');
      throw new UnauthorizedException('Incorrect email or password.');
    }

    const user = await this.users.createQueryBuilder('user')
      .addSelect('user.passwordHash')
      .where('user.email = :email', { email })
      .getOne();
    const passwordMatches = await compare(dto.password, user?.passwordHash ?? dummyHash);

    if (!user || !passwordMatches) {
      this.attempts.recordFailure(attemptKey);
      this.logger.warn('Authentication failed');
      throw new UnauthorizedException('Incorrect email or password.');
    }

    this.attempts.reset(attemptKey);
    const accessToken = await this.jwt.signAsync({ sub: user.id });
    this.logger.log('Authentication succeeded');
    return {
      accessToken,
      user: { id: user.id, fullName: user.fullName, email: user.email },
    };
  }

  async register(dto: RegisterDto): Promise<RegisterResponseDto> {
    if (dto.password !== dto['confirm Password']) {
      this.logger.warn('Registration rejected because password confirmation did not match');
      throw new BadRequestException('Passwords do not match.');
    }

    const email = dto.email.trim().toLowerCase();
    const fullName = dto.fullName.trim();
    const passwordHash = await hash(dto.password, this.config.getOrThrow<number>('app.authentication.bcryptCost'));

    try {
      const result = await this.users.manager.transaction(async (manager) => {
        const users = manager.getRepository(User);
        if (await users.exists({ where: { email } })) {
          throw new ConflictException('This email is already registered.');
        }

        const user = await users.save(users.create({ email, fullName, passwordHash }));
        const token = await this.jwt.signAsync({ sub: user.id });
        return {
          token,
          user: { id: user.id, fullName: user.fullName, email: user.email },
        };
      });
      this.logger.log('Registration succeeded');
      return result;
    } catch (error: unknown) {
      if (error instanceof ConflictException) {
        this.logger.warn('Registration rejected because the email is already registered');
        throw error;
      }
      if (this.isDuplicateEntry(error)) {
        this.logger.warn('Registration rejected by the unique email constraint');
        throw new ConflictException('This email is already registered.');
      }
      throw error;
    }
  }

  private requireDummyHash(): string {
    if (!this.dummyPasswordHash) throw new Error('Authentication service is not initialized');
    return this.dummyPasswordHash;
  }

  private isDuplicateEntry(error: unknown): boolean {
    if (!(error instanceof QueryFailedError)) return false;
    const driverError: unknown = error.driverError;
    return typeof driverError === 'object'
      && driverError !== null
      && 'code' in driverError
      && driverError.code === 'ER_DUP_ENTRY';
  }
}
